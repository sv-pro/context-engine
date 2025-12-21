import os
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import Json

logger = logging.getLogger(__name__)

from config import current_config

class Database:
    def __init__(self):
        self.url = os.environ.get("DATABASE_URL")
        self.embedding_dim = current_config.dimensions
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
                    embedding vector({dim}),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """.format(dim=self.embedding_dim))

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
                    embedding vector({dim}),
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(note_id, chunk_index)
                );
            """.format(dim=self.embedding_dim))
            
            # Create index for chunk embeddings if not exists
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
                ON brain.chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)

            # Add GIN indices for Full-Text Search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_content_gin ON brain.chunks USING GIN (to_tsvector('english', content));
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_content_gin ON brain.notes USING GIN (to_tsvector('english', content));
            """)
            
            logger.info("Database schema (brain) initialized with chunks table")


    def upsert_note(self, file_path, title, content, metadata):
        """
        Upserts a note and returns (id, was_updated).
        was_updated is True if content or metadata changed, indicating re-embedding is needed.
        """
        # Convert date objects to strings for JSON serialization
        import datetime
        serializable_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, (datetime.date, datetime.datetime)):
                serializable_metadata[k] = v.isoformat()
            else:
                serializable_metadata[k] = v
        
        metadata_json = Json(serializable_metadata)

        with self.conn.cursor() as cur:
            # Check if note exists and if content/metadata matches
            cur.execute("""
                SELECT id, title, content, metadata FROM brain.notes WHERE file_path = %s;
            """, (file_path,))
            existing = cur.fetchone()

            if existing:
                note_id, old_title, old_content, old_metadata = existing
                # Check for changes
                if old_title == title and old_content == content and old_metadata == serializable_metadata:
                    # No changes, skip update
                    return note_id, False
                
                # Changes detected, update
                cur.execute("""
                    UPDATE brain.notes SET
                        title = %s,
                        content = %s,
                        metadata = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (title, content, metadata_json, note_id))
                return note_id, True
            else:
                # New note
                cur.execute("""
                    INSERT INTO brain.notes (file_path, title, content, metadata, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id;
                """, (file_path, title, content, metadata_json))
                res = cur.fetchone()
                return res[0], True

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
                    ON CONFLICT DO NOTHING
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

    def graph_hybrid_search(self, query_vector, limit=5, wide_limit=15, threshold=0.4):
        """
        Implements Graph-Hybrid search:
        1. Wide semantic sweep (low threshold) to find candidates.
        2. Path-weighting to find "Hub" documents linked by candidates.
        3. Returns a mix of direct semantic hits and highly-linked hubs.
        """
        with self.conn.cursor() as cur:
            # Stage 1 & 2: Wide sweep and neighbor voting in one query
            # We use CTEs to find candidates and then count their outgoing links to other notes.
            cur.execute("""
                WITH wide_pool AS (
                    SELECT n.id as note_id, n.file_path, n.title, c.content, c.section,
                           1 - (c.embedding <=> %s::vector) as similarity
                    FROM brain.chunks c
                    JOIN brain.notes n ON c.note_id = n.id
                    WHERE c.embedding IS NOT NULL AND 1 - (c.embedding <=> %s::vector) > %s
                    ORDER BY similarity DESC
                    LIMIT %s
                ),
                hub_votes AS (
                    SELECT e.target_title, COUNT(*) as path_count
                    FROM brain.edges e
                    JOIN wide_pool w ON e.source_id = w.note_id
                    GROUP BY e.target_title
                ),
                hubs AS (
                    SELECT n.file_path, n.title, SUBSTRING(n.content FROM 1 FOR 1000) as content, 
                           'Structural Hub' as section, 0.4 as similarity, h.path_count
                    FROM brain.notes n
                    JOIN hub_votes h ON n.title = h.target_title
                    WHERE n.title NOT IN (SELECT title FROM wide_pool)
                    ORDER BY h.path_count DESC
                    LIMIT 2
                )
                -- Combine top semantic results and top structural hubs
                SELECT file_path, title, content, section, similarity FROM (
                    (SELECT file_path, title, content, section, similarity, 0 as path_count FROM wide_pool LIMIT 3)
                    UNION ALL
                    (SELECT file_path, title, content, section, similarity, path_count FROM hubs)
                ) combined
                ORDER BY path_count DESC, similarity DESC
                LIMIT %s;
            """, (query_vector, query_vector, threshold, wide_limit, limit))
            
            results = cur.fetchall()
            return results

    def keyword_search(self, query_text, limit=3):
        """
        Performs full-text keyword search on chunks.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT n.file_path, n.title, c.content, c.section, 
                       ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', %s)) as similarity
                FROM brain.chunks c
                JOIN brain.notes n ON c.note_id = n.id
                WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', %s)
                ORDER BY similarity DESC
                LIMIT %s;
            """, (query_text, query_text, limit))
            return cur.fetchall()

    def search(self, query_text, query_vector, strategy='graph', limit=5):
        """
        Unified search router that supports multiple strategies and RRF merging.
         Strategies: 'semantic', 'keyword', 'graph', 'hybrid', 'super_hybrid'
        """
        if strategy == 'semantic':
            return self.semantic_search(query_vector, limit=limit)
        elif strategy == 'keyword':
            return self.keyword_search(query_text, limit=limit)
        elif strategy == 'graph':
            return self.graph_hybrid_search(query_vector, limit=limit)
        elif strategy == 'hybrid':
            return self._rrf_search(query_text, query_vector, limit=limit, include_graph=False)
        elif strategy == 'super_hybrid':
            return self._rrf_search(query_text, query_vector, limit=limit, include_graph=True)
        else:
            logger.warning(f"Unknown search strategy: {strategy}. Defaulting to semantic.")
            return self.semantic_search(query_vector, limit=limit)

    def _rrf_search(self, query_text, query_vector, limit=5, include_graph=False, k=60):
        """
        Implements Reciprocal Rank Fusion (RRF) to combine multiple search results.
        score = sum(1 / (k + rank))
        """
        # Gather result sets
        semantic_results = self.semantic_search(query_vector, limit=limit*2)
        keyword_results = self.keyword_search(query_text, limit=limit*2)
        
        streams = [semantic_results, keyword_results]
        if include_graph:
            graph_results = self.graph_hybrid_search(query_vector, limit=limit*2)
            streams.append(graph_results)

        # Merge results using RRF
        scores = {}  # (file_path, title, content, section) -> score
        metadata = {} # (file_path, title, content, section) -> max_similarity

        for stream in streams:
            for rank, row in enumerate(stream):
                # row structure: (file_path, title, content, section, similarity)
                key = (row[0], row[1], row[2], row[3])
                score = 1.0 / (k + rank + 1)
                scores[key] = scores.get(key, 0) + score
                metadata[key] = max(metadata.get(key, 0), row[4])

        # Sort by RRF score
        sorted_keys = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Format final results
        final_results = []
        for key, score in sorted_keys[:limit]:
            # Re-attach the max similarity seen across streams for UI/logging
            final_results.append((key[0], key[1], key[2], key[3], metadata[key]))

        return final_results

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
