# Neurosymbolic ReAct Architecture

This document details how Context Engine integrates **Neurosymbolic AI** (structured knowledge extraction) with **ReAct Agents** (iterative reasoning) into a coherent, production-ready mechanism.

## The Core Concept

The system bridges the gap between **unstructured text** and **structured logic** by using a two-pass approach:

1.  **Ingestion Time (Neurosymbolic Distillation)**: Distill raw text into structured primitives (Facts, Rules, Capsules).
2.  **Inference Time (ReAct Reasoning)**: Use a ReAct agent to actively query and reason over these structures.

## 1. The Neurosymbolic Layer (Ingestion)

When a document is ingested, the `NeuroIngestionPipeline` (in `db.py`) runs it through three DSPy signatures to extract:

| Primitive | Description | Storage | Purpose |
|-----------|-------------|---------|---------|
| **Capsules** | Distilled summary, intent, domain | `brain.capsules` | High-level understanding & routing |
| **Facts** | Subject-Predicate-Object triples | `brain.facts` | Entity relationships & knowledge graph |
| **Rules** | IF-THEN logic with severity | `brain.rules` | Constraints, procedures, & invariants |

**Architectural Guardrail:** Capsules are navigation artifacts. They are non-normative, non-executable, and must not be used for validation. They exist solely to aid discovery and routing.

### Formalized Schemas

#### Rule Schema
Rules are **executable, auditable objects** rather than free text. 

```yaml
rule_id: RULE_DB_SSL_001
scope: database
trigger:
  subject: database_connection
  condition: ssl_required
action:
  type: page
  target: dba
severity: critical
confidence: 0.82
provenance:
  doc_id: prod_db_policy.md
  span: lines 12–18
version: 1
status: active
valid_from: 2025-01-01
valid_until: null
```

**The ReAct agent must prefer `active` artifacts, may reference `deprecated` ones with warning, and must ignore `invalid` artifacts.**

#### Fact Schema
Facts form a stable entity spine across the system.

```yaml
fact_id: FACT_DB_SSL_001
subject_id: entity:database_connection
predicate: requires
object_id: entity:ssl
confidence: 0.9
provenance:
  doc_id: prod_db_policy.md
  span: lines 5–7
status: active
```

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
3.  **Observation**: Returns rule object `RULE_DB_SSL_001` (IF SSL fails THEN page DBA).
4.  **Thought**: "I see the rule. I should also check context for connection setup."
5.  **Action**: `search_knowledge_base("database connection setup")`
6.  **Observation**: Returns text snippets.
7.  **Final Answer**: Synthesizes the strict rule (Page DBA) with the broad context.

## 3. Coherence Mechanism

The coherence comes from the **DSPy Signatures** which act as a **Procedural Contract**:

"The Agent Signature defines a procedural contract: when a question involves operational constraints, the agent must consult facts and rules via explicit tools."

This reframes the design as disciplined reasoning, enhancing auditability and enterprise credibility.

**Defense against Shortcuts:** The ReAct agent must not derive normative conclusions solely from Capsules.

### Answer Mode & Confidence

All agent responses include explicit signals for trust:

```yaml
answer_mode: kb-backed | mixed | fallback
confidence: 0.47
```

**Semantics:**
- **Confidence** is a heuristic signal, not a probability. It reflects internal agreement between sources and rules.
- **Fallback** indicates absence of verified knowledge, not agent failure.
- **Aggregation**: Confidence aggregation logic is implementation-specific and may evolve over time.

## Failure & Degradation Modes

The system defines explicit behavior for non-ideal conditions:

- **Tool conflict**: Conflicting tool outputs are surfaced explicitly.
- **Rule conflict**: The agent refuses to answer and requests escalation.
- **Low provenance**: The agent switches to `fallback` mode.
- **Reasoning loop detected**: The agent terminates reasoning and returns partial findings.
- **Escalation**: Escalation targets (human operator, workflow system, or supervisory agent) are deployment-defined.

## 4. Truth & Provenance Model

- **Everything has provenance**: Every fact and rule links back to a source line in a document.
- **Investigations are descriptive, not normative**: They capture a specific reasoning trace but are not authoritative sources of truth.
- **Rules are verified**: Only verified artifacts become normative rules.
- **Correctness > Completeness**: It is better to return "unknown" than a hallucinated fact.

## Rule & Fact Promotion Policy

Promotion from Investigations into Facts or Rules is gated by explicit policies:

- **Human-approved**: Manual confirmation by an authorized operator.
- **Multi-source corroboration**: Independent confirmation from multiple primary sources.
- **Repeated evidence**: The same conclusion appears in N investigations with confidence ≥ X over Y time window.

Authorized operators and promotion permissions are defined by system governance configuration.

No automatic promotion occurs without satisfying at least one policy.

## 5. Self-Improvement Loop (The Investigation Artifact)

To finalize the neurosymbolic loop, every successful ReAct reasoning session is automatically saved as a **Knowledge Artifact** (an "Investigation").

**Distinction:**
- **Investigations (Descriptive)**: Result of specific reasoning. May be incomplete. Used for retrieval navigation. Investigations may be retrieved for context and navigation, but must not be treated as authoritative sources without validation.
- **Facts / Rules (Normative)**: Verified, versioned, authoritative.

**Process:**
1.  **Capture**: The entire reasoning trace is formatted into a markdown document.
2.  **Storage**: Saved to `volumes/raw/investigations/Investigation_<timestamp>_<topic>.md`.
3.  **Ingestion**: The file watcher ingests it as an Investigation context.
4.  **Promotion**: Verified fragments can later be promoted into facts or rules through explicit validation.

**Example Artifact Structure:**

```markdown
---
type: investigation
status: closed
confidence: 0.85
date: 2025-12-28
tags: [react, auto-generated]
---
# Investigation: Why did the database fail?

## Executive Summary
The database failed due to connection exhaustion...

## Reasoning Trace
...
```

The system remembers its own problem-solving as investigations. Verified fragments can later be promoted into facts or rules through explicit validation, preventing uncontrolled self-learning and maintaining knowledge integrity.

## 6. Future Improvements

### Safety & Correctness
- **Automatic Rule Verification**: Agent automatically checks generated answers against stored rules.
- **Rule Conflict Detection**: Identifying contradictory rules in the knowledge base.
- **Answer Validation**: Ensuring outputs respect all critical severity rules.
- **Reasoning Telemetry**: Recording which tools, rules, and facts were consulted per answer.

### Knowledge Evolution
- **Rule Chaining**: Teaching agents to chain `Rule A -> Rule B -> Conclusion`.
- **SOP Proposal**: Pipeline to propose new Standard Operating Procedures (draft mode) based on successful investigations.
- **Investigation → Candidate Rule**: Automated pipeline to suggest rules from repeated investigations.

**The system prioritizes correctness, auditability, and controlled evolution over autonomous behavior.**

All autonomous behavior is constrained by explicit governance, validation, and lifecycle policies.
