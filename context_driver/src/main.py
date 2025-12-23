import time
import os
import logging
import requests
import re
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging FIRST
print("DEBUG: LOADED NEW CODE WITH TRUNCATION AND PARSER FIXES", flush=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("context-driver")

from db import Database
from parser import parse_markdown
from enricher import enrich_markdown
from mcp_server import mcp as mcp_instance
from mcp.server.fastmcp import FastMCP

# Separate logger for prompt logging (can be toggled independently)
prompt_logger = logging.getLogger("context-driver.prompts")
LOG_PROMPTS = os.environ.get("LOG_PROMPTS", "false").lower() in ("true", "1", "yes")

def log_prompt_to_litellm(operation: str, model: str, messages: list, extra_info: dict = None):
    """Log the actual prompt being sent to LiteLLM for debugging/auditing."""
    if not LOG_PROMPTS:
        return
    
    try:
        prompt_logger.info(f"=== PROMPT TO LITELLM [{operation}] ===")
        prompt_logger.info(f"Model: {model}")
        if extra_info:
            prompt_logger.info(f"Extra: {extra_info}")
        
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # Truncate very long content for readability
            if len(content) > 2000:
                content_preview = content[:1000] + f"\n... [TRUNCATED {len(content) - 2000} chars] ...\n" + content[-1000:]
            else:
                content_preview = content
            prompt_logger.info(f"Message {i+1} [{role}]:\n{content_preview}")
        
        prompt_logger.info("=== END PROMPT ===")
    except Exception as e:
        logger.warning(f"Failed to log prompt: {e}")

from config import current_config

# Configuration
BRAIN_DIR = os.environ.get("BRAIN_DIR", "/app/brain")
OLLAMA_API_BASE = os.environ.get("OLLAMA_API_BASE", "http://host.docker.internal:11434")
LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE", "http://litellm:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-1234-5678-admin")
SEARCH_STRATEGY = os.environ.get("SEARCH_STRATEGY", "super_hybrid")  # Default to best quality

# Vendor API Keys (optional)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Model priority: OpenAI > Anthropic > Ollama
def get_preferred_model():
    if OPENAI_API_KEY:
        logger.info("Using OpenAI as primary LLM (OPENAI_API_KEY detected)")
        return "gpt-4o-mini"  # Cost-effective default
    elif ANTHROPIC_API_KEY:
        logger.info("Using Anthropic as primary LLM (ANTHROPIC_API_KEY detected)")
        return "claude-3-haiku-20240307"  # Cost-effective default
    else:
        logger.info("Using Ollama/llama3 as primary LLM (no vendor keys detected)")
        return "llama3"

REAL_MODEL = get_preferred_model()

db = Database()
cost_tracker = None

def get_embedding(text, cost_tracker=None):
    """Get embedding vector for text, optionally logging cost."""
    import time
    start_time = time.time()
    try:
        if current_config.provider == "ollama":
            url = f"{OLLAMA_API_BASE}/api/embeddings"
            response = requests.post(url, json={
                "model": current_config.model,
                "prompt": text
            })
            response.raise_for_status()
            vector = response.json()["embedding"]

        elif current_config.provider in ["openai", "litellm"]:
            # Use LiteLLM Proxy or direct OpenAI
            url = f"{LITELLM_API_BASE}/embeddings"
            response = requests.post(url, json={
                "model": current_config.model,
                "input": text
            }, headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"})
            
            if response.status_code != 200:
                logger.error(f"Embedding failed: {response.status_code} - {response.text}")
                response.raise_for_status()
                
            vector = response.json()["data"][0]["embedding"]
            
        else:
            logger.error(f"Unknown embedding provider: {current_config.provider}")
            return None
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log cost if tracker available
        if cost_tracker:
            from cost_tracker import estimate_tokens
            input_tokens = estimate_tokens(text)
            cost_tracker.log_request(
                operation="embedding",
                model=current_config.model,
                input_tokens=input_tokens,
                output_tokens=0,
                latency_ms=latency_ms
            )
        
        return vector
    except Exception as e:
        logger.error(f"Failed to get embedding: {e}")
        return None

def extract_semantic_keywords(content, title):
    """
    Calls the LLM to extract a 'human-readable embedding' (set of semantic keywords).
    """
    try:
        prompt = (
            f"Document Title: {title}\n\n"
            f"Content Fragment:\n{content[:2000]}\n\n"
            "INSTRUCTIONS:\n"
            "Summarize this document into a set of 5-8 highly descriptive keywords or short tags.\n"
            "These keywords should act as a 'human-readable embedding' - they should capture the unique identity and context of the document.\n"
            "Return ONLY a comma-separated list of keywords. No prose, no intro."
        )
        
        messages = [{"role": "user", "content": prompt}]
        log_prompt_to_litellm("extract_keywords", REAL_MODEL, messages, {"title": title})
        
        response = requests.post(
            f"{LITELLM_API_BASE}/chat/completions",
            json={
                "model": REAL_MODEL,
                "messages": messages,
                "temperature": 0.3
            },
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            timeout=30
        )
        response.raise_for_status()
        keywords = response.json()["choices"][0]["message"]["content"].strip()
        # Clean up in case LLM added quotes or extra text
        keywords = keywords.replace('"', '').replace('Keywords:', '').strip()
        return [k.strip() for k in keywords.split(',') if k.strip()]
    except Exception as e:
        logger.warning(f"Failed to extract semantic keywords: {e}")
        return []

def process_file(file_path):
    try:
        if not os.path.exists(file_path):
            return
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parsed = parse_markdown(content)
        title = parsed['metadata'].get('title', os.path.basename(file_path).replace('.md', ''))
        
        note_id, was_updated = db.upsert_note(
            file_path=file_path,
            title=title,
            content=parsed['content'],
            metadata=parsed['metadata']
        )
        
        if was_updated:
            logger.info(f"Upserted note: {title} (ID: {note_id})")

            if parsed['links']:
                db.update_links(note_id, parsed['links'])
                logger.info(f"Updated {len(parsed['links'])} links for {title}")

            # Chunk the content and create embeddings for each chunk
            if parsed['content']:
                from chunker import split_markdown
                chunks = split_markdown(parsed['content'], max_tokens=500, overlap_tokens=50)
                
                if chunks:
                    # Store chunks in database
                    db.upsert_chunks(note_id, chunks)
                    
                    # Generate embedding for each chunk
                    for chunk in chunks:
                        chunk_vector = get_embedding(chunk.content, cost_tracker=cost_tracker)
                        if chunk_vector:
                            db.update_chunk_embedding(note_id, chunk.chunk_index, chunk_vector)
                    
                    logger.info(f"Created {len(chunks)} chunks with embeddings for {title}")
                
                # Also keep note-level embedding as fallback
                
                # 2. Extract keywords (if enabled and not present)
                # Default to enabled, or check env var
                enable_keywords = os.environ.get("ENABLE_KEYWORD_EXTRACTION", "true").lower() == "true"
                if enable_keywords and 'keywords' not in parsed['metadata']:
                    from prompts import extract_keywords
                    keywords = extract_keywords(parsed['content'], title)
                    if keywords:
                        parsed['metadata']['keywords'] = keywords
                        db.upsert_note(file_path, title, parsed['content'], parsed['metadata'])
                        logger.info(f"Extracted and updated keywords for {title}: {keywords}")

                # Truncate content for embedding
                try:
                    import tiktoken
                    encoding = tiktoken.encoding_for_model(current_config.model)
                    tokens = encoding.encode(parsed['content'])

                    if len(tokens) > 8000:
                        truncated_tokens = tokens[:8000]
                        truncated_content = encoding.decode(truncated_tokens)
                        logger.info(f"Truncated content from {len(tokens)} to 8000 tokens")
                    else:
                        truncated_content = parsed['content']
                except ImportError:
                    logger.warning("tiktoken not found, falling back to strict character truncation")
                    truncated_content = parsed['content'][:15000]
                
                vector = get_embedding(truncated_content, cost_tracker=cost_tracker)
                if vector:
                    db.update_embedding(note_id, vector)
                    logger.info(f"Updated note-level embedding for {title}")
        else:
            logger.debug(f"Note {title} unchanged, skipping re-embedding.")

        # 4. Enrich and Write-back (only for real files, not virtual webui://)
        if not file_path.startswith("webui://"):
            try:
                # Add ingestion/source metadata
                enrich_metadata = parsed['metadata'].copy()
                enrich_metadata['source'] = file_path
                enrich_metadata['source_type'] = 'manual' if 'volumes/brain' in file_path else 'git'
                
                # Human-Readable Embedding: Extract keywords if missing
                if 'keywords' not in enrich_metadata or not enrich_metadata['keywords']:
                    logger.info(f"Extracting human-readable embedding (keywords) for {title}...")
                    enrich_metadata['keywords'] = extract_semantic_keywords(parsed['content'], title)
                    # Update DB metadata to avoid re-extracting next time
                    db.upsert_note(file_path, title, parsed['content'], enrich_metadata)
                
                # Check if it was already in DB to get original ingested_at
                with db.conn.cursor() as cur:
                    cur.execute("SELECT created_at FROM brain.notes WHERE id = %s", (note_id,))
                    row = cur.fetchone()
                    if row:
                        enrich_metadata['ingested_at'] = row[0].isoformat()
                
                enriched_content = enrich_markdown(parsed['content'], enrich_metadata, parsed['links'])
                
                # Compare with original content to avoid redundant writes
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                # 4. Write back if changed
                if enriched_content.strip() != original_content.strip():
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(enriched_content)
                    logger.info(f"Enriched document with metadata and footer: {title}")
            except Exception as write_e:
                logger.error(f"Failed to enrich {file_path}: {write_e}")

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")


class BrainEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"Detected creation: {event.src_path}")
            process_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            logger.info(f"Detected modification: {event.src_path}")
            process_file(event.src_path)

def start_watching(path):
    event_handler = BrainEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    logger.info(f"Started watching directory: {path}")
    
    # Initial Scan in background thread to avoid blocking lifespan startup
    def initial_scan():
        logger.info("Starting initial brain scan...")
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".md"):
                    try:
                        process_file(os.path.join(root, file))
                    except Exception as e:
                        logger.error(f"Error during initial scan of {file}: {e}")
        logger.info("Initial brain scan completed.")

    threading.Thread(target=initial_scan, daemon=True).start()
    
    return observer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure schema is ready
    try:
        db._init_schema()
    except Exception as e:
        logger.error(f"Failed to initialize schema during lifespan: {e}")
        
    # Initialize CostTracker
    global cost_tracker
    try:
        from cost_tracker import CostTracker
        cost_tracker = CostTracker(db.conn)
        app.state.cost_tracker = cost_tracker
        logger.info("CostTracker initialized for cost monitoring")
    except Exception as e:
        logger.warning(f"CostTracker not available: {e}")
        app.state.cost_tracker = None

    # Startup: Start watcher in background thread
    observer = start_watching(BRAIN_DIR)
    
    # Initialize NoteSyncer
    try:
        from note_sync import NoteSyncer
        app.state.note_syncer = NoteSyncer(db, brain_dir=BRAIN_DIR)
        
        # Start background polling for WebUI notes
        # Wrapper for embedding and keyword extraction
        def embedding_fn(text):
            return get_embedding(text, cost_tracker=getattr(app.state, 'cost_tracker', None))
            
        def keywords_fn(content, title):
            return extract_semantic_keywords(content, title)
            
        app.state.note_syncer.start_polling(embedding_fn, keywords_fn, interval_seconds=60)
        logger.info("NoteSyncer watchdog started for Open WebUI notes")
    except Exception as e:
        logger.warning(f"NoteSyncer not available: {e}")
        app.state.note_syncer = None
    
    yield

    
    # Shutdown: Stop watcher and close connections
    observer.stop()
    observer.join()
    if app.state.note_syncer:
        app.state.note_syncer.close()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}


