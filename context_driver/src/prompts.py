
import logging
from litellm import completion
from config import current_config

logger = logging.getLogger(__name__)

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

        response = completion(
            model="gpt-4o-mini", # Explicitly use a cheap/fast model for keywords? Or current_config.model? Logs showed gpt-4o-mini
            messages=[{"role": "user", "content": prompt}]
        )
        
        keywords_text = response.choices[0].message.content.strip()
        # Clean up
        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        return keywords
        
    except Exception as e:
        logger.error(f"Failed to extract keywords: {e}")
        return []
