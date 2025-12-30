"""
DSPy Tools for Knowledge Base Access.

Provides callable tool functions for DSPy ReAct agents to interact with the knowledge base.
Each function is designed to be used as a tool in dspy.ReAct(tools=[...]).
"""

import logging
from typing import Optional
from db import Database

logger = logging.getLogger("dspy-tools")

# Singleton database connection
_db: Optional[Database] = None

def _get_db() -> Database:
    """Get or create database connection."""
    global _db
    if _db is None:
        _db = Database()
    return _db


def search_knowledge_base(query: str, limit: int = 5) -> str:
    """
    Search the knowledge base for documents relevant to the query.
    
    NOTE: Search results show snippets only. If you see truncated tables or 
    YAML configs (ending with incomplete lines), use get_document_section() 
    or get_capsule() to retrieve the full content.
    
    Args:
        query: Natural language search query
        limit: Maximum number of results (default 5)
    
    Returns:
        Formatted string of search results with titles and content snippets
    """
    from main import get_embedding
    
    db = _get_db()
    
    # Get query embedding
    vector = get_embedding(query)
    if not vector:
        return "Error: Failed to generate query embedding."
    
    try:
        # Fetch more results so we can filter and prioritize
        results = db.semantic_search(vector, limit=limit * 3)
        
        if not results:
            return f"No results found for query: '{query}'"
        
        # Separate documents from entities - prioritize actual documents
        documents = []
        entities = []
        
        for r in results:
            file_path = r[0] if len(r) > 0 else ""
            title = r[1] if len(r) > 1 else "Untitled"
            
            # Skip previous investigation artifacts to avoid context pollution/loops
            if title.startswith("Investigation_"):
                continue
            
            # Classify by file path
            if '/entities/' in file_path:
                entities.append(r)
            else:
                documents.append(r)
        
        # Prioritize: documents first, then entities (with note about source)
        prioritized = documents[:limit] + entities[:(limit - len(documents[:limit]))]
        
        output = []
        for i, r in enumerate(prioritized, 1):
            file_path = r[0] if len(r) > 0 else ""
            title = r[1] if len(r) > 1 else "Untitled"
            raw_content = r[2] or "" if len(r) > 2 else ""
            section = r[3] if len(r) > 3 else ""
            score = r[4] if len(r) > 4 else 0.0
            
            # Smart truncation: try to preserve complete code blocks and tables
            # Increase limit for config-heavy content
            max_len = 800 if ('```' in raw_content or '|' in raw_content) else 500
            
            if len(raw_content) > max_len:
                # Try to cut at a natural boundary
                content = raw_content[:max_len]
                # If we're in the middle of a code block, try to find its end
                if '```' in content and content.count('```') % 2 == 1:
                    # Incomplete code block - extend to close it or note truncation
                    next_close = raw_content.find('```', max_len)
                    if next_close != -1 and next_close < max_len + 300:
                        content = raw_content[:next_close + 3]
                    else:
                        content += "\n# ... [truncated - use get_document_section() for full content]"
                else:
                    content += "\n... [truncated]"
            else:
                content = raw_content
            
            section_info = f" > {section}" if section else ""
            
            # Add hint for entity pages pointing to source documents
            if '/entities/' in file_path:
                # Try to find source document from relationships
                source_hint = ""
                if 'configured_by' in raw_content.lower() or 'from' in raw_content.lower():
                    # Extract document references from wiki links
                    import re
                    refs = re.findall(r'\[\[([^\]]+)\]\]', raw_content)
                    if refs:
                        source_hint = f"\n[TIP: For config values, try get_capsule(\"{refs[0]}\")]"
                output.append(f"[{i}] {title}{section_info} (score: {score:.2f}) [ENTITY PAGE]{source_hint}\n{content}\n")
            else:
                output.append(f"[{i}] {title}{section_info} (score: {score:.2f})\n{content}\n")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"search_knowledge_base failed: {e}")
        return f"Error searching knowledge base: {e}"