# ==================== Cost Dashboard Endpoints ====================

@app.get("/cost-dashboard")
async def cost_dashboard():
    """Serve the cost tracking dashboard HTML."""
    import os
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "cost_dashboard.html")
    try:
        with open(dashboard_path, "r") as f:
            html = f.read()
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)
    except FileNotFoundError:
        return JSONResponse({"error": "Dashboard not found"}, status_code=404)


@app.get("/api/costs/summary")
async def costs_summary(request: Request, days: int = 7):
    """Get cost summary for the last N days."""
    if not hasattr(request.app.state, 'cost_tracker') or request.app.state.cost_tracker is None:
        return JSONResponse({"error": "CostTracker not available"}, status_code=503)
    
    try:
        summary = request.app.state.cost_tracker.get_summary(days)
        return JSONResponse(summary)
    except Exception as e:
        logger.error(f"Failed to get cost summary: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/costs/daily")
async def costs_daily(request: Request, days: int = 7):
    """Get daily cost breakdown."""
    if not hasattr(request.app.state, 'cost_tracker') or request.app.state.cost_tracker is None:
        return JSONResponse({"error": "CostTracker not available"}, status_code=503)
    
    try:
        daily = request.app.state.cost_tracker.get_daily_breakdown(days)
        return JSONResponse(daily)
    except Exception as e:
        logger.error(f"Failed to get daily costs: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/costs/requests")
