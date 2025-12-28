# Neurosymbolic ReAct Architecture

This document details how Context Engine integrates **Neurosymbolic AI** (structured knowledge extraction) with **ReAct Agents** (iterative reasoning) into a coherent mechanism.

## The Core Concept

The system bridges the gap between **unstructured text** and **structured logic** by using a two-pass approach:

1.  **Ingestion Time (System 1)**: Distill raw text into structured primitives (Facts, Rules, Capsules).
2.  **Inference Time (System 2)**: Use a ReAct agent to actively query and reason over these structures.

## 1. The Neurosymbolic Layer (Ingestion)

When a document is ingested, the `NeuroIngestionPipeline` (in `db.py`) runs it through three DSPy signatures to extract:

| Primitive | Description | Storage | Purpose |
|-----------|-------------|---------|---------|
| **Capsules** | Distilled summary, intent, domain | `brain.capsules` | High-level understanding & routing |
| **Facts** | Subject-Predicate-Object triples | `brain.facts` | Entity relationships & knowledge graph |
| **Rules** | IF-THEN logic with severity | `brain.rules` | Constraints, procedures, & invariants |

This turns a flat markdown file like:
> "In production, all database connections must use SSL. If this fails, page the DBA."

Into executable logic:
- **Rule**: `IF database connection THEN use SSL (Severity: High)`
- **Rule**: `IF SSL connection fails THEN page DBA (Severity: Critical)`

## 2. The ReAct Layer (Inference)

The `KnowledgeBaseReActAgent` (in `react_agent.py`) is initialized with a set of tools that provide direct access to these primitives.

### Available Tools (`dspy_tools.py`)

- `search_knowledge_base(query)`: Standard semantic/hybrid search.
- `get_facts(subject, predicate)`: Query the knowledge graph.
- `get_rules(domain, severity)`: Query operational constraints.
- `get_capsule(title)`: Get high-level summary of a doc.
- `list_documents(domain, intent)`: Discovery.

### The Reasoning Loop

When a user asks: *"What happens if the DB connection fails?"*

The integrated ReAct loop executes:

1.  **Thought**: "I need to check for failure handling procedures related to databases."
2.  **Action**: `get_rules(domain="database", severity="critical")`
3.  **Observation**: Returns rule: `IF SSL connection fails THEN page DBA`
4.  **Thought**: "I see the rule. I should also check context for connection setup."
5.  **Action**: `search_knowledge_base("database connection setup")`
6.  **Observation**: Returns text snippets.
7.  **Final Answer**: Synthesizes the strict rule (Page DBA) with the broad context.

## 3. Coherence Mechanism

The coherence comes from the **DSPy Signatures**:

1.  **Extraction Signature**: Enforces that extracted rules are atomic and logical.
2.  **Agent Signature**: Enforces that the agent *must* consider rules and facts if the question warrants it.

```python
class AnswerQuestion(dspy.Signature):
    """
    Answer... extract facts, and find applicable rules. 
    Reason step-by-step...
    """
```

By explicitly mentioning "facts" and "rules" in the agent's signature, we bias the LLM to utilize the specific tools we built, creating a feedback loop between the structured database and the unstructured reasoning process.

## 4. Future Improvements

To tighten the integration further:

- **Automatic Verification**: Agent could automatically check its generated answer against `get_rules()` to ensure no constraints are violated.
- **Rule Chaining**: Agent could be taught to chain rules (Rule A -> Rule B -> Conclusion).
- **Feedback Loop**: When the agent discovers a gap, it could propose new standard operating procedures to be added to the knowledge base.

## 5. Self-Improvement Loop (The Investigation Artifact)

To finalize the neurosymbolic loop, every successful ReAct reasoning session is automatically saved as a **Knowledge Artifact** (an "Investigation").

1.  **Process**: User asks complex question → ReAct Agent solves it.
2.  **Capture**: The entire reasoning trace (Thought, Action, Observation) and Final Answer are formatted into a markdown document.
3.  **Storage**: Saved to `volumes/raw/investigations/Investigation_<timestamp>_<topic>.md`.
4.  **Ingestion**: The file watcher detects the new file, ingests it, and distills it into facts/rules.

**Example Artifact Structure:**

```markdown
---
type: investigation
tags: [react, auto-generated]
---
# Investigation: Why did the database fail?

## Executive Summary
The database failed due to connection exhaustion...

## Reasoning Trace
### Step 1
**Thought**: I need to check error logs.
**Action**: `search("database error logs")`
...
```

This means the system **remembers its own problem-solving**, converting transient reasoning into permanent knowledge. Future queries can retrieve this investigation directly via `search_knowledge_base`, skipping the expensive reasoning steps.
