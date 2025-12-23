
import yaml
import re
import datetime

# Mock enricher logic
def generate_frontmatter(metadata):
    safe_metadata = {}
    for k, v in metadata.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            safe_metadata[k] = v.isoformat()
        else:
            safe_metadata[k] = v
            
    # replicate enricher.py exactly
    yaml_str = yaml.dump(safe_metadata, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---"

# Mock parser logic
def parse(content):
    # The regex from my previous edit
    frontmatter_pattern = r'^\s*---\s*\n(.*?)\n---\s*'
    match = re.search(frontmatter_pattern, content, re.DOTALL)
    if match:
        return yaml.safe_load(match.group(1))
    return None

# Test
metadata = {
    "title": "Test Note",
    "last_modified": "2025-12-23T07:50:12.471486"
}

generated = generate_frontmatter(metadata)
content = f"{generated}\n\n# Some Content"

print(f"Generated Frontmatter:\n{generated!r}")
print(f"Full Content Start:\n{content[:50]!r}")

parsed = parse(content)
print(f"Parsed Metadata: {parsed}")

if parsed and parsed.get('last_modified') == metadata['last_modified']:
    print("SUCCESS: Metadata preserved")
else:
    print("FAILURE: Metadata lost")
