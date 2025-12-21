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



def enrich_markdown(content, metadata, links):
    """
    Combines frontmatter and content.
    Links are now added to frontmatter as 'related' field instead of footer.
    """
    # Add links to metadata
    if links:
        # De-duplicate and sort links
        metadata['related'] = sorted(list(set(links)))
    
    header = generate_frontmatter(metadata)
    
    # Combine - no footer anymore
    enriched = f"{header}\n\n{content.strip()}"
    
    return enriched
