import os
import re
import shutil

BRAIN_DIR = "/app/brain"
RAW_DIR = "/app/raw"
LEGACY_DIRS = ["scrubbing-center", "jira", "intentos-specs", "_project", "presentation"]

def strip_frontmatter(content):
    """
    Removes YAML frontmatter if it contains enriched fields.
    """
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if match:
        fm = match.group(1)
        # Check if this is an enriched frontmatter (has source, ingested_at)
        if "source:" in fm or "ingested_at:" in fm or "generated_from:" in fm:
            # Return body only
            return content[match.end():]
    return content

def restore():
    print("Starting Raw Restoration...")
    count = 0
    os.makedirs(RAW_DIR, exist_ok=True)
    
    for subdir in LEGACY_DIRS:
        src_dir = os.path.join(BRAIN_DIR, subdir)
        if not os.path.exists(src_dir):
            print(f"Skipping missing dir: {subdir}")
            continue
            
        for filename in os.listdir(src_dir):
            if filename.endswith(".md"):
                file_path = os.path.join(src_dir, filename)
                with open(file_path, 'r') as f:
                    content = f.read()
                
                clean_content = strip_frontmatter(content)
                
                dest_path = os.path.join(RAW_DIR, filename)
                
                # Check for collision
                if os.path.exists(dest_path):
                    print(f"Warning: Overwriting {filename} in RAW")
                
                with open(dest_path, 'w') as f:
                    f.write(clean_content)
                
                print(f"Restored: {subdir}/{filename} -> RAW")
                count += 1
                
    print(f"Restoration Complete. {count} files moved to {RAW_DIR}.")

if __name__ == "__main__":
    restore()
