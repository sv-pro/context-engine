# ReAct Agent Improvement Recommendations

Based on testing with multi-hop questions against the knowledge base.

---

## ✅ Implemented Fixes (2024-12-30)

The following improvements have been implemented:

### 1. Enhanced AnswerQuestion Signature
- Added explicit workflow guidance (search → retrieve → extract → check)
- Added TOOL SELECTION BY QUESTION TYPE heuristics
- Added ACCURACY RULES emphasizing exact value extraction
- Added warning about entity pages vs source documents

### 2. Enhanced AnswerWithContext Signature
- Added instructions to extract ALL config values from YAML/JSON
- Added emphasis that code blocks are authoritative sources

### 3. Improved Search to Prioritize Documents
- Search now labels results with `[ENTITY PAGE]` when from entities folder
- Added tips like `[TIP: For config values, try get_capsule("Kong API Gateway")]`
- Documents are prioritized over entities in results

### 4. Added Fuzzy Matching to get_facts()
- Falls back to ILIKE pattern matching when exact match fails

### 5. Enhanced get_capsule() for Procedures
- Includes procedure steps and code blocks when intent=procedure

### 6. Added get_document_section() Tool
- New tool to retrieve specific sections from documents
- Helps avoid truncation issues with large documents

### 7. Smart Truncation in Search Results
- Increased from 500 to 800 chars for config content
- Preserves complete code blocks where possible
- Adds hint to use get_document_section() when truncated

### 8. Trajectory Rescue Mechanism
- Synthesizes better answer from trajectory when draft is weak
- Uses AnswerWithContext to extract values from observations

### 9. Smart Verification
- Keeps draft answer if it has specific values even when verifier says "Incorrect"
- Prevents verifier from overriding correct answers

### Test Results After Fixes
| Question | Before | After |
|----------|--------|-------|
| Q1 (SSL rotation) | Partial, missing SDS | Improved, has procedure steps |
| Q2 (Backup schedule) | Partial, missing RTO/RPO | Good, has schedule + RTO/RPO |
| Q3 (Incident roles) | Failed lookup | ✅ Correct |
| Q4 (Rate limits) | Wrong values (1000) | ✅ 5000/500, redis-ratelimit |

---

## Summary

| Issue | Severity | Effort |
|-------|----------|--------|
| Agent relies on capsule summaries, missing procedure details | High | Medium |
| Reasoning trace sometimes empty | Medium | Low |
| Answers lack specific values (commands, times, channels) | High | Medium |
| Verifier marks "Partial" but doesn't guide improvement | Medium | Medium |
| Entity naming mismatches prevent fact retrieval | Medium | Low |
| `get_facts()` works well but underutilized | Low | Low |
| Search snippets truncated, causing value misreads | High | Medium |

---

## Issue 1: Capsule Summaries Insufficient for Procedures

### Observed Behavior
When asked about PITR backup procedures, the agent:
1. Found `Database_Backup_Procedures` document
2. Called `get_capsule()` which returned a summary
3. Synthesized answer from summary alone
4. **Missed**: actual commands, RTO/RPO values, specific steps

### Root Cause
The capsule contains:
> "Recovery includes point-in-time recovery and full database restoration procedures"

But the **full document** has:
```bash
pgbackrest restore --type=time --target="2024-01-15 14:30:00"
```

The agent has no heuristic to fetch full content when procedures are involved.

### Recommendation
**Option A: Enhance `get_capsule` for procedures**
```python
# In dspy_tools.py
def get_capsule(title: str) -> str:
    capsule = _fetch_capsule(title)
    
    # If document is a procedure, include key sections
    if capsule.get("intent") == "procedure":
        full_doc = _fetch_full_document(title)
        # Extract code blocks and numbered steps
        capsule["procedures"] = extract_procedures(full_doc)
    
    return capsule
```

**Option B: Add `get_procedure_steps` tool**
```python
def get_procedure_steps(title: str) -> str:
    """Extract numbered steps and code blocks from a procedure document."""
    doc = fetch_document(title)
    steps = extract_numbered_lists(doc)
    commands = extract_code_blocks(doc)
    return format_procedure(steps, commands)
```

**Option C: Prompt engineering**
Add to ReAct signature:
> "When a document is classified as intent=procedure, always retrieve the full document content, not just the summary."

---

## Issue 2: Intermittent Missing Reasoning Trace

### Observed Behavior
- First SSL question: No `🧠 Reasoning Trace` displayed
- Second SSL question: Full trace with 5 steps
- Database question: Full trace with 5 steps

### Root Cause Analysis
In `react_agent.py`, `_extract_trajectory()` tries multiple formats:
1. `trajectory` / `trace` / `traces` attributes
2. Dict with `thought_N` / `tool_name_N` keys
3. List of step dicts

The first response likely had trajectory data in an unrecognized format, or the agent completed in a single step (no tool calls).

