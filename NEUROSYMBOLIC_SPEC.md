# Neurosymbolic Knowledge Distillation

## Phase 1: Knowledge Distillation Pipeline

```
            ┌──────────────────────────────┐
            │    RAW KNOWLEDGE SOURCES     │
            │  (docs, runbooks, logs, Jira)│
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │  PASS #1 — CONDENSE          │
            │  извлечение ядра смысла      │
            │  (summary, points, intent)   │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │  PASS #2 — STRUCTURE         │
            │  entities, facts, capsules   │
            │  (graph / triples / schema)  │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │  PASS #3 — DISTILL RULES     │
            │  invariants, conditions,     │
            │  actions, logic              │
            └──────────────┬───────────────┘
                           │
                ┌──────────▼───────────┐
                │  EXECUTABLE LORE     │
                │  (runtime package)   │
                └──────────┬───────────┘
                           │
                     ┌─────▼─────┐
                     │ EXECUTE   │
                     │ answer /  │
                     │ triage /  │
                     │ decisions │
                     └───────────┘
```

---

## Pass #1: CONDENSE

**Goal**: Extract the core meaning from raw documents.

**Input**: Raw source file (markdown, runbook, log, Jira ticket)

**Output**: Condensed capsule
```json
{
  "source_id": "runbook_ssl_renewal.md",
  "summary": "...",
  "key_points": ["...", "..."],
  "intent": "procedure | fact | policy | incident",
  "domain": "ssl | networking | auth | ...",
  "confidence": 0.95
}
```

**Implementation**:
- LLM prompt: "Summarize this document into its core meaning..."
- Store in `brain.capsules`

---

## Pass #2: STRUCTURE

**Goal**: Extract structured knowledge (entities, facts, relations).

**Input**: Condensed capsule + original source

**Output**: Facts and triples
```json
{
  "entities": [
    {"id": "ssl_cert", "type": "artifact", "name": "SSL Certificate"},
    {"id": "lets_encrypt", "type": "service", "name": "Let's Encrypt"}
  ],
  "facts": [
    {"subject": "ssl_cert", "predicate": "issued_by", "object": "lets_encrypt"},
    {"subject": "ssl_cert", "predicate": "expires_in", "object": "90_days"}
  ],
  "provenance": "runbook_ssl_renewal.md#L12-L25"
}
```

**Implementation**:
- LLM prompt with schema constraint
- Store in `brain.facts` (subject, predicate, object, provenance)
- Link to existing `brain.edges` for graph traversal

---

## Pass #3: DISTILL RULES

**Goal**: Extract executable rules (invariants, conditions, actions).

**Input**: Facts from Pass #2

**Output**: Logical rules
```json
{
  "rules": [
    {
      "id": "rule_ssl_renewal",
      "condition": "ssl_cert.expires_in < 30_days",
      "action": "trigger_renewal",
      "severity": "critical",
      "provenance": "runbook_ssl_renewal.md"
    },
    {
      "id": "rule_geo_filter",
      "condition": "request.country NOT IN allowed_countries",
      "action": "block_request",
      "severity": "normal",
      "provenance": "geo_filtering.md"
    }
  ]
}
```

**Implementation**:
- LLM prompt: "Given these facts, extract IF-THEN rules..."
- Store in `brain.rules` (condition, action, severity, provenance)

---

## Executable Lore (Runtime Package)

The final output is a **runtime-queryable knowledge package**:

| Table | Contents |
|-------|----------|
| `brain.capsules` | Condensed summaries per source |
| `brain.facts` | Subject-predicate-object triples |
| `brain.rules` | Executable IF-THEN logic |
| `brain.provenance` | Links back to source locations |

---

## Execution Phase

At query time:

1. **Retrieve**: Vector search + fact lookup
2. **Reason**: Apply rules to derive new facts
3. **Ground**: Link answer to provenance
4. **Generate**: LLM produces grounded response

---

## Delta from Current Implementation

| Aspect | Current | Neurosymbolic |
|--------|---------|---------------|
| Extraction | 1-pass (entities + relations) | 3-pass (condense → structure → rules) |
| Storage | `brain.notes`, `brain.edges` | + `brain.capsules`, `brain.facts`, `brain.rules` |
| Reasoning | Graph traversal only | + Rule execution |
| Grounding | WikiLinks | + Provenance chains |

---

## Next Steps

1. [ ] Define schema for `brain.capsules`, `brain.facts`, `brain.rules`
2. [ ] Implement Pass #1 (CONDENSE) in `main.py`
3. [ ] Implement Pass #2 (STRUCTURE) extending `prompts.py`
4. [ ] Implement Pass #3 (DISTILL RULES) as new extraction step
5. [ ] Create rule execution engine for query-time reasoning
