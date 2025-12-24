# Context Engine Implementation Plan

## Goal
Enhance the Context Engine with a GraphRAG-inspired architecture, separating Raw Source from Derived Graph, and enabling rich entity/relationship extraction and navigation.

## 1. Architecture: Source vs. Graph
We separate the "Source of Truth" into two layers:
1.  **Raw Source (`volumes/raw`)**: Immutable, manually managed markdown files.
2.  **Derived Graph (`volumes/brain`)**: Generated Knowledge Graph containing:
    -   **Enriched Documents**: Text objects with wiki-links and metadata.
    -   **Entity Nodes**: Standalone files (`Entities/Microsoft.md`) generated from extraction.

## 2. Infrastructure Changes
-   **Docker**: Add `volumes/raw` mapping.
-   **Config**: Define `RAW_DIR` and `BRAIN_DIR`.

## 3. Graph Extraction Pipeline
**Ingestor Strategy**:
-   Watch `volumes/raw`.
-   On file change:
    1.  **Extract**: Use LLM to extract Entities (Nodes) and Relationships (Edges).
    2.  **Generate Entity Nodes**: Create/Update files in `volumes/brain/entities/`.
    3.  **Generate Document Node**: Create file in `volumes/brain/documents/` with injected wiki-links and graph metadata.

**Indexer Strategy**:
-   Watch `volumes/brain`.
-   On file change:
    1.  **Index**: Upsert to Vector DB.
    2.  **Embed**: Generate semantic embeddings.
    3.  **Graph**: Store typed edges in `brain.edges`.

## 4. Components

### [Component] Context Driver

#### [MODIFY] [prompts.py]
-   Add `extract_graph_elements(content, title)` to return structured JSON {entities, relationships}.

#### [MODIFY] [db.py]
-   Add `update_edges(note_id, edges)` to store typed relationships.

#### [MODIFY] [main.py]
-   Split logic into `ingest_raw_file` and `index_processed_file`.
-   Implement dual file watchers.

### [NEW] Graph Navigator (CLI)
-   Create `src/graph_navigator.py`.
-   Features: Search, List Edges, Walk Graph.

## 5. Reliability & Backup Strategy
### Disaster Recovery
1.  **Raw Source (`volumes/raw`)**: This is the **primary Source of Truth**.
    -   **Strategy**: Regular file-system backups (e.g., git commit or cron tarball) of this directory are critical. If the DB or Graph crashes, everything can be rebuilt from `volumes/raw`.
2.  **Database (`postgres`)**:
    -   **Strategy**: Use `make db-backup` (wraps `pg_dumpall`). Run this via cron nightly.
    -   **Recovery**: `make flush` (clean slate) -> `make db-restore FILE=...` OR re-ingest from `volumes/raw`.
3.  **Graph Artifacts (`volumes/brain`)**:
    -   **Strategy**: These are derivative. Backing them up speeds up recovery, but is not strictly required if `volumes/raw` exists.
