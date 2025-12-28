# Context-Engine: RAG-Enhanced Chat with Local Knowledge Base

A self-hosted, privacy-first AI chat system with Retrieval-Augmented Generation (RAG) powered by your own knowledge base.

## 🎯 The Idea

**Problem**: Generic LLMs don't know your specific domain knowledge. Enterprise documentation, product details, internal processes—none of it exists in the LLM's training data.

**Solution**: Context-Engine intercepts chat requests, searches your local knowledge base using semantic similarity, and injects relevant context into the prompt before sending to the LLM. The result? An AI that knows YOUR information.

```
User: "Where are private keys stored?"
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Context Driver (RAG Proxy)                                  │
│   1. Extract user query                                     │
│   2. Generate embedding with mxbai-embed-large              │
│   3. Search brain.chunks via pgvector (cosine similarity)   │
│   4. Inject top 3 matches into prompt                       │
│   5. Forward to LLM                                         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
LLM Response: "Private keys are stored in HashiCorp Vault 
              with AES-256-GCM encryption..."
```

## ✨ Features

### Core
- **Open WebUI** - Beautiful chat interface
- **RAG Pipeline** - Semantic search over your knowledge base (`brain-rag` model)
- **ReAct Reasoning** - Iterative reasoning with tool use (`brain-react` model)
- **MCP Server** - Tool-based article exploration for Agentic AI
- **Chunked Embeddings** - 500-token chunks for precise retrieval
- **Vendor LLM Priority** - OpenAI → Anthropic → Ollama fallback
- **Meta-prompt Bypass** - Internal prompts skip RAG for efficiency

### Knowledge Base
- **55+ Knowledge Articles** - Scrubbing Center Portal documentation
- **Markdown Files** - Simple format, easy to edit
- **File Watcher** - Auto-ingests new/modified files
- **Open WebUI Notes Sync** - Create knowledge via chat interface
- **Cost Tracking Dashboard** - Monitor LLM API costs and token usage in real-time
- **Sub-Brains** - Scope searches to specific subdirectories for different modes/apps
- **`.brainignore`** - Exclude sub-brains from parent indexing

### Technical
- **pgvector** - PostgreSQL extension for vector similarity search
- **mxbai-embed-large** - 1024-dim embeddings (high quality)
- **Chunking with Overlap** - 50-token overlap prevents context loss
- **Database Isolation** - Separate schemas: litellm, webui, brain

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  Open WebUI │────▶│   LiteLLM   │────▶│ Context Driver  │
│  Port 3000  │     │  Port 4000  │     │   (RAG Proxy)   │
└─────────────┘     └─────────────┘     │   Port 8000     │
                                        └────────┬────────┘
                                                 │
                    ┌────────────────────────────┼────────────────┐
                    │                            │                │
                    ▼                            ▼                ▼
            ┌──────────────┐            ┌──────────────┐   ┌───────────┐
            │  PostgreSQL  │            │    Ollama    │   │ OpenAI/   │
            │  + pgvector  │            │   (local)    │   │ Anthropic │
            └──────────────┘            └──────────────┘   └───────────┘
```

### Components

| Service        | Purpose                 | Port  |
| -------------- | ----------------------- | ----- |
| Open WebUI     | Chat interface          | 3000  |
| LiteLLM        | Model proxy/router      | 4000  |
| Context Driver | RAG pipeline            | 8000  |
| PostgreSQL     | Vector DB + persistence | 5432  |
| Redis          | LiteLLM caching         | 6379  |
| Ollama         | Local LLM/embeddings    | 11434 |

## 🚀 Quick Start

```bash
# Clone and start
git clone https://github.com/sv-pro/context-engine.git
cd context-engine

# Optional: Add vendor API keys for cloud models
echo "OPENAI_API_KEY=sk-..." >> .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# Start all services
make quickstart

# Open browser
open http://localhost:3000
```

## 📁 Knowledge Base

### Adding Knowledge

**Option 1: Markdown Files**
```bash
# Create a new article
cat > volumes/brain/My_Topic.md << 'EOF'
# My Topic

This is knowledge that the RAG will use.

## Section 1
Details here...
EOF
```

**Option 2: Open WebUI Notes**
1. Open http://localhost:3000
2. Go to Notes (top-right menu)
3. Create a note with your knowledge
4. Trigger sync: `curl -X POST http://localhost:8000/sync-notes`

### Sub-Brains

Scope searches to specific subdirectories for different modes, apps, or contexts:

```bash
# Search only within a sub-brain
curl -X POST "http://localhost:8000/tools/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "SSL certificates", "sub_path": "projects/myapp"}'

# Discover available sub-brains
curl "http://localhost:8000/tools/sub-brains"
```

Use `.brainignore` to exclude sub-brains from parent indexing. See [SUB_BRAINS.md](SUB_BRAINS.md) for details.

### How Chunking Works

Large articles are split into ~500-token chunks with 50-token overlap:

```
Article: SSL_Certificates.md (2000 tokens)
         ↓
├── Chunk 0: "# SSL/TLS Certificates..." (embedding_0)
├── Chunk 1: "## Certificate Storage..." (embedding_1)  ← High similarity to storage queries
└── Chunk 2: "## Troubleshooting..."    (embedding_2)
```

