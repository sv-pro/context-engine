# Context Engine: From Chatbot to Knowledge Engine

> **A 7-Part Series on Building a Neurosymbolic AI System**

This article series documents the evolution of Context Engine — a system that started as a simple Dockerized chat UI and evolved into a **neurosymbolic context engine** capable of extracting facts, rules, entities, and domain knowledge from raw documents.

---

## The Series

### Part 1: [The Foundation](./01-the-foundation.md)
*Docker, Open WebUI, and the Makefile that started it all*

Set up the infrastructure foundation with Docker Compose, bringing together Open WebUI and LiteLLM. Learn how a simple Makefile transformed developer experience.

**Key Topics:** Docker Compose, LiteLLM, Makefile automation

---

### Part 2: [Memory & Intelligence](./02-memory-and-intelligence.md)
*Teaching the system to remember with PostgreSQL and pgvector*

Add persistence with PostgreSQL and Redis, then build a Python Context Driver that watches markdown files and stores embeddings for semantic search.

**Key Topics:** pgvector, watchdog, embeddings, semantic search

---

### Part 3: [RAG Evolution](./03-rag-evolution.md)
*From simple search to intelligent retrieval*

Build a full OpenAI-compatible RAG proxy with chunked embeddings, hybrid search (BM25 + vector + RRF fusion), cost tracking, and real citations.

**Key Topics:** Hybrid search, chunking, citations, cost tracking

---

### Part 4: [Enterprise Features](./04-enterprise-features.md)
*Scaling to real workloads with MCP and GraphRAG*

Integrate Model Context Protocol for tool use, add rich metadata extraction, and transform flat documents into a traversable knowledge graph.

**Key Topics:** MCP, GraphRAG, entity extraction, Jira integration

---

### Part 5: [The Neurosymbolic Turn](./05-neurosymbolic-turn.md)
*Beyond embeddings: structured knowledge extraction*

The breakthrough moment — using DSPy signatures to distill raw documents into structured primitives: Capsules (summaries), Facts (S-P-O triples), and Rules (IF-THEN logic).

**Key Topics:** DSPy, knowledge distillation, facts, rules, capsules

---

### Part 6: [Agentic Reasoning & Sub-Brains](./06-agentic-reasoning.md)
*From passive retrieval to active thinking*

Introduce the ReAct agent architecture with iterative reasoning and tool use. Add sub-brains for scoped knowledge domains.

**Key Topics:** ReAct, DSPy agents, sub-brains, scoped knowledge

---

### Part 7: [The Brain-React Pseudo Model](./07-brain-react-architecture.md)
*Verified reasoning with confidence assessment*

Deep dive into the brain-react pseudo model — the culmination of the architecture featuring multi-step reasoning, answer verification, confidence self-assessment, and self-learning through investigation artifacts.

**Key Topics:** brain-react, verification, confidence, investigations

---

## The Evolution Arc

```
Infrastructure → Memory → Search → RAG → GraphRAG → Neurosymbolic → Agentic → Verified ReAct
      ↓            ↓        ↓       ↓        ↓            ↓            ↓           ↓
    Docker       pgvector  Hybrid  Citations  Entities    DSPy        ReAct    brain-react
```

---

## Who Is This For?

- **AI Engineers** building production RAG systems
- **Knowledge Management practitioners** exploring neurosymbolic approaches
- **Developers** wanting to understand modern AI architectures
- **Teams** evaluating alternatives to vanilla RAG pipelines

---

## Getting Started

Clone the repository and run:

```bash
git clone https://github.com/your-org/context-engine.git
cd context-engine
make quickstart
```

Then explore each article in order, or jump directly to the topics that interest you.

---

> **The future isn't retrieval. It's verified reasoning over distilled knowledge.** 🥃🧠✅
