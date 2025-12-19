import yaml
import datetime
import re

def generate_frontmatter(metadata):
    """
    Safely generates a YAML frontmatter block.
    """
    # Filter out internal/tuple values that can't be serialized or we don't want in YAML
    safe_metadata = {}
    for k, v in metadata.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            safe_metadata[k] = v.isoformat()
        elif isinstance(v, (str, int, float, bool, list, dict)):
            safe_metadata[k] = v
        else:
            safe_metadata[k] = str(v)
            
    # Ensure standard fields
    if "ingested_at" not in safe_metadata:
        safe_metadata["ingested_at"] = datetime.datetime.now().isoformat()
    if "last_modified" not in safe_metadata:
        safe_metadata["last_modified"] = datetime.datetime.now().isoformat()
        
    yaml_str = yaml.dump(safe_metadata, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---"

def generate_footer(links):
    """
    Generates a 'Related' footer with wikilinks.
    """
    if not links:
        return ""
    
    # De-duplicate links
    unique_links = sorted(list(set(links)))
    
    footer_parts = ["\n\n---", "## Related"]
    for link in unique_links:
        footer_parts.append(f"- [[{link}]]")
    
    return "\n".join(footer_parts)

def enrich_markdown(content, metadata, links):
    """
    Combines frontmatter, content, and footer.
    """
    # 1. Clean existing frontmatter if present (handled by caller or parser usually)
    # But we want to preserve the core content.
    
    header = generate_frontmatter(metadata)
    footer = generate_footer(links)
    
    # Combine
    enriched = f"{header}\n\n{content.strip()}"
    if footer:
        enriched += f"\n{footer}"
        
    return enriched
