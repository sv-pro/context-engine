import time
import os
import logging
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from db import Database
from parser import parse_markdown

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
BRAIN_DIR = os.environ.get("BRAIN_DIR", "/app/brain")
OLLAMA_API_BASE = os.environ.get("OLLAMA_API_BASE", "http://host.docker.internal:11434")
EMBEDDING_MODEL = "nomic-embed-text:latest" # or whatever is available

db = Database()

def get_embedding(text):
    """
    Generates embedding using Ollama API directly (simpler than reaching LiteLLM for now)
    """
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
    """
    Reads, parses, and ingests a file into the DB.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse
        parsed = parse_markdown(content)
        title = parsed['metadata'].get('title', os.path.basename(file_path).replace('.md', ''))
        
        # Ingest Note
        note_id = db.upsert_note(
            file_path=file_path,
            title=title,
            content=parsed['content'],
            metadata=parsed['metadata']
        )
        logger.info(f"Upserted note: {title} (ID: {note_id})")

        # Ingest Links
        if parsed['links']:
            db.update_links(note_id, parsed['links'])
            logger.info(f"Updated {len(parsed['links'])} links for {title}")

        # Generate & Update Embedding
        # Only embed if content is successfully parsed
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
            
    # TODO: Handle deletions (remove from DB)

def start_watching(path):
    event_handler = BrainEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    logger.info(f"Started watching directory: {path}")
    
    # Intitial Scan
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".md"):
                process_file(os.path.join(root, file))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    # Ensure directory exists
    if not os.path.exists(BRAIN_DIR):
        logger.warning(f"Brain directory {BRAIN_DIR} does not exist. Creating it.")
        os.makedirs(BRAIN_DIR)

    start_watching(BRAIN_DIR)

