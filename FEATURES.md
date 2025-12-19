# Future Features

## Phase 2: Enhanced RAG

### 1. Chunked Embeddings [DONE]
**Problem**: Large articles produce embeddings that blur semantic specificity.

**Solution**: Split articles into overlapping chunks (~500 tokens each).

```sql
-- New schema
CREATE TABLE brain.chunks (
    id SERIAL PRIMARY KEY,
    note_id INTEGER REFERENCES brain.notes(id),
    chunk_index INTEGER,
    content TEXT,
    embedding vector(768),
    metadata JSONB  -- {section: "Certificate Storage", start_line: 42}
);
```

**Benefits**:
- More precise semantic matching
- Returns exact paragraph that answers the question
- Better handling of long documents

---

### 2. MCP Knowledge Base Server
**Problem**: One-shot retrieval limits the LLM's ability to explore the KB.

**Solution**: Expose KB as an MCP tool server.

```typescript
// MCP Tools
search_kb(query: string, limit?: number) → ChunkResult[]
get_article(title: string) → ArticleContent
list_articles() → ArticleMetadata[]
get_related(title: string) → RelatedArticles[]
```

**Benefits**:
- LLM can iteratively search and refine
- Multi-hop reasoning across documents
- User can see which tools the LLM used

---

### 3. Hybrid Search
**Problem**: Pure semantic search misses exact keyword matches.

**Solution**: Combine vector similarity with BM25 full-text search.

```sql
-- Hybrid ranking
SELECT title, content,
       0.7 * semantic_score + 0.3 * bm25_score AS hybrid_score
FROM brain.notes
ORDER BY hybrid_score DESC;
```

---

### 4. Query Expansion
**Problem**: User queries may use different vocabulary than KB content.

**Solution**: Use LLM to expand queries before search.

```
User: "Where are certs stored?"
Expanded: "certificate storage location encryption vault database"
```

---

### 5. Citation & Source Tracking
**Problem**: Hard to verify which KB article answered a question.

**Solution**: Include source citations in responses.

```json
{
  "content": "Private keys are stored in HashiCorp Vault...",
  "sources": [
    {"title": "SSL_Certificates", "section": "Certificate Storage", "similarity": 0.89}
  ]
}
```

---

### 6. LLM Cost Tracking & Logging [DONE]
**Problem**: No visibility into actual LLM API costs across all operations.

**Solution**: Track and log costs for ALL paid LLM requests:

**Operations to Track**:
- Embedding generation (per-chunk and per-note)
- Chat completions (RAG prompts + meta-prompts)
- Model selection (OpenAI vs Anthropic vs Ollama)

**Implementation**:
```python
# Cost estimator per 1K tokens
COSTS = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "text-embedding-3-small": {"input": 0.00002},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
}
```

**Database Table**:
```sql
CREATE TABLE brain.cost_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    operation TEXT,  -- 'embedding', 'chat', 'meta-prompt'
    model TEXT,
    input_tokens INT,
    output_tokens INT,
    estimated_cost DECIMAL(10, 6),
    metadata JSONB
);
```

**Benefits**:
- Daily/weekly cost reports
- Per-article ingestion cost
- Chat vs embedding cost breakdown
- Alert on cost spikes

---

## Phase 3: Advanced Features


### 7. Open WebUI Notes Import [DONE]
**Problem**: Adding knowledge requires creating markdown files manually.

**Solution**: Import notes created in Open WebUI directly into the brain KB.

**Open WebUI Notes Schema** (webui.note table):
| Column  | Type | Purpose      |
| ------- | ---- | ------------ |
| id      | text | Primary key  |
| title   | text | Note title   |
| data    | json | Note content |
| user_id | text | Creator      |

**Implementation**:
1. Add polling/trigger to watch `webui.note` table
2. Convert note `data` JSON to markdown
3. Ingest into `brain.notes` and create chunks
4. Handle updates and deletions (sync)

**Future**: Also import Open WebUI "Knowledge" for structured data.

---



### 6. Auto-Ingestion from External Sources
- Watch Confluence/Notion pages
- Import from GitHub wikis
- Scrape internal documentation sites

### 7. Feedback Loop
- Track which answers were helpful
- Use feedback to improve retrieval ranking
- A/B test different chunking strategies

### 8. Multi-Modal KB
- Index images and diagrams
- OCR for scanned documents
- Video transcript search

---

## Priority Order
1. ✅ Chunked Embeddings
2. ✅ LLM Cost Tracking (Projected + LiteLLM Actuals)
3. ✅ Open WebUI Notes Import
4. ✅ Source Attribution & Citations
5. MCP Knowledge Base Server
6. Hybrid Search
7. Query Expansion
