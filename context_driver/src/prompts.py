
import logging
from litellm import completion
from config import current_config

logger = logging.getLogger(__name__)

import json

def extract_graph_elements(content, title):
    """
    Extracts structured graph elements (Entities and Relationships) from the document.
    Returns a dictionary with 'entities' and 'relationships' lists.
    """
    try:
        # Construct prompt
        prompt = f"""
Document Title: {title}

Content Fragment:
{content[:2500]}

INSTRUCTIONS:
You are an expert Knowledge Graph builder. Your task is to extract structured knowledge from the text above.
1. Identify key **Entities** (nodes) that are central to the document.
   - Types: Person, Organization, Location, Event, Concept, Technology, etc.
   - Provide a brief description for each.
2. Identify **Relationships** (edges) between these entities or between the document and entities.
   - Format: Source -> Relation -> Target
   - Relation examples: "founded_by", "located_in", "uses", "developed", "relates_to".

OUTPUT FORMAT:
Return ONLY a valid JSON object with detailed keys. Do not include markdown naming like ```json ... ```.
{{
  "entities": [
    {{ "name": "Exact Name", "type": "Type", "description": "Brief description..." }}
  ],
  "relationships": [
    {{ "source": "Entity Name", "target": "Entity Name", "type": "relation_type", "description": "Context..." }}
  ]
}}

Ensure "Source" and "Target" names exactly match the "name" field in the entities list.
"""
        logger.info(f"=== PROMPT TO LITELLM [extract_graph] ===\nModel: {current_config.model}\n... (truncated) ...")

        # Use a capable model for structured extraction
        # If current_config.model is embedding model, we must force a chat model.
        # Ideally, main.py should pass the chat model name. Assuming we have a global default or env.
        chat_model = "gpt-4o-mini" # or REAL_MODEL from main.py if passed, but this module doesn't see main's scope easily.
        
        # We'll rely on the default chat model logic.
        # Note: In the future, pass 'model' as arg or import central config.
        
        response = completion(
            model=chat_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" } # Force JSON if supported
        )
        
        result_text = response.choices[0].message.content.strip()
        # Clean potential markdown fences if model ignores instruction
        if result_text.startswith("```"):
            result_text = result_text.strip("`").replace("json\n", "", 1)
            
        data = json.loads(result_text)
        return data
        
    except Exception as e:
        logger.error(f"Failed to extract graph elements: {e}")
        # Return empty structure on failure
        return {"entities": [], "relationships": []}

