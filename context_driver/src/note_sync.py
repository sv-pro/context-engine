"""
Open WebUI Notes synchronization module.
Polls the webui.note table and syncs notes into the brain KB.
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
import json
import re
from enricher import enrich_markdown

logger = logging.getLogger(__name__)

# WebUI database connection
WEBUI_DATABASE_URL = os.environ.get("WEBUI_DATABASE_URL", "postgresql://postgres:postgres@db:5432/webui")


class NoteSyncer:
    """Synchronizes Open WebUI notes with the brain knowledge base."""
    
    def __init__(self, brain_db, brain_dir: str = "/app/brain"):
        """
        Initialize the NoteSyncer.
        
        Args:
            brain_db: Database instance for brain operations
            brain_dir: Path to brain directory (source of truth)
        """
        self.brain_db = brain_db
        self.brain_dir = brain_dir
        self.webui_notes_dir = os.path.join(brain_dir, "webui_notes")
        self.webui_conn = None
        self._last_sync_timestamp = 0
        
        # Ensure webui_notes directory exists
        os.makedirs(self.webui_notes_dir, exist_ok=True)
    
    def _connect_webui(self):
        """Connect to Open WebUI database."""
        if self.webui_conn is None or self.webui_conn.closed:
            try:
                self.webui_conn = psycopg2.connect(WEBUI_DATABASE_URL)
                # Test connection
                with self.webui_conn.cursor() as cur:
                    cur.execute("SELECT 1")
                logger.info("Connected to Open WebUI database")
            except Exception as e:
                logger.error(f"Failed to connect to WebUI database: {e}")
                self.webui_conn = None
                raise
        return self.webui_conn
    
    def get_all_notes(self) -> List[Dict]:
        """
        Fetch all notes from Open WebUI.
        
        Returns:
            List of note dictionaries
        """
        conn = self._connect_webui()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, user_id, title, data, meta, created_at, updated_at
                FROM note
                ORDER BY updated_at DESC;
            """)
            return cur.fetchall()
    
    def get_updated_notes(self, since_timestamp: int = 0) -> List[Dict]:
        """
        Fetch notes updated since a given timestamp.
        
        Args:
            since_timestamp: Unix timestamp (milliseconds)
        
        Returns:
            List of updated note dictionaries
        """
        conn = self._connect_webui()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, user_id, title, data, meta, created_at, updated_at
                FROM note
                WHERE updated_at > %s
                ORDER BY updated_at ASC;
            """, (since_timestamp,))
            return cur.fetchall()
    
    def json_to_markdown(self, title: str, data: dict) -> str:
        """
        Convert Open WebUI note JSON data to markdown.
        
        Args:
            title: Note title
            data: Note data JSON (may contain 'content' field)
        
        Returns:
            Markdown string
        """
        if data is None:
            return f"# {title}\n\n(Empty note)"
        
        # Handle different data structures
        content = ""
        
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict):
            # Open WebUI notes have 'md', 'html', 'json' fields
            if 'md' in data:
                content = data['md']
            elif 'content' in data:
                content = data['content']
            elif 'text' in data:
                content = data['text']
            elif 'body' in data:
                content = data['body']
            else:
                # Serialize the entire dict as formatted JSON
                content = f"```json\n{json.dumps(data, indent=2)}\n```"
        else:
            content = str(data)
        
        # Build markdown document
        markdown = f"# {title}\n\n{content}"
        
        return markdown
    
    def sync_note(self, note: Dict, get_embedding_fn=None, extract_keywords_fn=None) -> Optional[str]:
        """
        Sync a single note to the brain KB by writing it as a markdown file.
        The file watcher will handle ingestion.
        
        Args:
            note: Note dictionary from webui.note
            get_embedding_fn: Not used (file watcher handles embedding)
            extract_keywords_fn: Not used (file watcher handles keywords)
        
        Returns:
            file_path of written note or None if failed
        """
        try:
            note_id = note['id']
            title = note['title'] or f"Untitled_Note_{note_id[:8]}"
            data = note['data']
            
            # Sanitize title for filename
            safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)
            file_name = f"{safe_title}.md"
            file_path = os.path.join(self.webui_notes_dir, file_name)
            
            # Convert to markdown
            content = self.json_to_markdown(title, data)
            
            # Add YAML frontmatter with metadata
            frontmatter = [
                "---",
                f"title: {title}",
                f"source: open_webui_notes",
                f"webui_note_id: {note_id}",
                f"user_id: {note['user_id']}",
                f"created_at: {note['created_at']}",
                f"updated_at: {note['updated_at']}",
                "---",
                ""
            ]
            
            full_content = "\n".join(frontmatter) + content
            
            # Write to file (brain directory is the source of truth)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            logger.info(f"Wrote note to file: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to sync note {note.get('id', 'unknown')}: {e}")
            return None
    
    def sync_all(self, get_embedding_fn=None, extract_keywords_fn=None) -> int:
        """
        Sync all notes from Open WebUI to brain KB.
        Writes notes as markdown files; file watcher handles ingestion.
        
        Returns:
            Number of notes synced
        """
        notes = self.get_all_notes()
        synced = 0
        
        for note in notes:
            if self.sync_note(note, get_embedding_fn, extract_keywords_fn):
                synced += 1
        
        logger.info(f"Synced {synced}/{len(notes)} notes from Open WebUI")
        return synced
    
    def sync_updates(self, get_embedding_fn=None, extract_keywords_fn=None) -> int:
        """
        Sync only updated notes since last sync.
        Writes notes as markdown files; file watcher handles ingestion.
        
        Returns:
            Number of notes synced
        """
        try:
            notes = self.get_updated_notes(self._last_sync_timestamp)
            synced = 0
            
            for note in notes:
                # updated_at is in milliseconds
                if self.sync_note(note, get_embedding_fn, extract_keywords_fn):
                    synced += 1
                    # Update timestamp
                    if note['updated_at'] > self._last_sync_timestamp:
                        self._last_sync_timestamp = note['updated_at']
            
            if synced > 0:
                logger.info(f"Synced {synced} updated notes from Open WebUI")
            
            return synced
        except Exception as e:
            logger.error(f"Error during sync_updates: {e}")
            return 0

    def start_polling(self, get_embedding_fn, extract_keywords_fn=None, interval_seconds: int = 60):
        """
        Start background polling for note updates.
        
        Args:
            get_embedding_fn: Function to generate embeddings
            extract_keywords_fn: Function to extract semantic keywords
            interval_seconds: Polling interval
        """
        import threading
        import time
        
        self._stop_polling = False
        
        def poll():
            logger.info(f"Started Open WebUI notes watchdog (interval: {interval_seconds}s)")
            
            # Initial sync of all notes
            try:
                self.sync_all(get_embedding_fn, extract_keywords_fn)
            except Exception as e:
                logger.error(f"Initial notes sync failed: {e}")

            while not self._stop_polling:
                try:
                    self.sync_updates(get_embedding_fn, extract_keywords_fn)
                except Exception as e:
                    logger.error(f"Error in notes watchdog loop: {e}")
                
                # Sleep in small increments to respond to stop signal
                for _ in range(interval_seconds):
                    if self._stop_polling:
                        break
                    time.sleep(1)
            
            logger.info("Stopped Open WebUI notes watchdog")

        self.polling_thread = threading.Thread(target=poll, daemon=True)
        self.polling_thread.start()

    def stop_polling(self):
        """Stop background polling."""
        self._stop_polling = True
        if hasattr(self, 'polling_thread'):
            self.polling_thread.join(timeout=5)

    def close(self):
        """Close database connections."""
        self.stop_polling()
        if self.webui_conn and not self.webui_conn.closed:
            self.webui_conn.close()
