# GraphRAG Implementation Walkthrough

## Overview
We have successfully transformed the Context Engine into a GraphRAG system. 

## Changes
1.  **Source/Graph Separation**:
# Walkthrough - GraphRAG Entity Extraction & Multi-Hop Reasoning

## Core Components Implemented
1. **Dual-Pipeline Architecture**:
   - `RAW_DIR` (`volumes/raw`): Immutable source documents.
   - `BRAIN_DIR` (`volumes/brain`): Derivable graph artifacts (Entities & Enriched Docs).
   - **Auto-Ingestion**: `main.py` watchers trigger LLM-based Graph Extraction upon new file creation.

2. **Graph Extraction Logic**:
   - **Prompts**: `extract_graph_elements` uses `gpt-4o-mini` to identify specialized Entities (Concepts, People, Locations) and Typed Relationships.
   - **Entity Merging**: Logic in `ingest_raw_file` ensures that when multiple documents reference the same Entity, their relationships are merged rather than overwritten.

3. **Iterative Retrieval (The "Agentic" Hop)**:
   - **Problem**: Standard RAG retrieves only direct matches (1-hop). Complex questions like "Who initiates Phantom Protocol?" require traversing `Protocol -> Project -> Sector -> Person` (3-4 hops).
   - **Solution**: Implemented **Iterative Retrieval** in `driver`.
     - **Round 1**: Vector/Hybrid Search finds initial hits.
     - **Link Extraction**: System scans retrieved content for `[[WikiLinks]]`.
     - **Recursive Step**: System actively queries the DB for these linked entities (handling title sanitization `Space` vs `_`).
     - **Multi-Round**: Repeats up to 5 rounds to gather the full context subgraph.

## Verification: The "Phantom Protocol" Test

### 1. Test Scenario
We created three synthetic documents to form a dependency chain:
- `security_protocols.md`: Links "Phantom Protocol" -> "Lead Researcher" & "Project Chimera".
- `project_chimera_staff.md`: Links "Project Chimera" -> "Sector 7".
- `sector_7_personnel.md`: Links "Sector 7" -> "Dr. Aris Thorne".

### 2. Graph Construction
Using `graph_navigator.py`, we verified the structure in the database:
```bash
docker exec -it context-driver python src/graph_navigator.py ls "Project_Chimera"
# Output:
# Outgoing Edges:
#   --[wikilink]--> Sector 7
#   --[wikilink]--> Phantom Protocol
```

### 3. Query Execution
We sent the multi-hop question to the API:
```bash
curl -X POST http://localhost:8000/v1/chat/completions ...
"Who should I contact if I want to initiate the Phantom Protocol?"
```

### 4. Success Result
The system successfully traversed the graph and returned:
> "You should contact the active Lead Researcher, as they are the one responsible for initiating the Phantom Protocol... In this case, the Lead Researcher is **Dr. Aris Thorne** [Dr__Aris_Thorne.md]."

## Test Case 2: Distributed Aggregation ("The Shadow Board")

### 1. Scenario
A more complex test where the answer is **scattered** across multiple documents.
-   **Q**: "Who are the current members of the Shadow Board?"
-   **Doc A**: "Shadow Board consists of leaders of [[Obsidian Vanguard]], [[Cipher Bureau]], [[Echo Station]]." (No names)
-   **Doc B**: "Obsidian Vanguard is led by **Director Kael**."
-   **Doc C**: "Cipher Bureau is under **Head Cryptographer Elara**."
-   **Doc D**: "Echo Station commanded by **Commander Voss**."

### 2. Execution
The system performed **3 Rounds** of iterative retrieval:
1.  **Round 1**: Found "Shadow Board" -> Discovered Division links.
2.  **Round 2**: Fetched Division docs -> Discovered Leader links (`[[Director Kael]]`, etc).
3.  **Round 3**: Fetched Leader entities.

### 3. Result
> "The current members of the Shadow Board are:
> 1. **Director Kael** - Leader of the Obsidian Vanguard
> 2. **Elara** - Head Cryptographer of the Cipher Bureau
> 3. **Commander Voss** - Commander of Echo Station"

 This demonstrates **Graph Aggregation**: collecting a group of entities defined by a relationship in a parent node.
-   `volumes/raw/graph_test.md`: Verification/Test data.
-   `IMPLEMENTATION_PLAN.md`: Saved in project root.

## Usage
-   Add markdown files to `volumes/raw`.
-   Wait for processing (check logs).
-   Use `docker exec -it context-driver python src/graph_navigator.py ...` to explore.
