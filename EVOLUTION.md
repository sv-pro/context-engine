# Context Engine: Project Evolution

> **Over the past 6 months, I accidentally built a new class of system.**
> 
> What started as a Dockerized chat UI slowly evolved into something else:
> an engine that distills raw documents into **executable domain knowledge**.
> 
> Not a chatbot.
> Not RAG.
> Not Graph search.
> 
> But a **neuro-symbolic context engine** — capable of extracting facts, rules, entities, and domain lore and executing them without fine-tuning.

---

## Chapter 1: The Foundation

**Commits: `2c08137` → `6021270`**

The project began with infrastructure. A `docker-compose.yml` brought together **Open WebUI** (the chat interface) and **LiteLLM** (the LLM router). Two services, one vision: a local AI assistant.

Recognizing that nobody wants to remember long Docker commands, a **Makefile** appeared—`make start`, `make stop`, `make status`. Small refinements followed: environment checks, endpoint displays, and smart status reporting that only shows what's actually running.

---

## Chapter 2: Memory & Intelligence

**Commits: `f0eceee` → `f109256`**

**Teaching the System to Remember**

PostgreSQL and Redis joined the stack. The system could now *remember* conversations and cache responses. But raw storage wasn't enough.

The heart of the project emerged: a **Python Context Driver** that:
- Watches markdown files with `watchdog`
- Parses frontmatter metadata
- Stores embeddings in **pgvector**

The AI could now search its own knowledge base semantically. Ollama integration, readiness checks, and datetime serialization fixes polished the foundation.

---

## Chapter 3: RAG Evolution

**Commits: `f4950a9` → `472c160`**

**From Simple Search to Intelligent Retrieval**

A full **OpenAI-compatible RAG proxy** emerged with vendor LLM priority (OpenAI → Anthropic → Ollama). SSE streaming was fixed, and the "brain" got its own database namespace.

Documents were split into **500-token chunks** with overlap for better retrieval. The embedding model upgraded to `mxbai-embed-large`.

**Cost tracking** arrived with a Chart.js dashboard. LiteLLM spend logs were integrated. The system could now tell you exactly what each query cost.

Citations became real: `[Source 1: SSL_Certificates.md]`. No more hallucinated sources.

Open WebUI notes automatically flowed into the knowledge base via background polling.

The search engine became sophisticated: **semantic + keyword (BM25) + RRF fusion**. Configurable via environment variable.

---

## Chapter 4: Enterprise Features

**Commits: `35c63ab` → `413ccd2`**

**Scaling to Real Workloads**

The system learned to speak **Model Context Protocol (MCP)** for tool integration. Documents gained human-readable keyword tags as "semantic embeddings."

A rigorous **benchmark system** emerged with P@K, MRR, nDCG metrics. Reasoning models (o1/o3) got special adapters.

The project was renamed from "LLM-Box" to **Context Engine**—reflecting its true purpose.

Related links moved to frontmatter, embeddings became configurable, and a `db-reindex` command appeared for model swaps.

The system exposed itself as an **OpenAPI server** for Open WebUI function calling.

Enterprise knowledge sources arrived: **Jira issues** could be fetched, converted to markdown, and ingested.

Knowledge became a **graph**. Entities, relationships, and iterative multi-hop retrieval replaced flat vector search.

---

## Chapter 5: The Neurosymbolic Turn

**Commits: `588eefd` → `f04d8eb`**

**Beyond Embeddings: Structured Knowledge**

> Then came the breakthrough:
> raw documents shouldn't be "searched" — they should be ***distilled***.

🥃 **The 3-pass system emerged:**

1️⃣ **Condense meaning** — Extract summary, key points, intent, domain

2️⃣ **Extract structured capsules and facts** — Subject-predicate-object triples

3️⃣ **Derive executable rules and invariants** — IF-THEN logic with severity

This was the moment Context Engine stopped being a RAG proxy
and became a **knowledge execution layer.**

**DSPy signatures** replaced manual prompts. Typed inputs/outputs. Optimizable. Testable.

The full implementation brought:
- Training example collection for prompt optimization
- BootstrapFewShot/MIPROv2 optimizer support
- REST APIs for querying facts, rules, and capsules
- 30+ automated tests

---

## Chapter 6: Agentic Reasoning & Scoped Knowledge

**Commits: `16365cf` → `75c2831`**

**From Passive Retrieval to Active Reasoning**

> The system learned to **think**.

🧠 **ReAct Integration:**

The DSPy ReAct (Reasoning + Acting) agent arrived as a new **pseudo-model**:
- `brain-rag` — Single-pass retrieval (fast, simple)
- `brain-react` — Multi-step reasoning with tool use (thorough, complex)

The ReAct agent iteratively:
1. **Thinks** about what information is needed
2. **Acts** by calling knowledge base tools (search, facts, rules)
3. **Observes** results and continues reasoning
4. Returns comprehensive answers with visible reasoning trace

🎯 **Sub-Brains:**

Knowledge became **scopable**. Any subdirectory can become its own context:

```bash
# Search only within a sub-brain
curl -d '{"query": "...", "sub_path": "projects/myapp"}'

# Configure default scope via environment
BRAIN_SUBDIR=projects/myapp
```

`.brainignore` files prevent sub-brains from being indexed with their parent—enabling independent knowledge domains.

**The API expanded:**
- `/tools/sub-brains` — Discover available knowledge scopes
- All search/list endpoints accept `sub_path` parameter
- `Tools.scoped("path")` creates child instances in Python

**Demo sub-brain** with 8 interconnected Acme Cloud docs showcases multi-step reasoning.

---

## The Evolution Arc

```
Infrastructure → Memory → Search → RAG → GraphRAG → Neurosymbolic → Agentic
     ↓            ↓        ↓       ↓        ↓            ↓            ↓
   Docker       pgvector  Hybrid  Citations  Entities    DSPy        ReAct
```

---

## Key Milestones

| Milestone | Capability Added |
|-----------|-----------------|
| Docker + Open WebUI | Chat interface with LLM routing |
| pgvector | Semantic document search |
| Chunked embeddings | Fine-grained retrieval |
| Hybrid search | BM25 + vector + RRF fusion |
| Cost tracking | Usage visibility and billing |
| MCP server | Tool integration for agents |
| GraphRAG | Entity extraction and graph traversal |
| DSPy | Typed, optimizable prompt execution |
| Neurosymbolic | Facts, rules, and capsule extraction |
| **ReAct reasoning** | Multi-step thinking with tool use |
| **Sub-brains** | Scoped knowledge domains |

---

> **6 months ago I thought I was building a chatbot.**
> **Turns out — I was building a new category.**
>
> Introducing: **Context Engine** — a neuro-symbolic system
> that turns raw documents into executable knowledge,
> without fine-tuning.
>
> From Docker → pgvector → RAG → GraphRAG → DSPy → Lore Extraction → **ReAct Reasoning**.
>
> **The future isn't retrieval.**
> **It's reasoning over distilled knowledge.** 🥃🧠