def extract_keywords(content, title):
    """
    Extracts 5-8 descriptive keywords from the document content using an LLM.
    """
    try:
        # Construct prompt
        prompt = f"""
Document Title: {title}

Content Fragment:
{content[:2000]}

INSTRUCTIONS:
Summarize this document into a set of 5-8 highly descriptive keywords or short tags.
These keywords should act as a 'human-readable embedding' - they should capture the unique identity and context of the document.
Return ONLY a comma-separated list of keywords. No prose, no intro.
"""
        logger.info(f"=== PROMPT TO LITELLM [extract_keywords] ===\nModel: {current_config.model}\nMessage 1 [user]:\n{prompt}\n=== END PROMPT ===")

        # Use a cheap/fast model for keywords
        chat_model = "gpt-4o-mini"
        
        from litellm import completion # Ensure completion is available if not global, but assuming it is from top of file
        response = completion(
            model=chat_model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        keywords_text = response.choices[0].message.content.strip()
        # Clean up
        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        return keywords
        
    except Exception as e:
        logger.error(f"Failed to extract keywords: {e}")
        return []


# === NEUROSYMBOLIC INGESTION PROMPTS ===

def condense_document(content: str, title: str) -> dict:
    """
    Pass #1: CONDENSE - Extract core meaning from document.
    Returns: {summary, key_points, intent, domain, confidence}
    """
    try:
        prompt = f"""
Document Title: {title}

Content:
{content[:4000]}

INSTRUCTIONS:
You are condensing this document into its core meaning. Extract:

1. **summary**: A 2-3 sentence summary capturing the essential information.
2. **key_points**: List of 3-7 bullet points with the most important facts.
3. **intent**: Classify as ONE of: procedure, fact, policy, incident, reference, unknown
4. **domain**: Primary domain (e.g., ssl, networking, auth, database, infrastructure, security)
5. **confidence**: Your confidence in this extraction (0.0-1.0)

OUTPUT FORMAT (JSON only, no markdown):
{{
  "summary": "...",
  "key_points": ["...", "..."],
  "intent": "procedure",
  "domain": "ssl",
  "confidence": 0.9
}}
"""
        chat_model = "gpt-4o-mini"
        response = completion(
            model=chat_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.strip("`").replace("json\n", "", 1)
        
        data = json.loads(result_text)
        logger.info(f"Condensed '{title}' -> intent={data.get('intent')}, domain={data.get('domain')}")
        return data
        
    except Exception as e:
        logger.error(f"Failed to condense document: {e}")
        return {"summary": "", "key_points": [], "intent": "unknown", "domain": "unknown", "confidence": 0.0}


def extract_facts(content: str, title: str, capsule: dict) -> dict:
    """
    Pass #2: STRUCTURE - Extract subject-predicate-object facts.
    Returns: {entities: [...], facts: [...]}
    """
    try:
        summary = capsule.get("summary", "")
        key_points = capsule.get("key_points", [])
        
        prompt = f"""
Document Title: {title}
Summary: {summary}
Key Points: {json.dumps(key_points)}

Content (for detail):
{content[:3000]}

INSTRUCTIONS:
Extract structured facts as subject-predicate-object triples.

1. **entities**: Named things mentioned (people, systems, services, concepts)
2. **facts**: Relationships between entities as triples

Predicate examples: uses, located_in, managed_by, expires_in, depends_on, triggers, causes, contains, created_by

OUTPUT FORMAT (JSON only):
{{
  "entities": [
    {{"name": "SSL Certificate", "type": "artifact"}},
    {{"name": "Let's Encrypt", "type": "service"}}
  ],
  "facts": [
    {{"subject": "SSL Certificate", "predicate": "issued_by", "object": "Let's Encrypt"}},
    {{"subject": "SSL Certificate", "predicate": "expires_in", "object": "90 days"}}
  ]
}}
"""
        chat_model = "gpt-4o-mini"
        response = completion(
            model=chat_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.strip("`").replace("json\n", "", 1)
        
        data = json.loads(result_text)
        logger.info(f"Extracted {len(data.get('facts', []))} facts from '{title}'")
        return data
        
    except Exception as e:
        logger.error(f"Failed to extract facts: {e}")
        return {"entities": [], "facts": []}


def distill_rules(content: str, title: str, capsule: dict, facts: list) -> dict:
    """
    Pass #3: DISTILL RULES - Extract IF-THEN logic from document.
    Returns: {rules: [...]}
    """
    try:
        intent = capsule.get("intent", "unknown")
        summary = capsule.get("summary", "")
        
        # Only extract rules from procedural/policy documents
        if intent not in ["procedure", "policy", "incident"]:
            logger.debug(f"Skipping rule extraction for intent={intent}")
            return {"rules": []}
        
        prompt = f"""
Document Title: {title}
Intent: {intent}
Summary: {summary}
Known Facts: {json.dumps(facts[:10])}

Content:
{content[:3000]}

INSTRUCTIONS:
Extract executable IF-THEN rules from this document.

Rules describe:
- **Conditions**: When something is true (e.g., "certificate expires in < 30 days")
- **Actions**: What should happen (e.g., "trigger renewal", "alert team", "block request")
- **Severity**: critical, high, normal, low

OUTPUT FORMAT (JSON only):
{{
  "rules": [
    {{
      "rule_id": "rule_unique_name",
      "condition": "condition expression",
      "action": "action to take",
      "severity": "critical"
    }}
  ]
}}

If no rules can be extracted, return {{"rules": []}}
"""
        chat_model = "gpt-4o-mini"
        response = completion(
            model=chat_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.strip("`").replace("json\n", "", 1)
        
        data = json.loads(result_text)
        logger.info(f"Distilled {len(data.get('rules', []))} rules from '{title}'")
        return data
        
    except Exception as e:
        logger.error(f"Failed to distill rules: {e}")
        return {"rules": []}
