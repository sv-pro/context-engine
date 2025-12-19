"""
Markdown chunker for splitting articles into smaller, embeddable pieces.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    """Represents a chunk of a markdown document."""
    content: str
    chunk_index: int
    section: Optional[str] = None
    line_start: int = 0
    line_end: int = 0


def estimate_tokens(text: str) -> int:
    """
    Estimate token count (rough approximation: ~4 chars per token).
    """
    return len(text) // 4


def split_markdown(
    content: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50
) -> List[Chunk]:
    """
    Split markdown content into chunks suitable for embedding.
    
    Args:
        content: The full markdown content
        max_tokens: Maximum tokens per chunk (~500 is good for most embedding models)
        overlap_tokens: Number of tokens to overlap between chunks for context continuity
    
    Returns:
        List of Chunk objects
    """
    if not content or not content.strip():
        return []
    
    lines = content.split('\n')
    chunks = []
    
    current_chunk_lines = []
    current_section = None
    current_tokens = 0
    chunk_start_line = 0
    
    max_chars = max_tokens * 4  # Approximate chars
    overlap_chars = overlap_tokens * 4
    
    for i, line in enumerate(lines):
        # Track section headers
        if line.startswith('#'):
            # Extract section name
            match = re.match(r'^#+\s+(.+)$', line)
            if match:
                current_section = match.group(1).strip()
        
        line_chars = len(line) + 1  # +1 for newline
        
        # Check if adding this line would exceed max
        if current_tokens + (line_chars // 4) > max_tokens and current_chunk_lines:
            # Save current chunk
            chunk_content = '\n'.join(current_chunk_lines)
            chunks.append(Chunk(
                content=chunk_content,
                chunk_index=len(chunks),
                section=current_section,
                line_start=chunk_start_line,
                line_end=i - 1
            ))
            
            # Start new chunk with overlap
            # Keep last N characters worth of lines for overlap
            overlap_content = chunk_content[-overlap_chars:] if len(chunk_content) > overlap_chars else ""
            overlap_lines = overlap_content.split('\n')
            
            current_chunk_lines = overlap_lines + [line]
            current_tokens = estimate_tokens('\n'.join(current_chunk_lines))
            chunk_start_line = max(0, i - len(overlap_lines))
        else:
            current_chunk_lines.append(line)
            current_tokens += line_chars // 4
    
    # Don't forget the last chunk
    if current_chunk_lines:
        chunks.append(Chunk(
            content='\n'.join(current_chunk_lines),
            chunk_index=len(chunks),
            section=current_section,
            line_start=chunk_start_line,
            line_end=len(lines) - 1
        ))
    
    # If the entire content is small enough, just return one chunk
    if len(chunks) == 0 and content.strip():
        chunks.append(Chunk(
            content=content,
            chunk_index=0,
            section=None,
            line_start=0,
            line_end=len(lines) - 1
        ))
    
    logger.debug(f"Split content into {len(chunks)} chunks")
    return chunks


def chunk_with_headers(content: str, max_tokens: int = 500) -> List[Chunk]:
    """
    Alternative chunking strategy: split by headers.
    Each H2/H3 section becomes its own chunk.
    """
    if not content or not content.strip():
        return []
    
    # Split by headers (## or ###)
    sections = re.split(r'\n(?=##[^#])', content)
    
    chunks = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        
        # If section is still too large, use the regular splitter
        if estimate_tokens(section) > max_tokens:
            sub_chunks = split_markdown(section, max_tokens)
            for sub_chunk in sub_chunks:
                sub_chunk.chunk_index = len(chunks)
                chunks.append(sub_chunk)
        else:
            # Extract section title
            match = re.match(r'^##\s+(.+)', section)
            section_name = match.group(1) if match else None
            
            chunks.append(Chunk(
                content=section,
                chunk_index=len(chunks),
                section=section_name,
                line_start=0,
                line_end=section.count('\n')
            ))
    
    return chunks