### Recommendation
**Add fallback logging in `_extract_trajectory`:**
```python
def _extract_trajectory(self, result) -> List[Dict[str, Any]]:
    trajectory = []
    
    # ... existing extraction logic ...
    
    if not trajectory:
        # Log full result structure for debugging
        logger.warning(f"Empty trajectory. Result keys: {dir(result)}")
        logger.warning(f"Result dict: {getattr(result, '__dict__', {})}")
        
        # Fallback: capture at least the reasoning if present
        if hasattr(result, 'rationale') and result.rationale:
            trajectory.append({
                "thought": result.rationale,
                "action": "direct_answer",
                "observation": ""
            })
    
    return trajectory
```

---

## Issue 3: Answers Lack Specific Values

### Observed Behavior
| Question | Expected | Returned |
|----------|----------|----------|
| SSL rotation | "approval within 1 hour for SEV-1" | ❌ Not mentioned |
| SSL rotation | "#incidents Slack channel" | ⚠️ "designated Slack channel" |
| PITR backup | "Daily at 02:00 UTC" | ⚠️ "Daily full backups" |
| PITR backup | "30 days retention" | ❌ Not mentioned |
| Incident mgmt | "5-minute response time" | ❌ Not mentioned |
| Incident mgmt | "#incident channel" | ✅ Found via get_facts() || Kong rate limit | Partner: 5000 req/min | ❌ Said "1000" (wrong row!) |
| Kong rate limit | `redis-ratelimit` | ✅ Correct |
### Root Cause
The agent synthesizes a general explanation rather than extracting specific facts from the knowledge base.

### Recommendation
**Add fact extraction step before synthesis:**
```python
class ExtractKeyFacts(dspy.Signature):
    """Extract specific values, numbers, names, and commands from context."""
    
    context: str = dspy.InputField()
    question: str = dspy.InputField()
    
    key_facts: str = dspy.OutputField(
        desc="Bullet list of specific values: times, durations, "
             "channel names, commands, thresholds, etc."
    )
```

Then include `key_facts` in the final answer synthesis.

---

## Issue 4: Verifier Doesn't Guide Improvement

### Observed Behavior
- Verifier returns `(Verified: Partial)` but agent still finishes
- No second pass to fill gaps

### Root Cause
The verifier runs **after** the agent finishes and only appends a status note.

### Recommendation
**Make verification actionable:**
```python
class VerifyAnswer(dspy.Signature):
    """Verify and identify gaps in the answer."""
    
    question: str = dspy.InputField()
    draft_answer: str = dspy.InputField()
    gathered_context: str = dspy.InputField()
    
    verification_status: str = dspy.OutputField(
        desc="'Complete', 'Partial', or 'Insufficient'"
    )
    missing_information: str = dspy.OutputField(
        desc="Specific information that should be added"
    )
    suggested_searches: str = dspy.OutputField(
        desc="Tool calls that might find missing information"
    )
```

If status is "Partial", trigger additional search iterations.

---

## Issue 5: Entity Naming Mismatches Prevent Fact Retrieval

### Observed Behavior
When asked about "Communication Lead" responsibilities during SEV-1:
```
Action: get_facts({"subject": "Communication Lead", "limit": 5})
Observation: No facts found with subject='Communication Lead'.
```

Yet the knowledge base has this role as "Communications" (assigned by IC).

### Root Cause
The question uses "Communication Lead" but the KB stores it as:
- A role name: "Communications" (one of: Communications, Technical Lead, Scribe)
- Not a standalone entity with its own facts

The agent correctly tried `get_facts()` but the entity name didn't match.

### Evidence from Trace
```
Step 3: get_facts({"subject": "Incident Commander", "limit": 5})
→ Found 5 facts including "assign roles: Communications, Technical Lead, Scribe"

Step 4: get_facts({"subject": "Communication Lead", "limit": 5})  
→ No facts found
```

### Recommendation
**Option A: Fuzzy entity matching in `get_facts`**
```python
def get_facts(subject: str, limit: int = 5) -> List[str]:
    # Try exact match first
    facts = db.query_facts(subject=subject, limit=limit)
    
    if not facts:
        # Try fuzzy/partial matching
        similar = find_similar_entities(subject, threshold=0.7)
        for entity in similar:
            facts.extend(db.query_facts(subject=entity, limit=limit))
    
    return facts
```

**Option B: Add entity alias resolution**
```python
ENTITY_ALIASES = {
    "Communication Lead": ["Communications", "Comms Lead"],
    "Tech Lead": ["Technical Lead"],
    # ...
}

def resolve_entity(name: str) -> List[str]:
    """Return the canonical name and any aliases."""
    return ENTITY_ALIASES.get(name, [name])
```

**Option C: Prompt the agent to search for partial matches**
Add to tool description:
> "If no facts found, try searching for partial entity names or related roles."

---

## Issue 6: `get_facts()` Works Well But Is Underutilized

