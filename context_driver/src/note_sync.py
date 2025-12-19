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

logger = logging.getLogger(__name__)

# WebUI database connection
WEBUI_DATABASE_URL = os.environ.get("WEBUI_DATABASE_URL", "postgresql://postgres:postgres@db:5432/webui")


class NoteSyncer:
    """Synchronizes Open WebUI notes with the brain knowledge base."""
    
    def __init__(self, brain_db):
        """
        Initialize the NoteSyncer.
        
        Args:
            brain_db: Database instance for brain operations
        """
        self.brain_db = brain_db
        self.webui_conn = None
        self._last_sync_timestamp = 0
    
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
            # Check for common fields
            if 'content' in data:
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
    
    def sync_note(self, note: Dict, get_embedding_fn) -> Optional[int]:
        """
        Sync a single note to the brain KB.
        
        Args:
            note: Note dictionary from webui.note
            get_embedding_fn: Function to generate embeddings
        
        Returns:
            note_id in brain.notes or None if failed
        """
        try:
            note_id = note['id']
            title = note['title'] or f"Untitled Note ({note_id[:8]})"
            data = note['data']
            
            # Convert to markdown
            content = self.json_to_markdown(title, data)
            
            # Create a synthetic file path for tracking
            file_path = f"webui://notes/{note_id}"
            
            # Upsert into brain.notes
            brain_note_id = self.brain_db.upsert_note(
                file_path=file_path,
                title=title,
                content=content,
                metadata={
                    'source': 'open_webui_notes',
                    'webui_note_id': note_id,
                    'user_id': note['user_id'],
                    'created_at': note['created_at'],
                    'updated_at': note['updated_at']
                }
            )
            
            logger.info(f"Synced note: {title} (brain_id={brain_note_id})")
            
            # Chunk and embed
            from chunker import split_markdown
            chunks = split_markdown(content, max_tokens=500, overlap_tokens=50)
            
            if chunks:
                self.brain_db.upsert_chunks(brain_note_id, chunks)
                
                for chunk in chunks:
                    chunk_vector = get_embedding_fn(chunk.content)
                    if chunk_vector:
                        self.brain_db.update_chunk_embedding(brain_note_id, chunk.chunk_index, chunk_vector)
                
                logger.info(f"Created {len(chunks)} chunks for note: {title}")
            
            # Also create note-level embedding
            note_vector = get_embedding_fn(content)
            if note_vector:
                self.brain_db.update_embedding(brain_note_id, note_vector)
            
            return brain_note_id
            
        except Exception as e:
            logger.error(f"Failed to sync note {note.get('id')}: {e}")
            return None
    
    def sync_all(self, get_embedding_fn) -> int:
        """
        Sync all notes from Open WebUI to brain.
        
        Args:
            get_embedding_fn: Function to generate embeddings
        
        Returns:
            Number of notes synced
        """
        notes = self.get_all_notes()
        synced = 0
        
        for note in notes:
            if self.sync_note(note, get_embedding_fn):
                synced += 1
        
        logger.info(f"Synced {synced}/{len(notes)} notes from Open WebUI")
        return synced
    
    def sync_updates(self, get_embedding_fn) -> int:
        """
        Sync only notes updated since last sync.
        
        Args:
            get_embedding_fn: Function to generate embeddings
        
        Returns:
            Number of notes synced
        """
        try:
            notes = self.get_updated_notes(self._last_sync_timestamp)
            synced = 0
            
            for note in notes:
                # updated_at is in milliseconds
                if self.sync_note(note, get_embedding_fn):
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

    def start_polling(self, get_embedding_fn, interval_seconds: int = 60):
        """
        Start background polling for note updates.
        
        Args:
            get_embedding_fn: Function to generate embeddings
            interval_seconds: Polling interval
        """
        import threading
        import time
        
        self._stop_polling = False
        
        def poll():
            logger.info(f"Started Open WebUI notes watchdog (interval: {interval_seconds}s)")
            
            # Initial sync of all notes
            try:
                self.sync_all(get_embedding_fn)
            except Exception as e:
                logger.error(f"Initial notes sync failed: {e}")

            while not self._stop_polling:
                try:
                    self.sync_updates(get_embedding_fn)
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
