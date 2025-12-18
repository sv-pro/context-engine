import os
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import Json

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.url = os.environ.get("DATABASE_URL")
        self.conn = None
        self._connect()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(self.url)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info("Connected to PostgreSQL")
            self._init_schema()
        except Exception as e:
            logger.error(f"Failed to connect to DB: {e}")
            raise

    def _init_schema(self):
        with self.conn.cursor() as cur:
            # Create brain schema
            cur.execute("CREATE SCHEMA IF NOT EXISTS brain;")
            
            # Enable pgvector extension (usually in public)
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create notes table in brain schema
            cur.execute("""
                CREATE TABLE IF NOT EXISTS brain.notes (
                    id SERIAL PRIMARY KEY,
                    file_path TEXT UNIQUE NOT NULL,
                    title TEXT,
                    content TEXT,
                    metadata JSONB,
                    embedding vector(768),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create edges table in brain schema
            cur.execute("""
                CREATE TABLE IF NOT EXISTS brain.edges (
                    source_id INT REFERENCES brain.notes(id) ON DELETE CASCADE,
                    target_title TEXT,
                    type TEXT,
                    PRIMARY KEY (source_id, target_title)
                );
            """)
            logger.info("Database schema (brain) initialized")

    def upsert_note(self, file_path, title, content, metadata):
        # Convert date objects to strings for JSON serialization
        import datetime
        serializable_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, (datetime.date, datetime.datetime)):
                serializable_metadata[k] = v.isoformat()
            else:
                serializable_metadata[k] = v

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO brain.notes (file_path, title, content, metadata, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (file_path) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
            """, (file_path, title, content, Json(serializable_metadata)))
            note_id = cur.fetchone()[0]
            return note_id

    def update_embedding(self, note_id, vector):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE brain.notes SET embedding = %s WHERE id = %s", (vector, note_id))

    def update_links(self, note_id, links):
        with self.conn.cursor() as cur:
            # Clear existing links for this note
            cur.execute("DELETE FROM brain.edges WHERE source_id = %s", (note_id,))
            
            # Insert new links
            for link in links:
                cur.execute("""
                    INSERT INTO brain.edges (source_id, target_title, type)
                    VALUES (%s, %s, 'wikilink')
                """, (note_id, link))

    def semantic_search(self, query_vector, limit=3):
        """
        Performs vector similarity search.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT title, content, metadata, 1 - (embedding <=> %s::vector) as similarity
                FROM brain.notes
                WHERE embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT %s;
            """, (query_vector, limit))
            return cur.fetchall()
