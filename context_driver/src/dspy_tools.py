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
        results = db.semantic_search(vector, limit=limit)
        
        if not results:
            return f"No results found for query: '{query}'"
        
        output = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            section = r.get("section", "")
            content = r.get("content", "")[:500]  # Truncate for readability
            score = r.get("similarity", 0.0)
            
            section_info = f" > {section}" if section else ""
            output.append(f"[{i}] {title}{section_info} (score: {score:.2f})\n{content}\n")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"search_knowledge_base failed: {e}")
        return f"Error searching knowledge base: {e}"


def get_facts(subject: Optional[str] = None, predicate: Optional[str] = None, limit: int = 10) -> str:
    """
    Query extracted facts (subject-predicate-object triples) from the knowledge base.
    
    Args:
        subject: Filter by subject entity (optional)
        predicate: Filter by predicate/relationship (optional)
        limit: Maximum number of facts to return (default 10)
    
    Returns:
        Formatted list of facts as natural language statements
    """
    db = _get_db()
    
    try:
        facts = db.get_facts(subject=subject, predicate=predicate, limit=limit)
        
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
    
    Args:
        title: Document title to look up
    
    Returns:
        Formatted capsule with summary, key points, and metadata
    """
    db = _get_db()
    
    try:
        # First find the note by title
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM brain.notes 
                WHERE title ILIKE %s 
                LIMIT 1
            """, (f"%{title}%",))
            row = cur.fetchone()
            
        if not row:
            return f"No document found with title matching: '{title}'"
        
        note_id = row[0]
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


# Export tools for DSPy ReAct
KNOWLEDGE_BASE_TOOLS = [
    search_knowledge_base,
    get_facts,
    get_rules,
    get_capsule,
    list_documents
]
