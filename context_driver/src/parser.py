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

    # 2. Extract Wikilinks with optional types
    # Format: [[Entity]](type) for typed, [[Entity]] for untyped
    links_with_types = []
    
    # First, find typed links: [[Entity]](type)
    typed_pattern = r'\[\[([^\]]+)\]\]\(([^\)]+)\)'
    for match in re.finditer(typed_pattern, clean_content):
        links_with_types.append({
            'target': match.group(1).strip(),
            'type': match.group(2).strip(),
            'is_typed': True
        })
    
    # Then, find simple links [[Entity]] (excluding those already captured as typed)
    # Use negative lookahead to skip typed ones
    simple_pattern = r'\[\[([^\]]+)\]\](?!\()'
    for match in re.finditer(simple_pattern, clean_content):
        target = match.group(1).strip()
        # Skip if it has an alias separator (|)
        if '|' in target:
            target = target.split('|')[0].strip()
        links_with_types.append({
            'target': target,
            'type': None,
            'is_typed': False
        })
    
    # Extract just target names for backwards compatibility
    links = [link['target'] for link in links_with_types]

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
        "links": links,
        "links_with_types": links_with_types
    }
