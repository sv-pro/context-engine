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
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
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

    return {
        "metadata": metadata,
        "content": clean_content.strip(),
        "links": links
    }
