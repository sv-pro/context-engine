# LLM-Box Status

## Current State: Phase 13 Complete ✅

The RAG-enabled chat system is fully operational with the following capabilities:

### Working Features
- **Open WebUI** running at `http://localhost:3000`
- **RAG Proxy** (`brain-rag` model) with semantic search over local knowledge base
- **55 knowledge base articles** covering the Scrubbing Center Portal documentation
- **Vendor LLM Priority**: OpenAI (gpt-4o-mini) > Anthropic (claude-3-haiku) > Ollama (llama3)
- **Meta-prompt bypass**: Internal Open WebUI tasks skip RAG for efficiency
- **Streaming responses**: Properly formatted SSE for real-time output
- **Database isolation**: Separate schemas for LiteLLM, WebUI, and Brain
- **MCP Server**: Knowledge Base exposed as tools at `/mcp/sse`

### Architecture
```
User → Open WebUI → LiteLLM → Context Driver (RAG) → LiteLLM → LLM
                                    ↓
                             PostgreSQL/pgvector
                             (semantic search)
```

### Known Limitations
1. **Whole-article embeddings**: Large articles may lose semantic specificity
2. **Single-shot retrieval**: No iterative search refinement
3. **Fixed context window**: Top 3 results only

### Quick Start
```bash
make quickstart  # Start all services
make seed-brain  # Load sample KB
```

### Endpoints
| Service        | URL                   |
| -------------- | --------------------- |
| Open WebUI     | http://localhost:3000 |
| LiteLLM        | http://localhost:4000 |
| Context Driver | http://localhost:8000 |

## Last Updated
2024-12-19
