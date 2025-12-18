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
EMBEDDING_MODEL = "nomic-embed-text:latest"

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

def get_embedding(text):
    try:
        url = f"{OLLAMA_API_BASE}/api/embeddings"
        response = requests.post(url, json={
            "model": EMBEDDING_MODEL,
            "prompt": text
        })
        response.raise_for_status()
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

        if parsed['content']:
            vector = get_embedding(parsed['content'])
            if vector:
                db.update_embedding(note_id, vector)
                logger.info(f"Updated embedding for {title}")

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
    
    # Initial Scan
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".md"):
                process_file(os.path.join(root, file))
    
    return observer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure schema is ready
    try:
        db._init_schema()
    except Exception as e:
        logger.error(f"Failed to initialize schema during lifespan: {e}")
        
    # Startup: Start watcher in background thread
    observer = start_watching(BRAIN_DIR)
    yield
    # Shutdown: Stop watcher
    observer.stop()
    observer.join()

app = FastAPI(lifespan=lifespan)

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
                response = requests.post(
                    f"{LITELLM_API_BASE}/chat/completions",
                    json=proxy_body,
                    headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                    timeout=60
                )
                return JSONResponse(status_code=response.status_code, content=response.json())

        # 2. Semantic Search (only for real user queries)
        context_text = ""
        query_vector = get_embedding(user_query)
        if query_vector:
            results = db.semantic_search(query_vector, limit=3)
            if results:
                context_parts = []
                for title, content, _, similarity in results:
                    context_parts.append(f"--- Document: {title} (Similarity: {similarity:.4f}) ---\n{content}")
                context_text = "\n\n".join(context_parts)
                logger.info(f"Found {len(results)} relevant documents for context.")
                # Debug: Log the actual context being used
                logger.debug(f"Context preview: {context_text[:500]}...")
        else:
            logger.warning("Failed to generate embedding for query, no context will be used.")

        # 3. Augment Prompt
        system_prompt = (
            "You are a helpful assistant with access to a local knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context doesn't contain the answer, tell the user, but still try to help with your general knowledge. "
            "Always mention that you are using information from the knowledge base if you do so.\n\n"
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
            try:
                response = requests.post(
                    f"{LITELLM_API_BASE}/chat/completions",
                    json=proxy_body,
                    headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                    timeout=60
                )
                logger.info(f"LiteLLM Response Status: {response.status_code}")
                if response.status_code != 200:
                    logger.error(f"LiteLLM Error Body: {response.text}")
                    return JSONResponse(status_code=response.status_code, content=response.json())
                
                return JSONResponse(status_code=response.status_code, content=response.json())
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

