# Context Engine Plan

This plan consolidates the existing documentation into a single roadmap and
compares those goals to `CURRENT_STATE.md`.

## Inputs reviewed
- `README.md`
- `FEATURES.md`
- `STATUS.md`
- `TASK_STATUS.md`
- `STABILITY_TRACKING.md`
- `IMPLEMENTATION_PLAN.md`
- `ADAPTIVE_STRATEGY.md`
- `WALKTHROUGH.md`
- `CONTEXT_DRIVER_LAB.md`
- `todo.md`
- `TEST_DESIGN.md`, `TEST_DESIGN_AGGREGATION.md`, `GRAPH_TEST_DESIGN.md`

## Delta vs CURRENT_STATE.md
The code already implements GraphRAG ingestion, chunking, MCP tools, hybrid
search, and cost tracking. The remaining gaps called out in docs and notes are:
- Query expansion is still missing.
- Related-links tooling is broken (tools and MCP reference `brain.links`).
- Contradiction handling test (T5) is still pending.
- Open WebUI Knowledge (distinct from notes) is not integrated.
- External source ingestion (Jira/Confluence/Bitbucket) is partial.
- Several docs are out of date relative to the current pipeline.

## Relevance decisions (docs to plan mapping)

Still relevant to keep or execute:
- Query expansion (FEATURES.md, README.md).
- External ingestion (FEATURES.md, todo.md, jira_tools).
- Open WebUI Knowledge integration (FEATURES.md, todo.md).
- Retrieval evaluation and stability tests (TASK_STATUS.md,
  STABILITY_TRACKING.md, TEST_DESIGN*.md).
- Fix result reference links and broken related-links endpoints (todo.md).
- Model and strategy routing experiments (todo.md).
- Adaptive strategy benchmarking and tuning (ADAPTIVE_STRATEGY.md).

No longer relevant as plan work (already done or outdated):
- Source vs graph separation, entity node generation, and graph traversal
  pipeline (IMPLEMENTATION_PLAN.md, WALKTHROUGH.md).
- Chunked embeddings and hybrid search implementation (FEATURES.md, README.md).
- "Whole-article embeddings only" limitation and "single-shot retrieval"
  limitations (STATUS.md are stale).
- Planned MCP server (README.md is outdated; it is implemented).

## Unified plan (epics)

Epic 1: Documentation alignment
- Update `README.md`, `STATUS.md`, and `FEATURES.md` to reflect the current
  GraphRAG pipeline, search strategies, and endpoints.
- Update `CONTEXT_DRIVER_LAB.md` to match RAW/BRAIN ingestion and edges schema.
- Replace or archive stale "planned" items that are already implemented.

Epic 2: Retrieval quality and grounding
- Implement query expansion for search strategies that benefit from it.
- Fix source reference links across `/v1/chat/completions`, tools, and MCP so
  citations resolve consistently.
- Repair related-links retrieval to use `brain.edges` or add a compatible view.
- Re-run benchmark suite and capture new baselines in `bm_*.md`.

Epic 3: Graph reasoning robustness
- Implement and validate contradiction handling (T5) and update stability docs.
- Fold graph-only tests (`GRAPH_TEST_DESIGN.md`) into benchmarks or CI scripts.
- Normalize or curate edge types to reduce graph noise in traversal.

Epic 4: Ingestion and integrations
- Integrate Open WebUI Knowledge content alongside notes.
- Expand external ingestion (Jira/Confluence/Bitbucket) with repeatable scripts
  and source metadata tagging.
- Define a durable pipeline for external sources (scheduling, idempotency,
  and deletion handling).

Epic 5: Agentic workflows and model routing
- Evaluate MCP + reasoning model workflows and the "triad architecture"
  experiments noted in `todo.md`.
- Add model/strategy/KB routing rules (pseudo-model selection per task).
- Decide whether to keep LiteLLM hook-based routing or proxy routing as the
  primary pattern and document it.

Epic 6: Neurosymbolic knowledge extraction and execution
- Define a symbolic schema (entities, relations, rules, constraints) aligned to
  the current graph extraction output.
- Add a rule or query layer that can execute symbolic reasoning against the
  extracted graph (and feed results back into retrieval).
- Build a verification loop that compares symbolic results against retrieved
  text evidence before answers are generated.