async def costs_requests(request: Request, limit: int = 50):
    """Get recent request logs."""
    if not hasattr(request.app.state, 'cost_tracker') or request.app.state.cost_tracker is None:
        return JSONResponse({"error": "CostTracker not available"}, status_code=503)
    
    try:
        requests_list = request.app.state.cost_tracker.get_recent_requests(limit)
        return JSONResponse(requests_list)
    except Exception as e:
        logger.error(f"Failed to get request logs: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)



@app.get("/api/costs/litellm")
async def costs_litellm(request: Request, days: int = 7):
    """Get actual spend stats from LiteLLM's internal logs."""
    if not hasattr(request.app.state, 'cost_tracker') or request.app.state.cost_tracker is None:
        return JSONResponse({"error": "CostTracker not available"}, status_code=503)
    
    try:
        stats = request.app.state.cost_tracker.get_litellm_stats(days)
        return JSONResponse(stats)
    except Exception as e:
        logger.error(f"Failed to get LiteLLM stats: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/sync-notes")
async def sync_notes(request: Request):
    """
    Manually trigger synchronization of Open WebUI notes to brain KB.
    """
    if not hasattr(request.app.state, 'note_syncer') or request.app.state.note_syncer is None:
        return JSONResponse({"error": "NoteSyncer not available"}, status_code=503)
    
    try:
        syncer = request.app.state.note_syncer
        def embedding_fn(text):
            return get_embedding(text, cost_tracker=cost_tracker)
        def keywords_fn(content, title):
            return extract_semantic_keywords(content, title)
            
        synced_count = syncer.sync_all(embedding_fn, keywords_fn)
        return JSONResponse({
            "status": "success",
            "synced_notes": synced_count
        })
    except Exception as e:
        logger.error(f"Failed to sync notes: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/sync-notes/status")
async def sync_notes_status(request: Request):
    """
    Get the status of the Open WebUI notes syncer.
    """
    if not hasattr(request.app.state, 'note_syncer') or request.app.state.note_syncer is None:
        return JSONResponse({"available": False})
    
    try:
        syncer = request.app.state.note_syncer
        notes = syncer.get_all_notes()
        return JSONResponse({
            "available": True,
            "webui_notes_count": len(notes),
            "last_sync_timestamp": syncer._last_sync_timestamp
        })
    except Exception as e:
        return JSONResponse({"available": False, "error": str(e)})


# ==================== MCP Server Endpoints ====================

@app.get("/mcp/sse")
async def mcp_sse(request: Request):
    """MCP SSE endpoint."""
    async with mcp_instance.sse_handler(request) as handler:
        return handler

@app.post("/mcp/messages")
async def mcp_messages(request: Request):
    """MCP messages endpoint."""
    async with mcp_instance.messages_handler(request) as handler:
        return handler


def build_context_for_query(user_query, *, strategy=SEARCH_STRATEGY, limit=5, cost_tracker=None):
    context_text = ""
    source_mapping = {}
    results = []

    query_vector = get_embedding(user_query, cost_tracker=cost_tracker)
    if query_vector:
        results = db.search(user_query, query_vector, strategy=strategy, limit=limit)
        if results:
            context_parts = []
            for i, row in enumerate(results):
                file_path, title, content, section, similarity = row

                source_num = i + 1
                source_label = f"Source {source_num}"
                section_info = f" > {section}" if section else ""

                source_mapping[source_num] = {
                    "title": title,
                    "file_path": file_path,
                    "section": section,
                    "similarity": similarity,
                }

                header = f"--- {source_label}: {title}{section_info} ({file_path}) ---"
                context_parts.append(f"{header}\n{content}")

            context_text = "\n\n".join(context_parts)
            logger.info(f"Found {len(results)} relevant documents using {strategy} search.")
    else:
        logger.warning("Failed to generate embedding for query, no context will be used.")

    return context_text, source_mapping, results


def build_system_prompt(context_text):
    return (
        "You are a knowledge base assistant with access to a local documentation repository (the 'Brain').\n\n"
        "CRITICAL RULES:\n"
        "1. You MUST ONLY use information from the provided CONTEXT below.\n"
        "2. Do NOT generate, infer, or extrapolate information beyond what is explicitly stated in the CONTEXT.\n"
        "3. If the CONTEXT does not contain the answer, you MUST respond with: 'I cannot find this information in the knowledge base.'\n"
        "4. You MUST cite your sources using [Source N] notation (e.g., [Source 1]) matching the headers in the context.\n"
        "5. Construct your answer by quoting or paraphrasing ONLY from the CONTEXT. Do not add your own knowledge.\n"
        "6. If the question requires information from multiple sources, synthesize them but cite each source used.\n"
        "7. If the CONTEXT is empty or irrelevant, state: 'No relevant information found in the knowledge base.'\n\n"
        f"CONTEXT:\n{context_text if context_text else '[No context available]'}"
    )


@app.post("/v1/context")
async def context_preview(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        return JSONResponse({"error": "query must be a non-empty string"}, status_code=400)
    query = query.strip()

    strategy = body.get("strategy") or SEARCH_STRATEGY
    include_system_prompt = bool(body.get("include_system_prompt", False))

    try:
        limit = int(body.get("limit", 5))
        if limit <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JSONResponse({"error": "limit must be a positive integer"}, status_code=400)

    cost_tracker = getattr(request.app.state, "cost_tracker", None)
    context_text, source_mapping, results = build_context_for_query(
        query,
        strategy=strategy,
        limit=limit,
        cost_tracker=cost_tracker,
    )

    sources = []
    for source_num, info in source_mapping.items():
        sources.append(
            {
                "source_num": source_num,
                "title": info["title"],
                "file_path": info["file_path"],
                "section": info["section"],
                "similarity": info["similarity"],
            }
        )

    response = {
        "query": query,
        "strategy": strategy,
        "limit": limit,
        "context_text": context_text,
        "sources": sources,
    }
    if include_system_prompt:
        response["system_prompt"] = build_system_prompt(context_text)

    return JSONResponse(response)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
        if not messages:
            return JSONResponse({"error": "No messages provided"}, status_code=400)

        # 1. Get user query
        user_query = messages[-1]["content"] or ""
        logger.info(f"RAG Request: {user_query[:50]}...")

        # Check for Open WebUI meta-prompts (title, tags, follow-up suggestions)
        # These internal tasks don't benefit from RAG context
        is_meta_prompt = user_query.strip().startswith("### Task:")
        
        if is_meta_prompt:
            logger.info("Detected meta-prompt, bypassing RAG retrieval...")
            # Forward directly to LLM without context augmentation
            proxy_body = body.copy()
            proxy_body["model"] = REAL_MODEL
            
            # Log the meta-prompt
            log_prompt_to_litellm("meta-prompt", REAL_MODEL, messages, {"stream": body.get("stream", False)})
            
            is_stream = body.get("stream", False)
            if is_stream:
                from fastapi.responses import StreamingResponse
                def generate_stream():
                    try:
                        with requests.post(
                            f"{LITELLM_API_BASE}/chat/completions",
                            json=proxy_body,
                            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                            stream=True,
                            timeout=120
                        ) as r:
                            for line in r.iter_lines():
                                if line:
                                    yield line + b"\n\n"
                    except Exception as e:
                        logger.error(f"Streaming error: {e}")
                        yield f'data: {{"error": "{str(e)}"}}\n\n'.encode('utf-8')
                return StreamingResponse(generate_stream(), media_type="text/event-stream")
            else:
                import time as _time
                start_time = _time.time()
                response = requests.post(
                    f"{LITELLM_API_BASE}/chat/completions",
                    json=proxy_body,
                    headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                    timeout=60
                )
                latency_ms = int((_time.time() - start_time) * 1000)
                
                # Log cost for meta-prompt
                try:
                    resp_json = response.json()
                    usage = resp_json.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
                    
                    if hasattr(request.app.state, 'cost_tracker') and request.app.state.cost_tracker:
                        request.app.state.cost_tracker.log_request(
                            operation="meta-prompt",
                            model=REAL_MODEL,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            latency_ms=latency_ms
                        )
                except Exception as log_e:
                    logger.warning(f"Failed to log meta-prompt cost: {log_e}")
                    
                return JSONResponse(status_code=response.status_code, content=resp_json)

        # 2. Semantic Search (only for real user queries)
        cost_tracker = getattr(request.app.state, 'cost_tracker', None)
        context_text, source_mapping, results = build_context_for_query(
            user_query,
            strategy=SEARCH_STRATEGY,
            limit=5,
            cost_tracker=cost_tracker,
        )

        # 3. Augment Prompt with STRICT grounding instructions
        system_prompt = build_system_prompt(context_text)

        # Insert or update system message
        new_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            if msg["role"] != "system":
                new_messages.append(msg)

        # 4. Proxy to real model
        proxy_body = body.copy()
        proxy_body["messages"] = new_messages
        proxy_body["model"] = REAL_MODEL
        
        is_stream = body.get("stream", False)
        
        # Log the RAG-augmented prompt
        log_prompt_to_litellm("rag-chat", REAL_MODEL, new_messages, {
            "stream": is_stream,
            "context_sources": len(source_mapping),
            "search_strategy": SEARCH_STRATEGY
        })
        
        logger.info(f"Forwarding RAG request to LiteLLM for model: {REAL_MODEL} (Stream: {is_stream})")
        
        if is_stream:
            from fastapi.responses import StreamingResponse
            
            def generate_stream():
                try:
                    with requests.post(
                        f"{LITELLM_API_BASE}/chat/completions",
                        json=proxy_body,
                        headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                        stream=True,
                        timeout=120  # Longer timeout for OpenAI
                    ) as r:
                        if r.status_code != 200:
                            logger.error(f"LiteLLM Stream Error: {r.status_code} - {r.text}")
                            yield f'data: {{"error": "LiteLLM status {r.status_code}"}}\n\n'.encode('utf-8')
                            return

                        for line in r.iter_lines():
                            if line:
                                # Ensure proper SSE format: each event ends with double newline
                                yield line + b"\n\n"
                except Exception as stream_e:
                    logger.error(f"Streaming error: {stream_e}")
                    yield f'data: {{"error": "{str(stream_e)}"}}\n\n'.encode('utf-8')

            return StreamingResponse(generate_stream(), media_type="text/event-stream")
        else:
            # Non-streaming
            import time as _time
            start_time = _time.time()
            try:
                response = requests.post(
                    f"{LITELLM_API_BASE}/chat/completions",
                    json=proxy_body,
                    headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                    timeout=60
                )
                latency_ms = int((_time.time() - start_time) * 1000)
                logger.info(f"LiteLLM Response Status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"LiteLLM Error Body: {response.text}")
                    return JSONResponse(status_code=response.status_code, content=response.json())
                
                # Log cost and post-process response
                try:
                    resp_json = response.json()
                    usage = resp_json.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
                    
                    if hasattr(request.app.state, 'cost_tracker') and request.app.state.cost_tracker:
                        request.app.state.cost_tracker.log_request(
                            operation="chat",
                            model=REAL_MODEL,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            latency_ms=latency_ms
                        )
                    
                    # Post-process: Replace [Source N] with clickable links
                    if source_mapping and 'choices' in resp_json:
                        for choice in resp_json['choices']:
                            if 'message' in choice and 'content' in choice['message']:
                                original_content = choice['message']['content']
                                processed_content = original_content
                                
                                # Replace [Source N] with [filename.md](file_path)
                                for source_num, info in source_mapping.items():
                                    pattern = f"\\[Source {source_num}\\]"
                                    file_path = info['file_path']
                                    # Extract filename from path
                                    filename = file_path.split('/')[-1] if '/' in file_path else file_path
                                    # Create clickable markdown link with filename
                                    replacement = f"[{filename}]({file_path})"
                                    processed_content = re.sub(pattern, replacement, processed_content)
                                
                                choice['message']['content'] = processed_content
                                
                except Exception as log_e:
                    logger.warning(f"Failed to log cost or post-process: {log_e}")
                
                return JSONResponse(status_code=response.status_code, content=resp_json)
            except requests.exceptions.Timeout:
                logger.error("LiteLLM request timed out")
                return JSONResponse({"error": "LiteLLM request timed out"}, status_code=504)
            except Exception as e:
                logger.error(f"Error forwarding to LiteLLM: {e}")
                return JSONResponse({"error": str(e)}, status_code=500)

    except Exception as e:
        logger.error(f"Error in chat_completions: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
