# Neurosymbolic Ingestion Spec

## Phase 1: Knowledge Distillation Pipeline

```
            ┌──────────────────────────────┐
            │    RAW KNOWLEDGE SOURCES     │
            │  (docs, runbooks, logs, Jira)│
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │  PASS #1 — CONDENSE (DSPy)   │
            │  summary, key_points, intent │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │  PASS #2 — STRUCTURE (DSPy)  │
            │  entities, facts, triples    │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼───────────────┐
            │  PASS #3 — DISTILL (DSPy)    │
            │  rules, conditions, actions  │
            └──────────────┬───────────────┘
                           │
                ┌──────────▼───────────┐
                │  EXECUTABLE LORE     │
                └──────────────────────┘
```

---

## DSPy Integration

DSPy provides **typed signatures** for predictable prompt execution. Each pass becomes a DSPy module with explicit input/output contracts.

### Why DSPy?
| Problem | DSPy Solution |
| --- | --- |
| Inconsistent LLM outputs | Typed signatures enforce structure |
| Prompt engineering churn | Optimizers tune prompts automatically |
| No validation | Field types + assertions catch errors |
| Hard to test | Modules are unit-testable |

### DSPy Signatures for 3-Pass Pipeline

```python
import dspy

# Pass #1: CONDENSE
class CondenseDocument(dspy.Signature):
    """Extract core meaning from a document."""
    title: str = dspy.InputField()
    content: str = dspy.InputField()
    
    summary: str = dspy.OutputField(desc="2-3 sentence summary")
    key_points: list[str] = dspy.OutputField(desc="3-7 bullet points")
    intent: str = dspy.OutputField(desc="procedure|fact|policy|incident|reference")
    domain: str = dspy.OutputField(desc="ssl|networking|auth|database|security|...")

# Pass #2: STRUCTURE
class ExtractFacts(dspy.Signature):
    """Extract subject-predicate-object facts from document."""
    title: str = dspy.InputField()
    content: str = dspy.InputField()
    summary: str = dspy.InputField()
    
    facts: list[dict] = dspy.OutputField(desc="List of {subject, predicate, object}")

# Pass #3: DISTILL RULES
class DistillRules(dspy.Signature):
    """Extract IF-THEN rules from procedural documents."""
    title: str = dspy.InputField()
    content: str = dspy.InputField()
    intent: str = dspy.InputField()
    facts: list[dict] = dspy.InputField()
    
    rules: list[dict] = dspy.OutputField(desc="List of {rule_id, condition, action, severity}")
```

### DSPy Modules (Predictors)

```python
class NeuroIngestionPipeline(dspy.Module):
    def __init__(self):
        self.condense = dspy.Predict(CondenseDocument)
        self.extract_facts = dspy.Predict(ExtractFacts)
        self.distill_rules = dspy.Predict(DistillRules)
    
    def forward(self, title: str, content: str):
        # Pass #1
        capsule = self.condense(title=title, content=content)
        
        # Pass #2
        facts_result = self.extract_facts(
            title=title, content=content, summary=capsule.summary
        )
        
        # Pass #3 (only for procedures/policies)
        rules_result = {"rules": []}
        if capsule.intent in ["procedure", "policy", "incident"]:
            rules_result = self.distill_rules(
                title=title, content=content,
                intent=capsule.intent, facts=facts_result.facts
            )
        
        return {
            "capsule": capsule,
            "facts": facts_result.facts,
            "rules": rules_result.rules
        }
```

---

## Storage Schema

| Table | Contents |
|-------|----------|
| `brain.capsules` | Condensed summaries per source |
| `brain.facts` | Subject-predicate-object triples |
| `brain.rules` | Executable IF-THEN logic |

---

## Delta from Current Implementation

| Aspect | Current (litellm) | DSPy |
|--------|---------|---------------|
| Prompts | Manual f-strings | Typed signatures |
| Output parsing | Manual JSON parse | Automatic type coercion |
| Validation | None | Field types + assertions |
| Optimization | Manual tuning | MIPROv2 / BootstrapFewShot |
| Testing | Integration only | Unit testable modules |
