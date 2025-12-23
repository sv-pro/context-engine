import re
import yaml
import logging

logger = logging.getLogger(__name__)

def parse_markdown(content):
    """
    Parses markdown content to extract:
    - Frontmatter (YAML)
    - Wikilinks ([[Link]])
    - Clean content
    """
    metadata = {}
    links = []
    clean_content = content

    # 1. Extract Frontmatter
    # Allow optional whitespace at start
    # Match content between --- delimiters, handling potential lack of trailing newline
    frontmatter_pattern = r'^\s*---\s*\n(.*?)\n---\s*'
    match = re.search(frontmatter_pattern, content, re.DOTALL)
    if match:
        try:
            metadata = yaml.safe_load(match.group(1))
            clean_content = content[match.end():]
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML: {e}")

    # 2. Extract Wikilinks
    # Matches [[Link]] or [[Link|Alias]]
    link_pattern = r'\[\[(.*?)(?:\|.*?)?\]\]'
    links = re.findall(link_pattern, clean_content)

    # 3. Strip existing footer sections to prevent duplication
    # Remove any "---\n## Related" footer blocks (including variations)
    # Handle cases where --- appears without newline (e.g., "text.---")
    footer_pattern = r'\.?---+\s*\n##\s+Related\s*\n(?:- \[\[.*?\]\]\s*\n*)*'
    clean_content = re.sub(footer_pattern, '.', clean_content, flags=re.MULTILINE)
    
    # Remove trailing periods and whitespace
    clean_content = re.sub(r'\.\s*$', '', clean_content)

    return {
        "metadata": metadata,
        "content": clean_content.strip(),
        "links": links
    }