### Observed Behavior (Positive!)
For the Incident Commander question, `get_facts()` returned excellent structured data:
```
• Incident Commander must declare severity in #incident Slack channel
• Incident Commander must create war room if SEV-1/SEV-2
• Incident Commander must assign roles: Communications, Technical Lead, Scribe
• Incident Commander must coordinate response until resolution
```

This is **exactly** what the answer needed, and the agent used it correctly.

### Contrast with Earlier Questions
- SSL question: Used `get_capsule()` → got summary, missed details
- PITR question: Used `get_capsule()` → got summary, missed commands
- Incident question: Used `get_facts()` → got structured facts, good answer

### Recommendation
**Encourage `get_facts()` usage in the ReAct prompt:**
```
When answering questions about roles, responsibilities, or relationships:
1. First use get_facts(subject="<entity>") to retrieve structured facts
2. Use get_capsule() only for document summaries
3. For procedures, retrieve full document content
```

**Add to tool selection heuristics:**
- Question contains "responsibilities" / "role" / "who" → prioritize `get_facts()`
- Question contains "procedure" / "how to" / "steps" → get full document
- Question contains "what is" / "explain" → `get_capsule()` may suffice

---

## Updated Priority Order

1. **Issue 1** (Capsule insufficient) - Highest impact, affects all procedure questions
2. **Issue 7** (Truncated snippets) - High impact, causes incorrect value extraction
3. **Issue 3** (Missing specifics) - High impact, makes answers less actionable  
4. **Issue 5** (Entity mismatch) - Medium impact, causes failed fact lookups
5. **Issue 4** (Verifier passive) - Medium impact, could auto-improve partial answers
6. **Issue 6** (Underutilized get_facts) - Low effort win, just needs prompt tuning
7. **Issue 2** (Trace missing) - Lower impact, mainly affects debugging/UX

---

## Issue 7: Search Snippets Truncated, Causing Value Misreads

### Observed Behavior
For the Kong rate limiting question, the agent:
1. Searched and found `API_Gateway_Configuration` with rate limit table
2. Saw truncated snippet in observation:
   ```
   | Partner | 5000 | 500 |
   ```
3. But answered with **wrong value**: "1000 requests per minute" (Authenticated tier, not Partner)

### Evidence from Trace
Step 1 observation showed the correct table:
```
| Tier | Requests/minute | Burst |
|------|-----------------|-------|
| Anonymous | 60 | 10 |
| Authenticated | 1000 | 100 |
| Partner | 5000 | 500 |
| Internal | Unlimited | - |
```

But the YAML config was cut off:
```yaml
plugins:
- name: rate-limiting
  route: 
```

The agent never retrieved the full document to see `redis_host: redis-ratelimit` in context.

### Root Cause
1. Search returns **snippets**, not full sections
2. Agent synthesizes from partial data instead of following up
3. No heuristic to call `get_capsule()` or full document when snippets are truncated

### Recommendation
**Option A: Detect truncation and auto-fetch full content**
```python
# In search result processing
if observation.endswith("...") or "route: \n" in observation:
    # Snippet appears truncated, fetch full document
    full_doc = get_capsule(document_title)
```

**Option B: Add prompt guidance**
```
When search results show tables or YAML configs that appear cut off,
always retrieve the full document using get_capsule() before answering.
```

**Option C: Increase snippet size for config documents**
```python
# In search indexing
if doc.intent == "configuration":
    snippet_size = 1000  # Larger snippets for configs
else:
    snippet_size = 500
```

**Option D: Add `get_config_block(title, block_name)` tool**
```python
def get_config_block(title: str, block_name: str) -> str:
    """Extract a specific YAML/config block from a document."""
    doc = fetch_document(title)
    blocks = extract_code_blocks(doc, language="yaml")
    for block in blocks:
        if block_name.lower() in block.lower():
            return block
    return "Config block not found"
```

---

## Quick Wins

1. Add `intent` check in prompt: *"For procedure documents, retrieve full content"*
2. Log trajectory structure when empty for debugging
3. Add `get_document_section(title, section_name)` tool for targeted retrieval
4. Add fuzzy matching for entity names in `get_facts()`
5. Update ReAct prompt to prefer `get_facts()` for role/responsibility questions
6. Add prompt: *"When snippets appear truncated, fetch full document before answering"*

---

## Test Results Summary

| Question | Verification | Key Wins | Key Gaps |
|----------|--------------|----------|----------|
| Q1: SSL rotation | Partial | Hot-reload, war room | SDS mechanism, approval timeline |
| Q2: PITR backup | Partial | WAL concept, drills | Commands, RTO/RPO, storage |
| Q3: Incident roles | Partial | IC responsibilities via get_facts(), #incident channel | Communication Lead not found, response time |
| Q4: Kong rate limiting | Partial | Found `redis-ratelimit` | Wrong rate value (1000 vs 5000), no YAML config |
