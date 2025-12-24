# Test Design: Non-Trivial Multi-Hop Reasoning

## Objective
Verify the GraphRAG system's ability to answer questions that require connecting pieces of information across multiple documents (Indirect Knowledge/Multi-hop Reasoning).

## Scenario: "The Phantom Protocol"

We will construct a knowledge graph where the answer depends on a chain of relationships `A -> B -> C -> D`.

### The Hidden Truth
**Answer**: "Dr. Aris Thorne" (The person to contact for the Phantom Protocol).
**Question**: "Who should I contact if I want to initiate the Phantom Protocol?"

### Synthetic Documents

#### Document 1: `security_protocols.md`
**Content**:
> The **Phantom Protocol** is a failsafe measure for **Project Chimera**. It can only be initiated by the active **Lead Researcher**.

*Information Provided*: `Phantom Protocol` --(initiated_by)--> `Lead Researcher of Project Chimera`

#### Document 2: `project_chimera_staff.md`
**Content**:
> **Project Chimera** is currently headquartered in **Sector 7**. The team structure was reorganized in 2024.

*Information Provided*: `Project Chimera` --(located_in)--> `Sector 7`
*(Distractor node to ensure simple keywords don't work)*

#### Document 3: `sector_7_personnel.md`
**Content**:
> Personnel in **Sector 7** report to the Chief Science Officer. However, the specific **Lead Researcher** for the classified biology division is **Dr. Aris Thorne**, who transferred from Geneva.

*Information Provided*: `Dr. Aris Thorne` --(is)--> `Lead Researcher (Sector 7/Biology)`

### The Reasoning Chain
1.  User asks: "Who do I contact for the Phantom Protocol?"
2.  Hop 1 (Doc 1): Phantom Protocol -> requires -> Lead Researcher of Project Chimera.
3.  Hop 2 (Doc 2): Project Chimera -> is in -> Sector 7.
4.  Hop 3 (Doc 3): Lead Researcher in Sector 7 -> is -> Dr. Aris Thorne.

*Note: This relies on the Graph inferring that "Lead Researcher of Project Chimera" is the same entity or related to "Lead Researcher" in "Sector 7" context. This is the challenge.*

## Execution Plan
1.  **Create Files**: Write these 3 markdown files to `volumes/raw/`.
2.  **Wait for Ingestion**: Allow `context-driver` to extract entities (`Phantom Protocol`, `Project Chimera`, `Sector 7`, `Dr. Aris Thorne`).
3.  **Verify Graph**: Use `graph_navigator.py ls` to check edges.
4.  **Test Query**: Ask the system the question.

## Success Criteria
-   The system identifies "Dr. Aris Thorne" as the answer.
-   It cites the source documents that form the chain.