def get_facts(subject: Optional[str] = None, predicate: Optional[str] = None, limit: int = 10) -> str:
    """
    Query extracted facts (subject-predicate-object triples) from the knowledge base.
    
    Args:
        subject: Filter by subject entity (optional) - supports fuzzy matching
        predicate: Filter by predicate/relationship (optional)
        limit: Maximum number of facts to return (default 10)
    
    Returns:
        Formatted list of facts as natural language statements
    """
    db = _get_db()
    
    try:
        facts = db.get_facts(subject=subject, predicate=predicate, limit=limit)
        
        # If no exact match and subject provided, try fuzzy matching
        if not facts and subject:
            logger.info(f"No exact match for subject '{subject}', trying fuzzy match")
            
            # Try to find similar entities
            with db.conn.cursor() as cur:
                # Search for entities containing the subject term or similar
                cur.execute("""
                    SELECT DISTINCT subject FROM brain.facts 
                    WHERE subject ILIKE %s OR subject ILIKE %s
                    LIMIT 5
                """, (f"%{subject}%", f"%{subject.replace(' ', '_')}%"))
                similar_subjects = [row[0] for row in cur.fetchall()]
            
            if similar_subjects:
                logger.info(f"Found similar entities: {similar_subjects}")
                for similar in similar_subjects:
                    similar_facts = db.get_facts(subject=similar, predicate=predicate, limit=limit)
                    facts.extend(similar_facts)
                
                if facts:
                    # Deduplicate
                    seen = set()
                    unique_facts = []
                    for f in facts:
                        key = (f.get("subject"), f.get("predicate"), f.get("object"))
                        if key not in seen:
                            seen.add(key)
                            unique_facts.append(f)
                    facts = unique_facts[:limit]
        
        if not facts:
            filters = []
            if subject:
                filters.append(f"subject='{subject}'")
            if predicate:
                filters.append(f"predicate='{predicate}'")
            filter_str = " with " + ", ".join(filters) if filters else ""
            return f"No facts found{filter_str}."
        
        output = ["Extracted Facts:"]
        for fact in facts:
            s = fact.get("subject", "?")
            p = fact.get("predicate", "?")
            o = fact.get("object", "?")
            source = fact.get("source_title", "unknown")
            output.append(f"• {s} {p} {o} (from: {source})")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"get_facts failed: {e}")
        return f"Error retrieving facts: {e}"


def get_rules(domain: Optional[str] = None, severity: Optional[str] = None, limit: int = 10) -> str:
    """
    Query extracted IF-THEN rules from the knowledge base.
    
    Args:
        domain: Filter by domain (e.g., 'ssl', 'auth', 'database')
        severity: Filter by severity ('low', 'medium', 'high', 'critical')
        limit: Maximum number of rules to return (default 10)
    
    Returns:
        Formatted list of rules with conditions and actions
    """
    db = _get_db()
    
    try:
        rules = db.get_rules(severity=severity, limit=limit)
        
        if not rules:
            filters = []
            if domain:
                filters.append(f"domain='{domain}'")
            if severity:
                filters.append(f"severity='{severity}'")
            filter_str = " with " + ", ".join(filters) if filters else ""
            return f"No rules found{filter_str}."
        
        output = ["Operational Rules:"]
        for rule in rules:
            rule_id = rule.get("rule_id", "?")
            condition = rule.get("condition", "?")
            action = rule.get("action", "?")
            sev = rule.get("severity", "medium")
            source = rule.get("source_title", "unknown")
            output.append(f"• [{sev.upper()}] {rule_id}: IF {condition} THEN {action} (from: {source})")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"get_rules failed: {e}")
        return f"Error retrieving rules: {e}"


