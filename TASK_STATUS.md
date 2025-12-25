# Entity Extraction and Graph Reasoning

- [x] Explore codebase
    - [x] Understand "brain scan" context <!-- id: 0 -->
    - [x] Analyze existing parsing and chunking logic <!-- id: 1 -->
- [x] Implement Source/Graph separation
    - [x] Update infrastructure (docker-compose, config) <!-- id: 9 -->
    - [x] Create RECOVERY.md <!-- id: 10 -->
    - [x] Create entity node generation logic <!-- id: 7 -->
- [x] Implement Graph Debugger (CLI)
    - [x] Create graph_navigator.py <!-- id: 8 -->
- [x] Verify implementation
    - [x] Create test raw file <!-- id: 11 -->
    - [x] Check graph extraction and db <!-- id: 12 -->
    - [x] Run navigator <!-- id: 13 -->
    - [x] LLM-based extraction <!-- id: 2 -->
    - [x] GraphRAG-inspired strategy <!-- id: 5 -->
    - [-] Regex/heuristic based <!-- id: 3 -->
- [x] Multi-Hop Reasoning & Iterative Retrieval
    - [x] Design "Phantom Protocol" test case (Sequential)
    - [x] Design "Shadow Board" test case (Aggregation/Distributed)
    - [x] Implement relationships in Entity Nodes
    - [x] Implement Entity Merging (prevent overwrite)
    - [x] Implement Iterative Retrieval (Recursive Link Following)
    - [x] Verify Sequential Query success (Phantom Protocol)
    - [x] Verify Aggregation Query success (Shadow Board)
- [x] Stability & Regression Testing
    - [x] Create STABILITY_TRACKING.md
    - [x] Test T3: Implicit Connection (Pass)
    - [x] Test T4: Temporal Reasoning (Pass)
    - [x] Achieve Stability (2 consecutive passes)
- [ ] Refinement
    - [ ] Test T5: Contradiction Handling


> [!IMPORTANT]
> **USER RULE**: Always copy artifacts to the project root before requesting review. Do not link to .gemini directory.
