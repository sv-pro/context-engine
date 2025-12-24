
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
