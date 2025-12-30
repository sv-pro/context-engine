# Part 2: Memory & Intelligence

> *Teaching the system to remember with PostgreSQL and pgvector*

**Commits:** `f0eceee` → `f109256`

---

## The Problem

A chat interface is useless if it can't remember anything. And "remembering" in the AI context means more than conversation history — it means **semantic search over your documents**.

I wanted to ask: *"What's our SSL certificate renewal process?"* and get answers from my own notes.

## Adding the Database Layer

PostgreSQL joined the stack. But not vanilla Postgres — **pgvector** enabled.

```yaml
postgres:
  image: pgvector/pgvector:pg16
  environment:
    POSTGRES_DB: context_engine
    POSTGRES_USER: context
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - ./volumes/postgres:/var/lib/postgresql/data
```

Redis came along for caching and session management:

```yaml
redis:
  image: redis:alpine
  volumes:
    - ./volumes/redis:/data
```

## The Context Driver

Here's where the magic began. A Python service that:

1. **Watches a directory** of markdown files using `watchdog`
2. **Parses frontmatter** YAML metadata from each file
3. **Generates embeddings** via OpenAI/Ollama
4. **Stores everything** in pgvector for semantic search

### The File Watcher

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class BrainWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.md'):
            self.process_file(event.src_path)
    
    def process_file(self, path):
        content = read_file(path)
        metadata = parse_frontmatter(content)
        embedding = generate_embedding(content)
        store_in_database(path, metadata, embedding)
```

### The Frontmatter Parser

Files could now carry structured metadata:

```markdown
---
title: SSL Certificate Renewal
tags: [ssl, certificates, infrastructure]
related: [[DNS_Configuration]]
---

# SSL Certificate Renewal

Here's how to renew certificates...
```

The parser extracts this YAML, making files searchable by tags and relationships.

### Semantic Search

With embeddings in pgvector, semantic search became trivial:

```python
def search(query: str, limit: int = 5):
    query_embedding = generate_embedding(query)
    
    results = db.execute("""
        SELECT title, content, 
               1 - (embedding <=> %s) as similarity
        FROM brain.notes
        ORDER BY embedding <=> %s
        LIMIT %s
    """, [query_embedding, query_embedding, limit])
    
    return results
```

The `<=>` operator is pgvector's cosine distance. Lower distance = more similar.

## Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA brain;

CREATE TABLE brain.notes (
    id SERIAL PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    metadata JSONB,
    embedding vector(1536),  -- OpenAI dimensions
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON brain.notes 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

## Integration Points

The Context Driver exposed a simple HTTP API:

- `POST /search` — Semantic search
- `GET /articles` — List all documents
- `GET /article/{title}` — Get full content

Open WebUI and LiteLLM could now query the knowledge base.

## Lessons Learned

1. **pgvector is production-ready** — no need for separate vector databases
2. **Frontmatter is powerful** — structured metadata in plain text
3. **File watching enables real-time sync** — edit in Obsidian, search immediately
4. **Embeddings are the foundation** — but not the whole story

## What's Next

Semantic search works, but it's naive. It treats every document as one big chunk. Long documents get poor embeddings.

Part 3 introduces **chunked embeddings, hybrid search, and real citations**.

---

[← Previous: The Foundation](./01-the-foundation.md) | [Back to Index](./README.md) | [Next: RAG Evolution →](./03-rag-evolution.md)
