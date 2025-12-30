# Part 5: The Neurosymbolic Turn

> *Beyond embeddings: structured knowledge extraction*

**Commits:** `588eefd` → `f04d8eb`

---

## The Epiphany

> Raw documents shouldn't be "searched" — they should be ***distilled***.

This was the breakthrough moment. Instead of treating documents as opaque text blobs that match queries, what if we **extracted their meaning** into structured primitives?

## The 3-Pass System

Every document now goes through three extraction phases:

### Pass 1: Condense Meaning → Capsule

Extract the document's essence:

```python
class ExtractCapsule(dspy.Signature):
    """Extract a condensed summary from a document."""
    
    document: str = dspy.InputField()
    
    summary: str = dspy.OutputField(desc="2-3 sentence summary")
    key_points: list[str] = dspy.OutputField(desc="3-5 key points")
    intent: str = dspy.OutputField(desc="procedure|policy|fact|incident")
    domain: str = dspy.OutputField(desc="ssl|database|networking|auth")
```

A document about SSL renewal becomes:

```json
{
  "summary": "This document describes the SSL certificate renewal process for production servers.",
  "key_points": [
    "Certificates must be renewed 30 days before expiry",
    "Use certbot for automated renewal",
    "Notify security team after renewal"
  ],
  "intent": "procedure",
  "domain": "ssl"
}
```

### Pass 2: Extract Structured Facts

Convert prose into Subject-Predicate-Object triples:

```python
class ExtractFacts(dspy.Signature):
    """Extract factual statements as S-P-O triples."""
    
    document: str = dspy.InputField()
    
    facts: list[Fact] = dspy.OutputField()

class Fact:
    subject: str    # "SSL certificates"
    predicate: str  # "must be renewed"
    object: str     # "30 days before expiry"
    confidence: float
```

Facts become queryable:

```sql
SELECT * FROM brain.facts 
WHERE subject ILIKE '%ssl%' 
  AND predicate ILIKE '%renew%';
```

### Pass 3: Derive Executable Rules

Extract IF-THEN logic:

```python
class ExtractRules(dspy.Signature):
    """Extract conditional rules and constraints."""
    
    document: str = dspy.InputField()
    
    rules: list[Rule] = dspy.OutputField()

class Rule:
    condition: str   # "certificate expires in < 7 days"
    action: str      # "page on-call engineer immediately"
    severity: str    # "critical"
```

Rules with severity enable prioritized reasoning:

```sql
SELECT * FROM brain.rules 
WHERE severity = 'critical' 
  AND condition ILIKE '%database%';
```

## Why DSPy?

Traditional LLM prompts are:
- **Brittle** — small wording changes break outputs
- **Untestable** — no type checking
- **Unoptimizable** — can't automatically improve

DSPy **Signatures** solve this:

```python
# Type-safe, optimizable, testable
class ExtractFacts(dspy.Signature):
    document: str = dspy.InputField()
    facts: list[Fact] = dspy.OutputField()

# Usage
extractor = dspy.Predict(ExtractFacts)
result = extractor(document=doc_text)
# result.facts is now a typed list
```

DSPy can **optimize signatures** with training examples:

```python
optimizer = dspy.BootstrapFewShot(metric=fact_accuracy)
optimized_extractor = optimizer.compile(
    extractor, 
    trainset=training_examples
)
```

## Database Schema

```sql
-- Document capsules (summaries)
CREATE TABLE brain.capsules (
    id SERIAL PRIMARY KEY,
    note_id INTEGER REFERENCES brain.notes(id),
    summary TEXT,
    key_points JSONB,
    intent TEXT,
    domain TEXT,
    confidence FLOAT
);

-- Extracted facts (S-P-O triples)
CREATE TABLE brain.facts (
    id SERIAL PRIMARY KEY,
    note_id INTEGER REFERENCES brain.notes(id),
    subject TEXT,
    predicate TEXT,
    object TEXT,
    confidence FLOAT
);

-- Executable rules (IF-THEN)
CREATE TABLE brain.rules (
    id SERIAL PRIMARY KEY,
    note_id INTEGER REFERENCES brain.notes(id),
    condition TEXT,
    action TEXT,
    severity TEXT,  -- critical, high, normal, low
    confidence FLOAT
);
```

## Query APIs

The system exposes these primitives via REST:

```bash
# Get facts about SSL
curl localhost:8000/tools/facts?subject=ssl

# Get critical rules
curl localhost:8000/tools/rules?severity=critical

# Get capsule for a document
curl localhost:8000/tools/capsule/SSL_Certificates
```

## The Paradigm Shift

Before neurosymbolic extraction:
- Query: "What happens if SSL expires?"
- System: *searches for documents mentioning SSL and expiry*
- Result: Maybe relevant, maybe not

After:
- Query: "What happens if SSL expires?"
- System: *queries rules where condition matches expiry*
- Result: "IF certificate expires THEN page on-call (CRITICAL)"

**This is the difference between searching and knowing.**

## Lessons Learned

1. **DSPy signatures > prompt templates** — type safety matters
2. **Facts enable precise queries** — S-P-O triples are powerful
3. **Rules capture operational knowledge** — IF-THEN is executable
4. **Capsules aid navigation** — summaries help users browse
5. **Extraction at ingestion time** — pay cost once, query forever

## What's Next

We have structured knowledge. But the system still passively responds to queries. What if it could **actively reason**?

Part 6 introduces **ReAct agents** that think, act, and iterate.

---

[← Previous: Enterprise Features](./04-enterprise-features.md) | [Back to Index](./README.md) | [Next: Agentic Reasoning →](./06-agentic-reasoning.md)
