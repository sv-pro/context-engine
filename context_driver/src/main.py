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
# Configuration
RAW_DIR = os.environ.get("RAW_DIR", "/app/raw")
BRAIN_DIR = os.environ.get("BRAIN_DIR", "/app/brain")
# Subdirectories for the Graph
DOCS_DIR = os.path.join(BRAIN_DIR, "documents")
ENTITIES_DIR = os.path.join(BRAIN_DIR, "entities")

# Ensure directories exist
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(ENTITIES_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

# ==================== .brainignore Support ====================

def load_brainignore(directory: str) -> set:
    """
    Load a .brainignore file from a directory.
    Returns a set of directory patterns to ignore (relative to that directory).
    
    .brainignore format (similar to .gitignore but simpler):
    - One pattern per line
    - Lines starting with # are comments
    - Patterns are relative paths to subdirectories to exclude
    - Leading/trailing slashes are normalized
    
    Example .brainignore:
        # Ignore these sub-brains (they're indexed separately)
        projects/myapp
        modes/debug
    """
    ignore_file = os.path.join(directory, '.brainignore')
    ignored = set()
    
    if not os.path.exists(ignore_file):
        return ignored
    
    try:
        with open(ignore_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                # Normalize: remove leading/trailing slashes
                pattern = line.strip('/').strip('\\')
                if pattern:
                    ignored.add(pattern)
        
        if ignored:
            logger.info(f"Loaded .brainignore from {directory}: {ignored}")
    except Exception as e:
        logger.warning(f"Failed to load .brainignore from {directory}: {e}")
    
    return ignored


def is_path_ignored(file_path: str, base_dir: str, ignored_patterns: set) -> bool:
    """
    Check if a file path should be ignored based on .brainignore patterns.
    
    Args:
        file_path: Absolute path to the file
        base_dir: Base directory where .brainignore was loaded from
        ignored_patterns: Set of patterns from .brainignore
    
    Returns:
        True if the path should be ignored, False otherwise
    """
    if not ignored_patterns:
        return False
    
    # Get relative path from base_dir
    try:
        rel_path = os.path.relpath(file_path, base_dir)
    except ValueError:
        return False  # On Windows, paths on different drives can cause this
    
    # Check if any ignored pattern is a prefix of the relative path
    for pattern in ignored_patterns:
        # Check if the file is under the ignored directory
        if rel_path == pattern or rel_path.startswith(pattern + os.sep):
            return True
    
    return False


def walk_with_brainignore(base_dir: str):
    """
    Walk a directory tree like os.walk, but respecting .brainignore files.
    
    Yields (root, dirs, files) tuples just like os.walk, but:
    - Loads .brainignore from base_dir
    - Excludes directories matching patterns in .brainignore
    - Also loads nested .brainignore files and respects them
    
    Args:
        base_dir: The base directory to walk
    
    Yields:
        Tuples of (root, dirs, files) like os.walk
    """
    # Load top-level .brainignore
    global_ignored = load_brainignore(base_dir)
    
    for root, dirs, files in os.walk(base_dir):
        # Check for local .brainignore in current directory
        local_ignored = load_brainignore(root) if root != base_dir else set()
        
        # Filter out ignored directories
        # We need to modify dirs in-place to prevent os.walk from descending
        dirs_to_remove = []
        for d in dirs:
            dir_path = os.path.join(root, d)
            
            # Check against global patterns (relative to base_dir)
            if is_path_ignored(dir_path, base_dir, global_ignored):
                dirs_to_remove.append(d)
                logger.debug(f"Ignoring directory (global .brainignore): {dir_path}")
                continue
            
            # Check against local patterns (relative to current root)
            if d in local_ignored or d.rstrip('/') in local_ignored:
                dirs_to_remove.append(d)
                logger.debug(f"Ignoring directory (local .brainignore): {dir_path}")
        
        for d in dirs_to_remove:
            dirs.remove(d)
        
        yield root, dirs, files

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

            # Legacy links handling removed/deferred to update_edges below
            # if parsed['links']:
            #    db.update_links(note_id, parsed['links'])


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
                    if title.startswith("CDDOS-"):
                         logger.info(f"Skipping keyword extraction for Jira: {title}")
                         keywords = ["Jira", "Issue", title]
                    else:
                        from prompts import extract_keywords
                        keywords = extract_keywords(parsed['content'], title)

                    if keywords:
                        parsed['metadata']['keywords'] = keywords
                        db.upsert_note(file_path, title, parsed['content'], parsed['metadata'])
                        logger.info(f"Extracted and updated keywords for {title}: {keywords}")


                
                # 3. Truncate and Embed
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
            logger.debug(f"Db Note {title} unchanged, skipping re-embedding.")

        # 4. Handle Edges (Graph Data)
        # If 'graph_data' is in metadata (from Raw Ingestion), strictly use it to build edges
        if 'graph_data' in parsed['metadata']:
            graph_data = parsed['metadata']['graph_data']
            if 'relationships' in graph_data:
                db.update_edges(note_id, graph_data['relationships'])
                logger.info(f"Updated structured edges for {title}")
        
        # Fallback: if no graph_data but 'links' exist (WebUI or legacy), use those as basic wikilinks
        elif parsed['links']:
             # Convert simple links to edges format
             edges = [{'target': link, 'type': 'wikilink'} for link in parsed['links']]
             db.update_edges(note_id, edges)

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

# ==================== PIPELINE STAGE 1: RAW INGESTION (Source -> Graph) ====================

def ingest_raw_file(file_path):
    """
    Reads a RAW file, extracts Graph Elements, and writes Enriched artifacts to BRAIN_DIR.
    """
    try:
        if not os.path.exists(file_path):
            return
            
        logger.info(f"Ingesting RAW file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        filename = os.path.basename(file_path)
        title = filename.replace('.md', '')
        
        # 1. Extract Graph Elements
        # Optimization: Skip expensive LLM graph extraction for Jira tickets (CDDOS-*)
        if title.startswith("CDDOS-"):
            graph_data = {"entities": [], "relationships": []}
            logger.info(f"Skipping graph extraction for Jira ticket: {title}")
        else:
            from prompts import extract_graph_elements
            graph_data = extract_graph_elements(content, title)
        
        # 2. Generate/Update Entity Nodes
        entities = graph_data.get('entities', [])
        for entity in entities:
            name = entity.get('name')
            if not name: continue
            
            # Sanitized filename for entity
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
            entity_path = os.path.join(ENTITIES_DIR, f"{safe_name}.md")
            
            # Find relationships involving this entity
            entity_rels = []
            for r in graph_data.get('relationships', []):
                if r.get('source') == name:
                    entity_rels.append(f"- **{r.get('type')}** -> [[{r.get('target')}]]")
                elif r.get('target') == name:
                    entity_rels.append(f"- **{r.get('type')}** (from [[{r.get('source')}]])")
            
            rels_text = "\n".join(entity_rels) if entity_rels else "No specific relationships extracted."

            # Merge with existing if exists
            existing_rels = set()
            existing_content_top = f"---\ntype: {entity.get('type', 'Concept')}\ngenerated_from: \"{title}\"\n---\n# {name}\n\n{entity.get('description', 'No description available.')}\n"
            
            if os.path.exists(entity_path):
                with open(entity_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
                
                # Simple parsing of existing relationships
                if "## Relationships" in old_content:
                    parts = old_content.split("## Relationships")
                    # Use the old description/header if preferred? 
                    # For now, let's keep the NEW description as it might be fresher or from a focused doc?
                    # actually, let's keep the Longest description? Or just append?
                    # Let's simple merge relationships.
                    
                    rel_lines = parts[1].strip().split('\n')
                    for line in rel_lines:
                        if line.strip().startswith('-'):
                            existing_rels.add(line.strip())
            
            # Add new rels
            for r in entity_rels:
                existing_rels.add(r)
            
            # Sort for stability
            final_rels_text = "\n".join(sorted(list(existing_rels)))
            
            entity_content = f"""{existing_content_top}
## Relationships
{final_rels_text}
"""
            with open(entity_path, 'w', encoding='utf-8') as f:
                f.write(entity_content)
                
        # 3. Generate Enriched Document Node
        # Inject wikilinks? For now, we just attach the metadata.
        # Future: Regex replace entity names with [[Name]]
        
        # Prepare Metadata
        from enricher import generate_frontmatter
        
        # We need to parse existing frontmatter to preserve user metadata from raw!
        parsed_raw = parse_markdown(content)
        metadata = parsed_raw['metadata']
        
        # Inject graph data
        metadata['graph_data'] = graph_data
        metadata['source_path'] = file_path
        
        # Reconstruct content with new frontmatter
        # We strip original frontmatter and prepend new
        new_frontmatter = generate_frontmatter(metadata)
        
        final_content = f"{new_frontmatter}\n\n{parsed_raw['content']}"
        
        doc_path = os.path.join(DOCS_DIR, filename)
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        logger.info(f"Generated Graph artifacts for {title}: {len(entities)} entities.")
        
        # 4. NEUROSYMBOLIC DISTILLATION (3-pass pipeline)
        # Run after graph extraction to store capsules, facts, and rules
        try:
            neurosymbolic_distill(content, title, file_path)
        except Exception as e:
            logger.error(f"Neurosymbolic distillation failed for {title}: {e}")

    except Exception as e:
        logger.error(f"Error ingesting raw file {file_path}: {e}")


def neurosymbolic_distill(content: str, title: str, source_path: str):
    """
    3-pass neurosymbolic knowledge distillation pipeline.
    
    Uses DSPy for structured, predictable extraction with litellm fallback.
    Pass #1: CONDENSE -> capsule
    Pass #2: STRUCTURE -> facts
    Pass #3: DISTILL RULES -> rules
    """
    logger.info(f"[NEURO] Starting 3-pass distillation for: {title}")
    
    # Find the note_id for this source
    with db.conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM brain.notes WHERE title ILIKE %s OR file_path ILIKE %s LIMIT 1
        """, (title, f"%{title}%"))
        row = cur.fetchone()
        if not row:
            logger.warning(f"[NEURO] Note not found for {title}, skipping distillation")
            return
        note_id = row[0]
    
    provenance = f"{os.path.basename(source_path)}"
    
    # Try DSPy pipeline first
    try:
        from dspy_signatures import run_dspy_pipeline
        
        result = run_dspy_pipeline(title=title, content=content)
        
        capsule = result.get("capsule", {})
        facts_list = result.get("facts", [])
        rules_list = result.get("rules", [])
        
        logger.info(f"[NEURO/DSPy] Pipeline completed for {title}")
        
    except Exception as e:
        logger.warning(f"[NEURO] DSPy pipeline failed, falling back to litellm: {e}")
        
        # Fallback to litellm prompts
        from prompts import condense_document, extract_facts, distill_rules
        
        capsule = condense_document(content, title)
        
        facts_data = extract_facts(content, title, capsule)
        facts_list = facts_data.get("facts", [])
        
        rules_data = distill_rules(content, title, capsule, facts_list)
        rules_list = rules_data.get("rules", [])
    
    # Store results
    db.upsert_capsule(
        source_id=note_id,
        summary=capsule.get("summary", ""),
        key_points=capsule.get("key_points", []),
        intent=capsule.get("intent", "unknown"),
        domain=capsule.get("domain", "unknown"),
        confidence=capsule.get("confidence", 0.0)
    )
    
    db.upsert_facts(source_id=note_id, facts=facts_list, provenance=provenance)
    db.upsert_rules(source_id=note_id, rules=rules_list, provenance=provenance)
    
    logger.info(f"[NEURO] Completed distillation for {title}: {len(facts_list)} facts, {len(rules_list)} rules")


# ==================== PIPELINE STAGE 2: INDEXING (Graph -> DB) ====================

def index_processed_file(file_path):
    """
    Reads a file from BRAIN_DIR (Document or Entity) and indexes it to the DB.
    Refactored from old process_file.
    """
    # This is effectively the old process_file, but logic is slightly adjusted 
    # to handle the pre-enriched files.
    # We rename 'process_file' to this name in the watcher.
    process_file(file_path) # Call the existing function for now (it works on files with frontmatter)


class RawEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._ignored = load_brainignore(RAW_DIR)
    
    def _should_process(self, path):
        if not path.endswith('.md'):
            return False
        if is_path_ignored(path, RAW_DIR, self._ignored):
            logger.debug(f"Ignoring file (brainignore): {path}")
            return False
        return True
    
    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            ingest_raw_file(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            ingest_raw_file(event.src_path)


class BrainEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._ignored = load_brainignore(BRAIN_DIR)
    
    def _should_process(self, path):
        if not path.endswith('.md'):
            return False
        if is_path_ignored(path, BRAIN_DIR, self._ignored):
            logger.debug(f"Ignoring file (brainignore): {path}")
            return False
        return True
    
    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            logger.info(f"Indexing new graph node: {event.src_path}")
            index_processed_file(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            logger.info(f"Re-indexing graph node: {event.src_path}")
            index_processed_file(event.src_path)

def start_watchers():
    # 1. Watch RAW (Ingestion)
    raw_handler = RawEventHandler()
    raw_observer = Observer()
    raw_observer.schedule(raw_handler, RAW_DIR, recursive=True)
    raw_observer.start()
    logger.info(f"Started watching RAW Source: {RAW_DIR}")
    
    # 2. Watch BRAIN (Indexing)
    brain_handler = BrainEventHandler()
    brain_observer = Observer()
    brain_observer.schedule(brain_handler, BRAIN_DIR, recursive=True)
    brain_observer.start()
    logger.info(f"Started watching GRAPH (Brain): {BRAIN_DIR}")
    
    # Initial Scan RAW (uses walk_with_brainignore to respect .brainignore)
    def initial_scan_raw():
        logger.info("Scanning RAW source (respecting .brainignore)...")
        for root, dirs, files in walk_with_brainignore(RAW_DIR):
            for file in files:
                if file.endswith(".md"):
                    ingest_raw_file(os.path.join(root, file))
        logger.info("Raw scan complete.")

    # Initial Scan BRAIN (Indexing) - uses walk_with_brainignore to respect .brainignore
    def initial_scan_brain():
        logger.info("Scanning GRAPH for index (respecting .brainignore)...")
        for root, dirs, files in walk_with_brainignore(BRAIN_DIR):
            for file in files:
                if file.endswith(".md"):
                    try:
                        index_processed_file(os.path.join(root, file))
                    except Exception as e:
                        logger.error(f"Error indexing {file}: {e}")
        logger.info("Graph index scan complete.")

    threading.Thread(target=initial_scan_raw, daemon=True).start()
    # We delay brain scan slightly to avoid race if raw scan is rewriting? 
    # Actually, raw scan writes files, which triggers brain watcher. 
    # So we strictly only need to scan BRAIN if we assume raw is static but we lost DB.
    # Let's run both.
    threading.Thread(target=initial_scan_brain, daemon=True).start()
    
    return [raw_observer, brain_observer]

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

    # Startup: Start watchers
    observers = start_watchers()
    
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
    # Shutdown: Stop watchers
    for o in observers:
        o.stop()
        o.join()
    if app.state.note_syncer:
        app.state.note_syncer.close()

# Get the external URL for OpenAPI servers spec (needed for Open WebUI)
EXTERNAL_URL = os.environ.get("EXTERNAL_URL", "")

app = FastAPI(
    lifespan=lifespan,
    title="Context Driver - Brain RAG API",
    description="RAG-enhanced chat and knowledge base tools for AI assistants",
    version="1.0.0",
    servers=[{"url": EXTERNAL_URL}] if EXTERNAL_URL else None
)

# Enable CORS for Open WebUI integration
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Open WebUI domain
    # Important: browsers will block responses if credentials are allowed with wildcard origin.
    # Open WebUI tool-server discovery doesn't need cookies, so keep this disabled.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the tools API router for Open WebUI integration
from tools_api import router as tools_router
app.include_router(tools_router)

# Include the ColBERTv2-compatible API router for DSPy integration
from colbert_api import router as colbert_router
app.include_router(colbert_router)


@app.get("/")
async def root():
    """API root - provides basic info and links to OpenAPI spec."""
    return {
        "name": "Context Driver - Brain RAG API",
        "version": "1.0.0",
        "description": "RAG-enhanced knowledge base tools for AI assistants",
        "openapi_spec": "/openapi.json",
        "docs": "/docs",
        "health": "/health",
        "tools": {
            "search": "/tools/search",
            "articles": "/tools/articles",
            "article": "/tools/article/{title}",
            "related": "/tools/related/{title}"
        }
    }

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


def classify_query(query: str) -> str:
    """
    Classifies the query to determine the best retrieval strategy.
    Returns: 'semantic', 'graph', or 'super_hybrid'
    """
    try:
        from litellm import completion
        
        prompt = f"""
You are an expert Query Classifier for a RAG system.
Your task is to analyze the user's query and select the optimal retrieval strategy.

Strategies:
1. **semantic**: Best for simple fact lookups, definition questions, or finding specific error messages. High precision, low noise.
   - Examples: "How do I configure X?", "What is error 500?", "define caching"
2. **graph**: Best for multi-hop reasoning, implicit dependencies, finding connections between distinct entities, or aggregation tasks.
   - Examples: "Who manages the team that manages Project X?", "What is the common dependency of A and B?", "List all members of the board."
3. **super_hybrid**: Best for complex questions that might need both exact facts and broader context, or when you are unsure.
   - Examples: "Why is the system slow and showing geo-blocking errors?", "Explain the relationship between X and Y and how to fix Z."

Query: "{query}"

Output ONLY the strategy name: 'semantic', 'graph', or 'super_hybrid'.
"""
        response = completion(
            model=REAL_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        strategy = response.choices[0].message.content.strip().lower()
        
        # Fallback for dirty output
        if "graph" in strategy: return "graph"
        if "hybrid" in strategy: return "super_hybrid"
        if "semantic" in strategy: return "semantic"
        
        return "super_hybrid" # Default safe
        
    except Exception as e:
        logger.error(f"Query classification failed: {e}")
        return "super_hybrid"

def retrieve_context_docs(user_query, *, strategy=SEARCH_STRATEGY, limit=5, cost_tracker=None):
    """
    Retrieves context documents based on the selected strategy.
    Supported strategies: 'semantic', 'keyword', 'graph', 'hybrid', 'super_hybrid', 'adaptive'
    Returns a list of tuples: (file_path, title, content, type, score)
    """
    
    # Adaptive Selection
    if strategy == "adaptive":
        actual_strategy = classify_query(user_query)
        logger.info(f"Adaptive Strategy selected: {actual_strategy} for query: '{user_query}'")
        # Recursively call with the chosen strategy
        return retrieve_context_docs(user_query, strategy=actual_strategy, limit=limit, cost_tracker=cost_tracker)
        
    # Standard Strategies
    if strategy == "semantic":
        query_vector = get_embedding(user_query, cost_tracker=cost_tracker)
        if not query_vector: return []
        results = db.search(user_query, query_vector, strategy="semantic", limit=limit)
        # Adapt format to 5-tuple
        return [(r[0], r[1], r[2], "semantic", r[3]) for r in results]

    elif strategy == "keyword":
        query_vector = get_embedding(user_query, cost_tracker=cost_tracker) # Vector needed for signature even if unused by pure keyword? 
        # Actually db.search handles keyword only if vector is None? No, db.search requires vector usually.
        # Let's rely on db.search('keyword') logic
        if not query_vector: query_vector = [0.0]*1024 # Dummy
        results = db.search(user_query, query_vector, strategy="keyword", limit=limit)
        return [(r[0], r[1], r[2], "keyword", r[3]) for r in results]
        
    elif strategy == "hybrid":
         query_vector = get_embedding(user_query, cost_tracker=cost_tracker)
         if not query_vector: return []
         results = db.search(user_query, query_vector, strategy="hybrid", limit=limit)
         return [(r[0], r[1], r[2], "hybrid", r[3]) for r in results]

    elif strategy == "graph":
        # Pure graph traversal
        return run_iterative_graph_retrieval(user_query, limit=limit, use_semantic_seed=False, cost_tracker=cost_tracker)

    elif strategy == "super_hybrid":
        # Graph + Semantic
        return run_iterative_graph_retrieval(user_query, limit=limit, use_semantic_seed=True, cost_tracker=cost_tracker)

    else:
        logger.warning(f"Unknown strategy {strategy}, defaulting to super_hybrid")
        return retrieve_context_docs(user_query, strategy="super_hybrid", limit=limit, cost_tracker=cost_tracker)

def extract_query_edge_types(query: str) -> list:
    """
    Uses LLM to extract likely relationship types from a query.
    Returns a list of relationship type keywords (e.g., ['designed', 'created', 'built']).
    """
    try:
        from litellm import completion
        
        prompt = f"""
You are an expert at understanding relationship semantics in knowledge graphs.

Given this user query, extract 2-5 relationship types that would be most relevant for traversing a knowledge graph to find the answer.

Query: "{query}"

Examples of relationship types: located_in, commanded_by, designed_by, works_for, part_of, contains, founded, mentored, developed, uses, sourced_from, manufactured_by

Output ONLY a comma-separated list of relationship types (lowercase, use underscores). No explanation.
"""
        response = completion(
            model=REAL_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content.strip().lower()
        # Parse comma-separated list
        edge_types = [t.strip() for t in result.split(",") if t.strip()]
        logger.info(f"Query edge types extracted: {edge_types}")
        return edge_types
        
    except Exception as e:
        logger.error(f"Edge type extraction failed: {e}")
        return []

def run_iterative_graph_retrieval(user_query, limit=5, use_semantic_seed=True, cost_tracker=None):
    """
    Retrieves relevant documents using iterative graph traversal with typed relationships.
    Returns a list of tuples: (file_path, title, content, type, score)
    
    Parses relationship format: `- **relation_type** (from [[Target]])`
    Uses query-aware edge filtering to prioritize relevant edges.
    """
    MAX_ROUNDS = 5
    seen_files = set()
    all_results = []
    
    # Regex for typed relationships: `- **relation_type** (from [[Target]])`
    TYPED_REL_PATTERN = re.compile(r'-\s*\*\*(\w+)\*\*\s*\((?:from|to)\s*\[\[(.*?)\]\]\)')
    SIMPLE_LINK_PATTERN = re.compile(r'\[\[(.*?)\]\]')
    
    # Extract query-relevant edge types for filtering
    query_edge_types = extract_query_edge_types(user_query)
    
    # 1. Initial Seed (Vector Search)
    query_vector = get_embedding(user_query, cost_tracker=cost_tracker)
    if not query_vector:
        return []

    seed_results = db.search(user_query, query_vector, strategy="hybrid", limit=limit)
    current_results = [(r[0], r[1], r[2], "Seed", r[3]) for r in seed_results]
    
    round_idx = 1
    while round_idx <= MAX_ROUNDS and current_results:
        # Dict: target_entity -> list of (relation_type, source_entity, priority)
        typed_links = {}
        next_round_results = []
        
        logger.info(f"Round {round_idx}: Processing {len(current_results)} documents")
        
        for res in current_results:
            fpath, title, content, _, score = res
            
            if fpath not in seen_files:
                seen_files.add(fpath)
                all_results.append(res)
                
                # 1. Extract TYPED relationships
                typed_matches = TYPED_REL_PATTERN.findall(content)
                for rel_type, target in typed_matches:
                    if target not in typed_links:
                        typed_links[target] = []
                    
                    # Calculate priority: higher if rel_type matches query edge types
                    priority = 2 if any(qet in rel_type.lower() for qet in query_edge_types) else 1
                    typed_links[target].append((rel_type, title, priority))
                    
                    if priority == 2:
                        logger.info(f"HIGH PRIORITY edge: {title} --[{rel_type}]--> {target}")
                
                # 2. Extract simple [[WikiLinks]] as fallback
                simple_links = SIMPLE_LINK_PATTERN.findall(content)
                for link in simple_links:
                    if link not in typed_links:
                        typed_links[link] = []
                    if not any(src == title for _, src, _ in typed_links[link]):
                        typed_links[link].append(("links_to", title, 0))  # Lowest priority
        
        if not typed_links:
            break
        
        # Sort targets by max priority of their edges (higher priority first)
        sorted_targets = sorted(
            typed_links.keys(),
            key=lambda t: max((p for _, _, p in typed_links[t]), default=0),
            reverse=True
        )
        
        logger.info(f"Round {round_idx}: Found {len(typed_links)} entities (sorted by edge relevance)")
        
        # Fetch linked documents (prioritized)
        for target_entity in sorted_targets:
            edges = typed_links[target_entity]
            sanitized_title = re.sub(r'[^a-zA-Z0-9_-]', '_', target_entity)
            
            with db.conn.cursor() as cur:
                cur.execute(
                    "SELECT file_path, title, content, metadata FROM brain.notes WHERE title ILIKE %s OR title ILIKE %s", 
                    (target_entity, sanitized_title)
                )
                rows = cur.fetchall()
                
                for row in rows:
                    fpath, t, c, m = row
                    if fpath not in seen_files:
                        max_priority = max((p for _, _, p in edges), default=0)
                        edge_info = ", ".join([f"{rel}←{src}" for rel, src, _ in edges[:3]])
                        # Boost score based on priority
                        boost = 1.0 + (max_priority * 0.1)
                        next_round_results.append((fpath, t, c, f"Graph({max_priority}): {edge_info}", boost))
        
        current_results = next_round_results
        round_idx += 1
            
    return all_results

def build_context_for_query(user_query, *, strategy=SEARCH_STRATEGY, limit=5, cost_tracker=None):
    all_results = retrieve_context_docs(user_query, strategy=strategy, limit=limit, cost_tracker=cost_tracker)
    
    context_text = ""
    source_mapping = {}
    context_parts = []
    
    for i, row in enumerate(all_results):
        file_path, title, content, section, similarity = row
        source_num = i + 1
        
        # Populate source mapping
        source_mapping[source_num] = {
            "title": title,
            "file_path": file_path,
            "section": section,
            "similarity": similarity,
        }

        header = f"--- Source {source_num}: {title} ({section or 'Doc'}) ({file_path}) ---"
        context_parts.append(f"{header}\n{content}")

    context_text = "\n\n".join(context_parts)
    logger.info(f"Context built with {len(all_results)} documents.")

    return context_text, source_mapping, all_results


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


# ==================== ReAct Mode Handler ====================

def _save_investigation(query: str, answer: str, trajectory: list):
    """
    Save the ReAct reasoning session as a knowledge artifact.
    
    Args:
        query: The user's original question
        answer: The final answer provided by the agent
        trajectory: List of reasoning steps (thought, action, observation)
    """
    import datetime
    import re
    
    try:
        # Create investigations directory if not exists
        investigations_dir = os.path.join(RAW_DIR, "investigations")
        os.makedirs(investigations_dir, exist_ok=True)
        
        # Generate filename based on timestamp and query
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sanitize query for filename
        slug = re.sub(r'[^\w\s-]', '', query).strip().lower()
        slug = re.sub(r'[-\s]+', '-', slug)[:50]
        filename = f"Investigation_{timestamp}_{slug}.md"
        filepath = os.path.join(investigations_dir, filename)
        
        # Format reasoning trace
        trace_md = ""
        for i, step in enumerate(trajectory):
            thought = step.get("thought", "").strip()
            action = step.get("action", "").strip()
            observation = step.get("observation", "").strip()
            
            trace_md += f"### Step {i+1}\n\n"
            if thought:
                trace_md += f"**Thought:** {thought}\n\n"
            if action:
                trace_md += f"**Action:** `{action}`\n\n"
            if observation:
                # Wrap long outputs in code block or blockquote
                if len(observation) > 100 or "\n" in observation:
                    trace_md += f"**Observation:**\n> {observation.replace(chr(10), chr(10)+'> ')}\n\n"
                else:
                    trace_md += f"**Observation:** {observation}\n\n"
        
        # Build document content
        content = f"""---
type: investigation
status: closed
date: {datetime.datetime.now().isoformat()}
query: "{query.replace('"', '\\"')}"
tags: [react, investigation, auto-generated]
---

# Investigation: {query}

## Executive Summary

{answer}

## Reasoning Trace

{trace_md}

## Methodology

This investigation was automatically generated by the Context Engine ReAct agent.
It represents a finalized reasoning process that successfully derived an answer.
"""
        
        # Write to file
        with open(filepath, "w") as f:
            f.write(content)
            
        logger.info(f"Saved investigation artifact: {filepath}")
        
    except Exception as e:
        logger.error(f"Failed to save investigation artifact: {e}")


async def handle_react_request(request: Request, user_query: str, body: dict):
    """
    Handle a chat completion request using the ReAct reasoning agent.
    
    This routes the request to the DSPy ReAct agent, which iteratively
    reasons and uses knowledge base tools to answer the question.
    
    Args:
        request: FastAPI request object
        user_query: The user's question
        body: The original request body
    
    Returns:
        JSONResponse in OpenAI chat completion format
    """
    import time as _time
    import uuid
    
    start_time = _time.time()
    
    try:
        from react_agent import ask_question
        
        # Use ReAct agent to answer the question
        result = ask_question(user_query, max_iters=5)
        
        latency_ms = int((_time.time() - start_time) * 1000)
        
        # Extract answer and trajectory
        answer = result.get("answer", "I couldn't find an answer to your question.")
        trajectory = result.get("trajectory", [])
        success = result.get("success", False)
        
        # Format reasoning trace as markdown for display
        reasoning_trace = ""
        if trajectory:
            reasoning_trace = "\n\n---\n**🧠 Reasoning Trace:**\n"
            for i, step in enumerate(trajectory):
                thought = step.get("thought", "")
                action = step.get("action", "")
                observation = step.get("observation", "")
                
                if thought:
                    reasoning_trace += f"\n**Step {i+1} - Thinking:** {thought}"
                if action:
                    reasoning_trace += f"\n**Action:** `{action}`"
                if observation:
                    # Truncate long observations
                    obs = observation[:500] + "..." if len(observation) > 500 else observation
                    reasoning_trace += f"\n**Observation:** {obs}"
                reasoning_trace += "\n"
        
        # Build the response content
        content = answer
        if trajectory and len(trajectory) > 0:
            content += reasoning_trace
        
        # Create OpenAI-compatible response
        response = {
            "id": f"chatcmpl-react-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(_time.time()),
            "model": "brain-react",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(user_query.split()),  # Approximate
                "completion_tokens": len(content.split()),  # Approximate
                "total_tokens": len(user_query.split()) + len(content.split())
            }
        }
        
        # Log cost if tracker available
        cost_tracker = getattr(request.app.state, 'cost_tracker', None)
        if cost_tracker:
            try:
                cost_tracker.log_request(
                    operation="react-agent",
                    model="brain-react",
                    input_tokens=response["usage"]["prompt_tokens"],
                    output_tokens=response["usage"]["completion_tokens"],
                    latency_ms=latency_ms
                )
            except Exception as log_e:
                logger.warning(f"Failed to log ReAct cost: {log_e}")
        
        # Save as investigation artifact if successful and has trajectory
        if success and trajectory:
            _save_investigation(user_query, answer, trajectory)

        logger.info(f"ReAct completed in {latency_ms}ms, success={success}, steps={len(trajectory)}")
        return JSONResponse(response)
        
    except Exception as e:
        logger.error(f"ReAct agent error: {e}")
        import traceback
        traceback.print_exc()
        
        # Return error as a chat response so user sees it
        error_response = {
            "id": f"chatcmpl-error-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(_time.time()),
            "model": "brain-react",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"⚠️ ReAct reasoning failed: {str(e)}\n\nPlease try rephrasing your question or use the standard RAG model."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        return JSONResponse(error_response)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
        if not messages:
            return JSONResponse({"error": "No messages provided"}, status_code=400)

        # 1. Get user query
        user_query = messages[-1]["content"] or ""
        model_name = body.get("model", "")
        logger.info(f"RAG Request: {user_query[:50]}... (model: {model_name})")

        # Check if this is a brain-react model (ReAct reasoning mode)
        is_react_mode = "brain-react" in model_name.lower() or "react" in model_name.lower()
        
        if is_react_mode:
            # Use ReAct agent for this request
            logger.info("Using ReAct reasoning mode...")
            return await handle_react_request(request, user_query, body)

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
