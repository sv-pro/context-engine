# Part 4: Enterprise Features

> *Scaling to real workloads with MCP and GraphRAG*

**Commits:** `35c63ab` → `413ccd2`

---

## Beyond Personal Notes

The system worked great for personal knowledge bases. But enterprise scenarios demand more:

- **Tool integration** — LLMs need to call external APIs
- **Rich metadata** — Documents need structured, queryable tags
- **Graph relationships** — Flat search isn't enough for connected knowledge
- **External data sources** — Jira, Confluence, internal wikis

## Model Context Protocol (MCP)

MCP is an emerging standard for LLM tool integration. Instead of prompt-hacking tools, you expose them as typed schemas.

```python
@mcp_server.tool()
def search_knowledge_base(query: str, limit: int = 5) -> list[dict]:
    """Search the knowledge base for relevant documents."""
    return perform_search(query, limit)

@mcp_server.tool()
def get_article(title: str) -> str:
    """Retrieve the full content of an article."""
    return load_article(title)
```

Any MCP-compatible client can now discover and use these tools without custom integration.

## Rich Metadata Extraction

Documents gained **human-readable embeddings** — keyword tags extracted by LLM:

```markdown
---
title: SSL Certificate Renewal
keywords: [ssl, tls, certificates, letsencrypt, renewal, https]
domain: infrastructure
intent: procedure
---
```

These aren't just for display. They enable:
- Faceted search by domain
- Intent-based routing (procedures vs. policies)
- Graph edge typing

## GraphRAG: Knowledge as a Graph

The breakthrough wasn't better embeddings — it was **relationships**.

### Entity Extraction

Every document gets parsed for entities:

```python
def extract_entities(content: str) -> list[Entity]:
    # Use LLM to identify entities
    prompt = f"""Extract named entities from this document.
    Return as JSON: [{{"name": "...", "type": "..."}}]
    
    {content}
    """
    return llm_extract(prompt)
```

### Relationship Mapping

Wikilinks (`[[Target]]`) become explicit graph edges:

```sql
CREATE TABLE brain.edges (
    source_id INTEGER REFERENCES brain.notes(id),
    target_title TEXT,
    type TEXT,  -- 'wikilink', 'see_also', 'prerequisite'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Iterative Graph Retrieval

Instead of one search, the system *traverses*:

```python
def graph_retrieval(query: str, max_hops: int = 3):
    # 1. Seed with vector search
    seeds = semantic_search(query, limit=3)
    
    visited = set()
    results = []
    frontier = seeds
    
    for hop in range(max_hops):
        next_frontier = []
        
        for doc in frontier:
            if doc.id in visited:
                continue
            visited.add(doc.id)
            results.append(doc)
            
            # Follow links
            linked = get_linked_documents(doc.id)
            next_frontier.extend(linked)
        
        frontier = next_frontier
    
    return results
```

A query about "database connection" might:
1. Find `Database_Configuration.md` (vector match)
2. Follow link to `Connection_Pooling.md`
3. Follow link to `PostgreSQL_Tuning.md`
4. Return all three for complete context

## Jira Integration

Enterprise knowledge lives in many systems. A script fetches Jira issues and converts them to markdown:

```bash
./fetch-jira-issues.sh --project INFRA --output volumes/raw/jira/
```

Each issue becomes a searchable document:

```markdown
---
title: INFRA-1234
type: jira-issue
status: resolved
---

# INFRA-1234: SSL Certificate Expired

## Description
Production certificates expired causing outage...

## Resolution
Implemented auto-renewal with certbot...
```

Now the AI knows about past incidents, their resolutions, and can cite them.

## Benchmark System

How do you measure RAG quality? A benchmark system emerged with:

- **P@K** — Precision at K (how many of top-K are relevant?)
- **MRR** — Mean Reciprocal Rank (where does the correct answer appear?)
- **nDCG** — Normalized Discounted Cumulative Gain

```python
def evaluate_query(query: str, expected_docs: list[str]):
    results = search(query, limit=10)
    
    # Calculate metrics
    precision_at_5 = len(set(results[:5]) & set(expected_docs)) / 5
    
    for i, doc in enumerate(results):
        if doc in expected_docs:
            mrr = 1 / (i + 1)
            break
    
    return {"p@5": precision_at_5, "mrr": mrr}
```

## Lessons Learned

1. **MCP is the future of tool integration** — invest in it now
2. **Graphs beat flat search** — relationships matter
3. **Integrate with existing systems** — Jira, Confluence, etc.
4. **Measure retrieval quality** — benchmarks reveal blind spots
5. **Metadata enables filtering** — domain/intent routing is powerful

## What's Next

We have rich retrieval and graph traversal. But we're still just *finding* documents — not *understanding* them.

Part 5 introduces the **neurosymbolic turn** — extracting structured knowledge from raw text.

---

[← Previous: RAG Evolution](./03-rag-evolution.md) | [Back to Index](./README.md) | [Next: The Neurosymbolic Turn →](./05-neurosymbolic-turn.md)