def get_capsule(title: str) -> str:
    """
    Get the condensed capsule (summary) for a specific document.
    
    For procedure documents (intent=procedure), this also includes extracted 
    procedure steps and code blocks to ensure complete information.
    
    Args:
        title: Document title to look up
    
    Returns:
        Formatted capsule with summary, key points, and metadata.
        For procedures, also includes steps and commands.
    """
    db = _get_db()
    
    try:
        # First find the note by title
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT id, content FROM brain.notes 
                WHERE title ILIKE %s 
                LIMIT 1
            """, (f"%{title}%",))
            row = cur.fetchone()
            
        if not row:
            return f"No document found with title matching: '{title}'"
        
        note_id, full_content = row
        capsule = db.get_capsule(note_id)
        
        if not capsule:
            return f"No capsule found for document: '{title}'"
        
        output = [
            f"Document: {title}",
            f"Intent: {capsule.get('intent', 'unknown')}",
            f"Domain: {capsule.get('domain', 'unknown')}",
            f"Summary: {capsule.get('summary', 'No summary available.')}",
            "",
            "Key Points:"
        ]
        
        for point in capsule.get("key_points", []):
            output.append(f"• {point}")
        
        # For procedure documents, extract and include procedure steps and code blocks
        intent = capsule.get('intent', '').lower()
        if intent == 'procedure' and full_content:
            import re
            
            # Extract numbered steps (1. Step, 2. Step, etc.)
            numbered_steps = re.findall(r'^\s*\d+\.\s+\*?\*?(.+?)(?:\*?\*?)$', full_content, re.MULTILINE)
            if numbered_steps:
                output.append("")
                output.append("## Procedure Steps:")
                for i, step in enumerate(numbered_steps[:15], 1):  # Limit to 15 steps
                    output.append(f"{i}. {step.strip()}")
            
            # Extract code blocks
            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', full_content, re.DOTALL)
            if code_blocks:
                output.append("")
                output.append("## Key Commands:")
                for block in code_blocks[:5]:  # Limit to 5 code blocks
                    # Trim long blocks
                    block_lines = block.strip().split('\n')
                    if len(block_lines) > 10:
                        block_content = '\n'.join(block_lines[:10]) + '\n# ... (truncated)'
                    else:
                        block_content = block.strip()
                    output.append(f"```\n{block_content}\n```")
        
        # Add navigation footer with related documents
        edges = db.get_edges_for_note(note_id, limit=8)
        if edges:
            output.append("")
            output.append("# Related Documents")
            for edge in edges:
                relation_type = edge['type']
                target_title = edge['target_title']
                output.append(f"- [[{target_title}]] ({relation_type})")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"get_capsule failed: {e}")
        return f"Error retrieving capsule: {e}"


def list_documents(domain: Optional[str] = None, intent: Optional[str] = None, limit: int = 10) -> str:
    """
    List documents in the knowledge base, optionally filtered by domain or intent.
    
    Args:
        domain: Filter by domain (e.g., 'ssl', 'networking', 'auth')
        intent: Filter by intent (e.g., 'procedure', 'policy', 'incident')
        limit: Maximum number of documents to list
    
    Returns:
        Formatted list of document titles and metadata
    """
    db = _get_db()
    
    try:
        capsules = db.get_capsules(domain=domain, intent=intent, limit=limit)
        
        if not capsules:
            return "No documents found matching the criteria."
        
        output = ["Documents in Knowledge Base:"]
        for c in capsules:
            title = c.get("source_title", "Untitled")
            intent_val = c.get("intent", "unknown")
            domain_val = c.get("domain", "unknown")
            summary = c.get("summary", "")[:100] + "..." if c.get("summary") else ""
            output.append(f"• [{domain_val}/{intent_val}] {title}")
            if summary:
                output.append(f"  {summary}")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"list_documents failed: {e}")
        return f"Error listing documents: {e}"


def get_related_documents(title: str) -> str:
    """
    Find related documents via knowledge graph links (see_also, emergency procedures, etc.).
    
    Use this when you find a general document but need specific procedures, emergency guides,
    or related policies. For example, if you find "SSL_Certificate_Management" but need
    the emergency rotation procedure, this will show you the link to "SSL_Certificate_Emergency".
    
    Args:
        title: Title of the document to find relationships for
    
    Returns:
        Formatted list of related document links with relationship types
    """
    db = _get_db()
    
    try:
        # Find the note by title
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT id, file_path FROM brain.notes 
                WHERE title ILIKE %s 
                LIMIT 1
            """, (f"%{title}%",))
            row = cur.fetchone()
            
        if not row:
            return f"No document found with title matching: '{title}'"
        
        note_id, file_path = row
        
        # Get relationships from the edges table
        # The edges table has: source_id, target_title, type
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT 
                    e.type as relationship_type,
                    e.target_title
                FROM brain.edges e
                WHERE e.source_id = %s
                ORDER BY e.type, e.target_title
                LIMIT 20
            """, (note_id,))
            edges = cur.fetchall()
        
        if not edges:
            return f"No related documents found for '{title}'"
        
        output = [f"Related documents for '{title}':"]
        for relationship_type, related_title in edges:
            output.append(f"• **{relationship_type}** -> [[{related_title}]]")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"get_related_documents failed: {e}")
        return f"Error retrieving related documents: {e}"


def get_document_section(title: str, section_name: str) -> str:
    """
    Extract a specific section from a document, including full code blocks and procedures.
    
    Use this when you need complete procedure steps, YAML configurations, or command examples
    that may be truncated in search results. This returns the FULL content of the matching section.
    
    Args:
        title: Document title to search in
        section_name: Name of the section to extract (e.g., "Recovery Procedures", "Rate Limiting", "PITR")
    
    Returns:
        Full content of the matching section including all code blocks and steps
    """
    db = _get_db()
    
    try:
        # Find the note by title
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT id, content FROM brain.notes 
                WHERE title ILIKE %s 
                LIMIT 1
            """, (f"%{title}%",))
            row = cur.fetchone()
            
        if not row:
            return f"No document found with title matching: '{title}'"
        
        note_id, content = row
        
        if not content:
            return f"Document '{title}' has no content"
        
        # Try to find the section by header
        import re
        
        # Match markdown headers (## Section Name or ### Section Name)
        section_pattern = rf'^(#{1,4})\s*.*{re.escape(section_name)}.*$'
        lines = content.split('\n')
        
        section_start = None
        section_level = None
        
        for i, line in enumerate(lines):
            match = re.match(section_pattern, line, re.IGNORECASE)
            if match:
                section_start = i
                section_level = len(match.group(1))  # Number of # symbols
                break
        
        if section_start is None:
            # Try fuzzy matching on section headers
            for i, line in enumerate(lines):
                if line.startswith('#') and section_name.lower() in line.lower():
                    section_start = i
                    section_level = len(re.match(r'^(#+)', line).group(1))
                    break
        
        if section_start is None:
            return f"Section '{section_name}' not found in document '{title}'. Available sections: " + \
                   ", ".join([l.lstrip('#').strip() for l in lines if l.startswith('#')][:10])
        
        # Extract until next section of same or higher level
        section_lines = [lines[section_start]]
        for i in range(section_start + 1, len(lines)):
            line = lines[i]
            # Check if this is a new section at same or higher level
            header_match = re.match(r'^(#+)\s+', line)
            if header_match and len(header_match.group(1)) <= section_level:
                break
            section_lines.append(line)
        
        section_content = '\n'.join(section_lines).strip()
        
        # Ensure we got meaningful content
        if len(section_content) < 50:
            return f"Section '{section_name}' found but appears empty or too short"
        
        return f"## Section from '{title}':\n\n{section_content}"
        
    except Exception as e:
        logger.error(f"get_document_section failed: {e}")
        return f"Error retrieving document section: {e}"


# Export tools for DSPy ReAct
KNOWLEDGE_BASE_TOOLS = [
    search_knowledge_base,
    get_facts,
    get_rules,
    get_capsule,
    list_documents,
    get_related_documents,
    get_document_section
]
