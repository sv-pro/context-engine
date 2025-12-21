#!/usr/bin/env python3
"""
Cleanup script to remove all footer sections from brain documents.
Run this once to clean existing duplicates.
"""

import os
import re
import sys

def clean_footer(file_path):
    """Remove all footer sections from a markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_count = content.count('## Related')
        
        # Remove all footer sections
        # Pattern matches: \n---\n## Related\n- [[Link]]\n...
        footer_pattern = r'\n+---+\s*\n##\s+Related\s*\n(?:- \[\[.*?\]\]\s*\n*)*'
        clean_content = re.sub(footer_pattern, '', content, flags=re.MULTILINE)
        
        # Also remove trailing whitespace
        clean_content = clean_content.rstrip() + '\n'
        
        if original_count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(clean_content)
            print(f"✓ {file_path}: Removed {original_count} footer(s)")
            return True
        else:
            print(f"  {file_path}: No footers found")
            return False
            
    except Exception as e:
        print(f"✗ {file_path}: Error - {e}")
        return False

def main():
    brain_dir = "/app/brain"
    
    if not os.path.exists(brain_dir):
        print(f"Error: {brain_dir} does not exist")
        sys.exit(1)
    
    print(f"Cleaning footers from {brain_dir}...")
    print()
    
    cleaned_count = 0
    total_count = 0
    
    for root, dirs, files in os.walk(brain_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                total_count += 1
                if clean_footer(file_path):
                    cleaned_count += 1
    
    print()
    print(f"Summary: Cleaned {cleaned_count}/{total_count} files")

if __name__ == "__main__":
    main()
