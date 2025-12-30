# Part 3: RAG Evolution

> *From simple search to intelligent retrieval*

**Commits:** `f4950a9` → `472c160`

---

## The Chunking Problem

Early semantic search had a flaw: long documents produced averaged embeddings that matched nothing well. A 5000-word operations manual would return for queries about SSL, DNS, *and* databases — because it mentioned all of them.

The solution: **chunked embeddings**.

## Chunked Embeddings

Split documents into overlapping chunks:

```python
def chunk_document(content: str, chunk_size: int = 500, overlap: int = 50):
    words = content.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    return chunks
```

Each chunk gets its own embedding. Now a query about "SSL renewal" matches the specific paragraph about SSL, not the whole document.

## Hybrid Search

Pure vector search has blind spots. If someone searches "NGINX config," they expect documents with those exact words — even if semantically, "web server configuration" is closer.

Enter **hybrid search**: combine vector similarity with keyword matching (BM25), then fuse results with **Reciprocal Rank Fusion (RRF)**.

```python
def hybrid_search(query: str, limit: int = 5):
    # Vector search
    vector_results = semantic_search(query, limit=limit*2)
    
    # Keyword search (BM25)
    keyword_results = keyword_search(query, limit=limit*2)
    
    # RRF fusion
    return reciprocal_rank_fusion(
        [vector_results, keyword_results],
        k=60
    )
```

RRF is elegant:

```python
def reciprocal_rank_fusion(result_lists, k=60):
    scores = defaultdict(float)
    
    for results in result_lists:
        for rank, doc in enumerate(results):
            scores[doc.id] += 1 / (k + rank + 1)
    
    return sorted(scores.items(), key=lambda x: -x[1])
```

Documents that appear high in *both* lists get boosted. Documents that only appear in one still contribute.

## Real Citations

RAG without citations is hallucination with extra steps. The system needed to prove its sources.

```python
def build_context_for_query(query):
    results = hybrid_search(query, limit=5)
    
    context_parts = []
    source_mapping = {}
    
    for i, (doc, score) in enumerate(results):
        source_num = i + 1
        source_mapping[source_num] = doc.title
        
        context_parts.append(
            f"--- Source {source_num}: {doc.title} ---\n{doc.content}"
        )
    
    return '\n\n'.join(context_parts), source_mapping
```

The system prompt instructs the LLM:

> You MUST cite sources using [Source N] notation. Do NOT generate information beyond what is in the context.

Post-processing replaces `[Source 1]` with clickable markdown links: `[SSL_Certificates.md](/brain/SSL_Certificates.md)`.

## Cost Tracking

With API calls to OpenAI for every embedding and completion, costs matter. A Chart.js dashboard tracks:

- Tokens per request (input/output)
- Cost per operation
- Daily/weekly aggregates

```python
def log_request(operation, model, input_tokens, output_tokens, latency_ms):
    db.execute("""
        INSERT INTO brain.cost_log 
        (operation, model, input_tokens, output_tokens, cost_usd, latency_ms)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, [operation, model, input_tokens, output_tokens, 
          calculate_cost(model, input_tokens, output_tokens), latency_ms])
```

## The RAG Proxy

The Context Driver became a full **OpenAI-compatible proxy**:

```python
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    user_query = body["messages"][-1]["content"]
    
    # 1. Build context from knowledge base
    context, sources = build_context_for_query(user_query)
    
    # 2. Inject context into system prompt
    system_prompt = build_system_prompt(context)
    
    # 3. Forward to real LLM
    response = await forward_to_llm(body, system_prompt)
    
    # 4. Post-process citations
    return add_source_links(response, sources)
```

Point LiteLLM at this proxy, and every chat message gets augmented with relevant context.

## Lessons Learned

1. **Chunking is essential** — embed paragraphs, not pages
2. **Hybrid search beats pure vector** — keywords still matter
3. **RRF is simple and effective** — no ML required for fusion
4. **Citations build trust** — always show your sources
5. **Track costs early** — before they become a surprise

## What's Next

The system now does intelligent retrieval. But documents are still flat. What if they formed a **graph** of relationships?

Part 4 introduces **MCP, GraphRAG, and enterprise integrations**.

---

[← Previous: Memory & Intelligence](./02-memory-and-intelligence.md) | [Back to Index](./README.md) | [Next: Enterprise Features →](./04-enterprise-features.md)
