# Part 6: Agentic Reasoning & Sub-Brains

> *From passive retrieval to active thinking*

**Commits:** `16365cf` → `75c2831`

---

## The Limitation of Retrieval

Even with neurosymbolic primitives, the system was reactive:
1. User asks question
2. System retrieves relevant content
3. LLM generates answer

For complex questions, this single-shot approach fails. Consider: *"What's the full procedure for recovering from a database corruption that affects our SSL certificate store?"*

This requires:
1. Finding the database recovery procedure
2. Finding the SSL certificate recovery procedure
3. Understanding their relationship
4. Synthesizing a combined answer

No single retrieval gets all of that.

## ReAct: Reasoning + Acting

ReAct (Yao et al., 2022) is a paradigm where agents:
1. **Think** about what information is needed
2. **Act** by calling tools
3. **Observe** the results
4. **Repeat** until confident in the answer

DSPy provides a clean implementation:

```python
from dspy import ReAct

class AnswerQuestion(dspy.Signature):
    question: str = dspy.InputField()
    answer: str = dspy.OutputField()

agent = dspy.ReAct(
    signature=AnswerQuestion,
    tools=[search_knowledge_base, get_facts, get_rules],
    max_iters=5
)

result = agent(question="How do I recover from database corruption?")
```

## The Knowledge Base Tools

Seven tools give the agent deep access:

```python
KNOWLEDGE_BASE_TOOLS = [
    search_knowledge_base,   # Hybrid semantic+keyword search
    get_facts,               # Query S-P-O triples
    get_rules,               # Query IF-THEN rules
    get_capsule,             # Get document summary
    get_document_section,    # Extract specific section
    get_related_documents,   # Graph navigation
    list_documents,          # Browse by domain/intent
]
```

Each tool returns **formatted text**, not raw objects. This lets the LLM naturally incorporate results into reasoning.

## A ReAct Trace

```
Question: "What happens if the database connection fails?"

Thought: I need to find rules about database failure handling.
Action: get_rules(domain="database", severity="critical")
Observation: RULE_DB_001: IF connection fails THEN page DBA (critical)

Thought: Found a rule. Let me search for more context.
Action: search_knowledge_base("database connection failure handling")
Observation: Found: Database_Operations.md - "Connection failures trigger automatic retry..."

Thought: I have enough information to answer.
Final Answer: When the database connection fails, the system first attempts
automatic retry. If retries are exhausted, a critical alert pages the DBA
per operational rule RULE_DB_001.
```

## Pseudo-Models

The system exposes two models to users:

| Model | Behavior | Use Case |
|-------|----------|----------|
| `brain-rag` | Single-pass retrieval | Fast, simple questions |
| `brain-react` | Multi-step reasoning | Complex, multi-part questions |

In LiteLLM config:

```yaml
model_list:
  - model_name: brain-rag
    litellm_params:
      model: custom_openai/context-brain
      api_base: http://context-driver:8000/v1
      
  - model_name: brain-react
    litellm_params:
      model: custom_openai/context-brain-react
      api_base: http://context-driver:8000/v1
```

Users select the model in Open WebUI. The system routes accordingly.

## Sub-Brains: Scoped Knowledge

Not all knowledge should be global. A "sub-brain" is a scoped subset:

```
volumes/raw/
├── operations/          # General ops knowledge
│   ├── SSL_Certs.md
│   └── Database_Ops.md
├── projects/
│   └── acme-app/        # Sub-brain: Acme project
│       ├── .brainignore # Prevents parent indexing
│       ├── Architecture.md
│       └── Runbook.md
```

Query with scope:

```bash
curl -X POST localhost:8000/tools/search \
  -d '{"query": "deployment", "sub_path": "projects/acme-app"}'
```

The `.brainignore` file prevents the parent from indexing the sub-brain, enabling independent knowledge domains.

## API Extensions

```python
# Discover sub-brains
GET /tools/sub-brains
→ ["projects/acme-app", "projects/beta-service", "modes/debug"]

# Scoped search
POST /tools/search
{
  "query": "database connection",
  "sub_path": "projects/acme-app"
}

# Scoped listing
GET /tools/articles?sub_path=projects/acme-app
```

## Programmatic Scoping

```python
from brain_rag import Tools

# Global search
global_tools = Tools()
global_tools.search_knowledge_base("SSL")

# Scoped to project
project_tools = Tools(sub_path="projects/acme-app")
project_tools.search_knowledge_base("deployment")  # Only searches Acme docs
```

## Lessons Learned

1. **ReAct beats single-shot retrieval** for complex questions
2. **Tools should return formatted text** — LLMs reason better with prose
3. **Pseudo-models simplify UX** — users just pick a model
4. **Sub-brains enable multi-tenancy** — projects get private knowledge
5. **Scoping is composable** — nest sub-brains arbitrarily

## What's Next

The ReAct agent thinks and acts. But how do we know it's right? How confident is it?

Part 7 introduces **answer verification, confidence assessment, and self-learning**.

---

[← Previous: The Neurosymbolic Turn](./05-neurosymbolic-turn.md) | [Back to Index](./README.md) | [Next: Brain-React Architecture →](./07-brain-react-architecture.md)
