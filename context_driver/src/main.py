import time
import os
import logging
import requests
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from db import Database
from parser import parse_markdown

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("context-driver")

# Configuration
BRAIN_DIR = os.environ.get("BRAIN_DIR", "/app/brain")
OLLAMA_API_BASE = os.environ.get("OLLAMA_API_BASE", "http://host.docker.internal:11434")
LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE", "http://litellm:4000/v1")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-1234-5678-admin")
EMBEDDING_MODEL = "mxbai-embed-large:latest"
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
        url = f"{OLLAMA_API_BASE}/api/embeddings"
        response = requests.post(url, json={
            "model": EMBEDDING_MODEL,
            "prompt": text
        })
        response.raise_for_status()
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log cost if tracker available
        if cost_tracker:
            from cost_tracker import estimate_tokens
            input_tokens = estimate_tokens(text)
            cost_tracker.log_request(
                operation="embedding",
                model=EMBEDDING_MODEL,
                input_tokens=input_tokens,
                output_tokens=0,
                latency_ms=latency_ms
            )
        
        return response.json()["embedding"]
    except Exception as e:
        logger.error(f"Failed to get embedding: {e}")
        return None

def process_file(file_path):
    try:
        if not os.path.exists(file_path):
            return
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parsed = parse_markdown(content)
        title = parsed['metadata'].get('title', os.path.basename(file_path).replace('.md', ''))
        
        note_id = db.upsert_note(
            file_path=file_path,
            title=title,
            content=parsed['content'],
            metadata=parsed['metadata']
        )
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
            vector = get_embedding(parsed['content'], cost_tracker=cost_tracker)
            if vector:
                db.update_embedding(note_id, vector)
                logger.info(f"Updated note-level embedding for {title}")

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
        app.state.note_syncer = NoteSyncer(db)
        
        # Start background polling for WebUI notes
        # We define a simple wrapper for get_embedding that uses the current cost_tracker
        def embedding_fn(text):
            return get_embedding(text, cost_tracker=getattr(app.state, 'cost_tracker', None))
            
        app.state.note_syncer.start_polling(embedding_fn, interval_seconds=60)
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
        synced_count = syncer.sync_all(lambda x: get_embedding(x, cost_tracker=cost_tracker))
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
        context_text = ""
        cost_tracker = getattr(request.app.state, 'cost_tracker', None)
        cost_tracker = getattr(request.app.state, 'cost_tracker', None)
        query_vector = get_embedding(user_query, cost_tracker=cost_tracker)
        if query_vector:
            # Use the unified search router with the configured strategy
            # Strategies: 'super_hybrid', 'hybrid', 'graph', 'keyword', 'semantic'
            results = db.search(user_query, query_vector, strategy=SEARCH_STRATEGY, limit=5)
            if results:
                context_parts = []
                for i, row in enumerate(results):
                    # Unpack result structure: (file_path, title, content, section, similarity)
                    file_path, title, content, section, similarity = row
                    
                    source_label = f"Source {i+1}"
                    section_info = f" > {section}" if section else ""
                    
                    header = f"--- {source_label}: {title}{section_info} ({file_path}) ---"
                    context_parts.append(f"{header}\n{content}")
                    
                context_text = "\n\n".join(context_parts)
                logger.info(f"Found {len(results)} relevant documents using {SEARCH_STRATEGY} search.")
        else:
            logger.warning("Failed to generate embedding for query, no context will be used.")

        # 3. Augment Prompt with strict citation instructions
        system_prompt = (
            "You are a helpful assistant with access to a local knowledge base (the 'Brain').\n\n"
            "INSTRUCTIONS:\n"
            "1. Use the provided CONTEXT to answer the user's question.\n"
            "2. You MUST cite your sources using [Source N] notation (e.g., [Source 1]) matching the headers in the context.\n"
            "3. If the context contains the answer, stick to it and mention the source.\n"
            "4. If the context does not contain the answer, state that clearly and then provide a general answer if possible.\n"
            "5. Maintain a professional and helpful tone.\n\n"
            f"CONTEXT:\n{context_text}"
        )

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
                
                # Log cost
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
                except Exception as log_e:
                    logger.warning(f"Failed to log cost: {log_e}")
                
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

