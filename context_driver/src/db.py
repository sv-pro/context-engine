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
                    embedding vector(1024),
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
            
            # Create chunks table for fine-grained embeddings
            cur.execute("""
                CREATE TABLE IF NOT EXISTS brain.chunks (
                    id SERIAL PRIMARY KEY,
                    note_id INT REFERENCES brain.notes(id) ON DELETE CASCADE,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    section TEXT,
                    embedding vector(1024),
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(note_id, chunk_index)
                );
            """)
            
            # Create index for chunk embeddings if not exists
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
                ON brain.chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            
            logger.info("Database schema (brain) initialized with chunks table")


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
        Performs vector similarity search on chunks (preferred) or notes.
        Returns chunks with their parent note titles for context.
        """
        with self.conn.cursor() as cur:
            # First try chunk-based search
            cur.execute("""
                SELECT n.file_path, n.title, c.content, c.section, 1 - (c.embedding <=> %s::vector) as similarity
                FROM brain.chunks c
                JOIN brain.notes n ON c.note_id = n.id
                WHERE c.embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT %s;
            """, (query_vector, limit))
            results = cur.fetchall()
            
            # Fall back to note-based search if no chunks exist
            if not results:
                cur.execute("""
                    SELECT file_path, title, content, metadata, 1 - (embedding <=> %s::vector) as similarity
                    FROM brain.notes
                    WHERE embedding IS NOT NULL
                    ORDER BY similarity DESC
                    LIMIT %s;
                """, (query_vector, limit))
                results = cur.fetchall()
            
            return results

    def semantic_search_notes(self, query_vector, limit=3):
        """
        Legacy: Performs vector similarity search on whole notes.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT file_path, title, content, metadata, 1 - (embedding <=> %s::vector) as similarity
                FROM brain.notes
                WHERE embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT %s;
            """, (query_vector, limit))
            return cur.fetchall()

    def upsert_chunks(self, note_id, chunks):
        """
        Insert or update chunks for a note.
        
        Args:
            note_id: The parent note ID
            chunks: List of Chunk objects from chunker.py
        """
        with self.conn.cursor() as cur:
            # Clear existing chunks for this note
            cur.execute("DELETE FROM brain.chunks WHERE note_id = %s", (note_id,))
            
            # Insert new chunks
            for chunk in chunks:
                cur.execute("""
                    INSERT INTO brain.chunks (note_id, chunk_index, content, section, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    note_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.section,
                    Json({
                        'line_start': chunk.line_start,
                        'line_end': chunk.line_end
                    })
                ))
            
            logger.info(f"Upserted {len(chunks)} chunks for note_id={note_id}")

    def update_chunk_embedding(self, note_id, chunk_index, vector):
        """
        Update embedding for a specific chunk.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE brain.chunks 
                SET embedding = %s 
                WHERE note_id = %s AND chunk_index = %s
            """, (vector, note_id, chunk_index))

    def get_chunks(self, note_id):
        """
        Get all chunks for a note.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, chunk_index, content, section, embedding IS NOT NULL as has_embedding
                FROM brain.chunks
                WHERE note_id = %s
                ORDER BY chunk_index;
            """, (note_id,))
            return cur.fetchall()
