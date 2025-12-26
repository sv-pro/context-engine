# Context Engine Current State

This document describes the current implementation based on the code in
`context_driver/src` and top-level scripts. It is a code-first snapshot.

## System overview
- Open WebUI sends chat requests to LiteLLM, which is configured to call the
  Context Driver as a RAG proxy.
- Context Driver builds context from a local knowledge base and proxies
  requests to the selected LLM provider (OpenAI, Anthropic, or Ollama).
- PostgreSQL + pgvector stores documents, chunks, and graph edges.
- File watchers keep the knowledge base and database in sync.

## Data flow
1. Raw ingestion (`/app/raw`)
   - `main.py` watches RAW files and runs LLM extraction.
   - Extracted graph data (entities and relationships) is written to
     `/app/brain/documents` and `/app/brain/entities`.
2. Indexing (`/app/brain`)
   - `main.py` watches the graph artifacts and calls `process_file`.
   - Notes are upserted into `brain.notes`.
   - Chunks are created in `brain.chunks` with embeddings.
   - Typed edges are written to `brain.edges`.
3. Retrieval
   - Requests call `retrieve_context_docs` and `build_context_for_query`.
   - Context is injected into a strict system prompt before LLM completion.

## Storage schema (brain)
- `brain.notes`: file_path, title, content, metadata, note-level embedding.
- `brain.chunks`: per-note chunks with section, metadata, and embeddings.
- `brain.edges`: typed relationships (source_id -> target_title).
- `brain.cost_log`: LLM request cost tracking and metadata.

## Core modules
- `context_driver/src/main.py`
  - FastAPI app and RAG pipeline
  - File watchers for RAW and BRAIN
  - Retrieval strategies and graph traversal
  - Context and chat completion endpoints
- `context_driver/src/db.py`
  - Schema creation (notes, chunks, edges, cost_log)
  - Vector, keyword, graph, and RRF search
- `context_driver/src/chunker.py`
  - Markdown chunking with overlap and section tracking
- `context_driver/src/parser.py`
  - Frontmatter parsing and wikilink extraction
- `context_driver/src/enricher.py`
  - Frontmatter generation and metadata enrichment
- `context_driver/src/prompts.py`
  - LLM prompts for graph extraction and keyword extraction
- `context_driver/src/tools_api.py`
  - OpenAPI tools for search, article retrieval, and listing
- `context_driver/src/mcp_server.py`
  - MCP tool server for search and article retrieval
- `context_driver/src/note_sync.py`
  - Open WebUI note sync to `/app/brain/webui_notes`
- `context_driver/src/cost_tracker.py`
  - Cost estimation, persistence, and dashboard endpoints
- `context_driver/src/benchmark.py`
  - Retrieval evaluation metrics and evidence pack generation
- `context_driver/src/benchmark_runner.py`
  - CLI runner for strategy benchmarking
- `context_driver/src/graph_navigator.py`
  - CLI for inspecting nodes and edges
- `context_driver/src/cli.py`
  - CLI for `/v1/context`
- `context_driver/src/jira_tools/`
  - Jira issue fetcher and helpers

## Retrieval strategies
- `semantic`: vector similarity over chunks.
- `keyword`: PostgreSQL full-text search over chunks.
- `hybrid`: RRF over semantic and keyword results.
- `graph`: iterative traversal over typed edges and wikilinks.
- `super_hybrid`: RRF plus iterative graph traversal.
- `adaptive`: LLM classifier selects semantic, graph, or super_hybrid.

## API surface
- Context Driver (port 8000)
  - `POST /v1/chat/completions` (RAG proxy)
  - `POST /v1/context` (context preview)
  - `GET /health`
  - `GET /cost-dashboard` and `/api/costs/*`
  - `POST /sync-notes`, `GET /sync-notes/status`
  - `GET /mcp/sse`, `POST /mcp/messages`
  - `GET /tools/openapi.json`
- Tools endpoints
  - `POST /tools/search`, `GET /tools/search`
  - `GET /tools/article/{title_or_path}`
  - `GET /tools/articles`
  - `GET /tools/related/{title_or_path}`

## Integrations
- Embedding providers: Ollama or LiteLLM/OpenAI via `EMBEDDING_CONFIGURATION`.
- Chat providers: OpenAI, Anthropic, or Ollama (priority based on API keys).
- Open WebUI note sync via `WEBUI_DATABASE_URL`.
- Jira ingestion scripts via `context_driver/src/jira_tools`.

## Evaluation and test artifacts
- `context_driver/test_queries.json` drives the benchmark suite.
- Test design docs define multi-hop and graph-only test cases.
- `bm_*.md` capture benchmark outputs for strategy comparisons.

## Notable gaps or mismatches (code-level)
- `tools_api.py` and `mcp_server.py` query `brain.links`, but the schema
  defines `brain.edges` and edge updates flow through `update_edges`.
- Query expansion is described in docs but not implemented in code.
- Open WebUI knowledge (separate from notes) is not integrated.
- Note sync handles inserts and updates but not deletions.
- Graph extraction uses a hard-coded chat model (`gpt-4o-mini`) and does not
  use the runtime model selection logic.
