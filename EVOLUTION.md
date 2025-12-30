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

## Chapter 7: The Brain-React Pseudo Model

**Commits: `60e96f4` → `c05fbc4`**

**From Tool Use to Verified Reasoning**

> The `brain-react` pseudo model represents the culmination of the architecture:
> a **DSPy-powered ReAct agent** that thinks, acts, verifies, and learns.

### 🧠 Architecture Overview

The brain-react model is a **pseudo-model** — it appears as a standard LLM in LiteLLM's model list but internally routes to a sophisticated reasoning pipeline:

```
LiteLLM → brain-react → Context Driver → DSPy ReAct Agent → Knowledge Tools
                                              ↓
                                    Verification Layer
                                              ↓
                                    Confidence Assessment
                                              ↓
                                  Investigation Artifact (saved)
```

**Key Insight:** Unlike `brain-rag` (single-pass retrieval), `brain-react` performs *iterative multi-step reasoning* with explicit tool calls, allowing it to:

1. **Search** → find relevant documents
2. **Navigate** → follow knowledge graph relationships  
3. **Extract** → retrieve specific facts, rules, or sections
4. **Verify** → validate answers against the knowledge base
5. **Learn** → save successful investigations as reusable artifacts

### 🔧 The Tool Arsenal (`dspy_tools.py`)

Seven specialized tools give the agent deep access to the knowledge base:

| Tool | Purpose | Use Case |
|------|---------|----------|
| `search_knowledge_base()` | Semantic + keyword search | Initial document discovery |
| `get_facts(subject, predicate)` | Query S-P-O triples | Entity relationships, roles |
| `get_rules(domain, severity)` | Query IF-THEN logic | Procedures, constraints |
| `get_capsule(title)` | Document summary + key points | Quick understanding |
| `get_document_section(title, section)` | Extract full section content | Complete procedures, configs |
| `get_related_documents(title)` | Knowledge graph navigation | Find linked policies, procedures |
| `list_documents(domain, intent)` | Browse the knowledge base | Discovery, exploration |

**Architectural Choice:** Tools return *formatted text*, not raw objects — enabling the LLM to naturally incorporate tool outputs into its reasoning.

### 🔄 The Reasoning Loop (`react_agent.py`)

The `KnowledgeBaseReActAgent` uses DSPy's `dspy.ReAct` pattern:

```python
self.react = dspy.ReAct(
    signature=AnswerQuestion,
    tools=KNOWLEDGE_BASE_TOOLS,
    max_iters=7
)
```

**The AnswerQuestion Signature** contains extensive guidance:

- **Workflow hints:** Search → Get Capsule → Extract Facts → Check Relations
- **Tool selection by question type:** Roles → `get_facts()`, Procedures → `get_document_section()`
- **Accuracy rules:** Match correct table rows, quote values exactly, trust YAML configs

### ✅ Answer Verification (`KnowledgeBaseVerifier`)

Before returning an answer, the agent runs verification:

1. **Extract entities** from the question and draft answer
2. **Query facts** for each entity
3. **Search** the knowledge base for corroboration
4. **Cross-check** with operational rules
5. **Produce verdict:** `Correct`, `Partial`, `Incorrect`, or `Unverified`

**Defensive Logic:** If the verifier says "Incorrect" but the draft contains specific values (numbers, hostnames), the draft is kept — the verifier may lack sufficient context to validate correct answers.

### 📊 Confidence Self-Assessment (`EstimateConfidence`)

A dedicated DSPy signature estimates answer confidence:

```python
class EstimateConfidence(dspy.Signature):
    question: str
    gathered_info: str
    current_answer: str
    
    confidence_score: float  # 0.0 to 1.0
    missing_aspects: str
    recommendation: str  # "finish" or next steps
```

This enables:
- **Early termination** when confidence is high
- **Targeted follow-up** when specific aspects are missing
- **User warnings** when confidence is low (< 0.8)

### 📝 The Investigation Artifact Loop

Every successful ReAct session generates an **Investigation artifact**:

```markdown
---
type: investigation
status: closed
date: 2025-12-30T20:00:00Z
query: "What happens if the DB connection fails?"
tags: [react, investigation, auto-generated]
---

# Investigation: What happens if the DB connection fails?

## Executive Summary
The system pages the DBA on connection failure...

## Reasoning Trace
### Step 1
**Thought:** I need to check for failure handling rules...
**Action:** `get_rules(domain="database", severity="critical")`
**Observation:** > RULE_DB_SSL_001: IF SSL fails THEN page DBA...
```

**Self-Improvement Loop:**
1. Investigation saved to `volumes/raw/investigations/`
2. Watchdog detects the new file
3. File ingested into knowledge base (as `type: investigation`)
4. **Neurosymbolic distillation skipped** — investigations don't generate new facts/rules to prevent hallucination loops
5. Investigation becomes searchable context for future questions

### 🛡️ Stability Improvements

Recent commits hardened the system:

- **Thread-safe DSPy:** `dspy.context(lm=lm)` per-request configuration
- **Trajectory extraction:** Robust parsing of DSPy's dict-format ReAct results
- **Empty trace handling:** Fallback to rationale capture when trajectory parsing fails
- **Typed wikilinks:** `[[Entity]](type)` syntax for richer graph navigation
- **Investigation filtering:** Skipped in search to prevent context pollution

### ⚡ Performance Characteristics

| Metric | brain-rag | brain-react |
|--------|-----------|-------------|
| Latency | 1-3s | 5-30s |
| Accuracy (complex) | 60% | 85%+ |
| Tool calls | 0 | 3-7 |
| Self-verification | ❌ | ✅ |
| Learning | ❌ | ✅ (Investigation) |

**When to use `brain-react`:**
- Multi-hop questions (A relates to B which affects C)
- Procedure lookups requiring section extraction
- Questions about relationships between entities
- Complex troubleshooting inquiries

---

## The Evolution Arc

```
Infrastructure → Memory → Search → RAG → GraphRAG → Neurosymbolic → Agentic → Verified ReAct
      ↓            ↓        ↓       ↓        ↓            ↓            ↓           ↓
    Docker       pgvector  Hybrid  Citations  Entities    DSPy        ReAct    brain-react
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
| **brain-react** | Verified reasoning with confidence assessment |
| **Investigation artifacts** | Self-learning through reasoning traces |

---

> **6 months ago I thought I was building a chatbot.**
> **Turns out — I was building a new category.**
>
> Introducing: **Context Engine** — a neuro-symbolic system
> that turns raw documents into executable knowledge,
> without fine-tuning.
>
> From Docker → pgvector → RAG → GraphRAG → DSPy → Lore Extraction → ReAct → **`brain-react`**.
>
> **The future isn't retrieval.**
> **It's verified reasoning over distilled knowledge.** 🥃🧠✅