Each chunk gets its own embedding, enabling precise semantic matching.

## 🔧 Configuration

### Environment Variables

| Variable            | Description                        | Default               |
| ------------------- | ---------------------------------- | --------------------- |
| `OPENAI_API_KEY`    | OpenAI API key (optional)          | -                     |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional)       | -                     |
| `BRAIN_DIR`         | Processed knowledge base directory | `/app/brain`          |
| `RAW_DIR`           | Raw document ingestion source      | `/app/raw`            |
| `BRAIN_SUBDIR`      | Default sub-brain scope (optional) | - (full brain)        |
| `OLLAMA_API_BASE`   | Ollama API endpoint                | `http://ollama:11434` |

### LLM Priority

The system automatically selects the best available LLM:
1. **OpenAI** (gpt-4o-mini) - if `OPENAI_API_KEY` set
2. **Anthropic** (claude-3-haiku) - if `ANTHROPIC_API_KEY` set
3. **Ollama** (llama3) - local fallback

### Brain Models

Two specialized pseudo-models are available in Open WebUI:

| Model | Description | Best For |
|-------|-------------|----------|
| `brain-rag` | Single-pass RAG - retrieves context, injects into prompt | Simple questions, fast responses |
| `brain-react` | ReAct reasoning - iterative tool use with thinking | Complex questions requiring multi-step reasoning |

**Example - Using brain-react:**
```
User: "How is SSL configured in the system and what troubleshooting steps exist?"

🧠 ReAct Reasoning:
1. Search for "SSL configuration"
2. Find related facts and rules
3. Search for "SSL troubleshooting"
4. Synthesize comprehensive answer
```

## 📊 API Endpoints

### Context Driver (Port 8000)

| Endpoint               | Method | Description                  |
| ---------------------- | ------ | ---------------------------- |
| `/v1/chat/completions` | POST   | RAG-enhanced chat            |
| `/v1/context`          | POST   | Context preview (no LLM call) |
| `/sync-notes`          | POST   | Sync Open WebUI notes to KB  |
| `/sync-notes/status`   | GET    | Check note sync status       |
| `/tools/search`        | POST   | Search with optional sub_path |
| `/tools/sub-brains`    | GET    | List available sub-brains    |
| `/mcp/sse`             | GET    | MCP Server-Sent Events (SSE) |
| `/mcp/messages`        | POST   | MCP Messages transport       |
| `/health`              | GET    | Health check                 |

### Example RAG Query

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "brain-rag",
    "messages": [{"role": "user", "content": "Where are private keys stored?"}],
    "stream": false
  }'
```

### Example Context Preview

```bash
curl http://localhost:8000/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Where are private keys stored?",
    "limit": 5,
    "strategy": "super_hybrid"
  }'
```

### Example CLI (inside context-driver container)

```bash
python src/cli.py /context "Where are private keys stored?"
```

## 🗄️ Database Schema

### brain.notes
| Column    | Type         | Description                         |
| --------- | ------------ | ----------------------------------- |
| id        | SERIAL       | Primary key                         |
| file_path | TEXT         | Source file or `webui://notes/{id}` |
| title     | TEXT         | Article title                       |
| content   | TEXT         | Full markdown content               |
| embedding | vector(1024) | Note-level embedding                |

### brain.chunks
| Column      | Type         | Description          |
| ----------- | ------------ | -------------------- |
| id          | SERIAL       | Primary key          |
| note_id     | INT          | Foreign key to notes |
| chunk_index | INT          | Position in article  |
| content     | TEXT         | Chunk content        |
| section     | TEXT         | Section header       |
| embedding   | vector(1024) | Chunk embedding      |

## 🔬 Implementation Details

### Embedding Model
- **Model**: `mxbai-embed-large` (1024 dimensions)
- **Previous**: `nomic-embed-text` (768 dimensions) - replaced due to vocabulary limitations
- **Index**: ivfflat with cosine similarity

### Chunking Strategy
- **Max Tokens**: 500 per chunk
- **Overlap**: 50 tokens between chunks
- **Section Tracking**: Preserves header context

### Semantic Search
```sql
SELECT n.title, c.content, c.section, 
       1 - (c.embedding <=> query_vector) as similarity
FROM brain.chunks c
JOIN brain.notes n ON c.note_id = n.id
WHERE c.embedding IS NOT NULL
ORDER BY similarity DESC
LIMIT 3;
```

## 📈 Roadmap

See [FEATURES.md](FEATURES.md) for the full roadmap.

### Completed
- ✅ Chunked embeddings
- ✅ mxbai-embed-large upgrade
- ✅ Open WebUI Notes sync
- ✅ Source attribution in responses ([Source N] → clickable links)
- ✅ LLM cost tracking dashboard (`/cost-dashboard`)
- ✅ Prompt logging for debugging (`CONTEXT_DRIVER_LOG_PROMPTS=true`)
- ✅ Database backup/restore (`make db-backup`, `make db-restore-webui`)
- ✅ **Sub-brains** - Scope searches to subdirectories with `.brainignore` support

### Planned
- MCP Knowledge Base server
- Hybrid search (semantic + BM25)
- Query expansion

## 🐛 Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues.

## 📄 License

MIT
