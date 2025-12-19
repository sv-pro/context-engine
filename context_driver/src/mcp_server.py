import os
import json
import logging
import asyncio
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
from db import Database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-kb-server")

# FastMCP constructor
mcp = FastMCP("Brain Knowledge Base")

# Database connection
db = Database()

@mcp.tool()
async def search_kb(query: str, limit: int = 5) -> str:
    """
    Search the knowledge base for information using semantic search.
    
    Args:
        query: The search query (natural language)
        limit: Number of results to return (default: 5)
    """
    try:
        from main import get_embedding
        
        query_vector = get_embedding(query)
        if not query_vector:
            return "Failed to generate embedding for search query."
        
        results = db.search(query, query_vector, strategy="super_hybrid", limit=limit)
        
        if not results:
            return "No relevant information found in the knowledge base."
        
        formatted_results = []
        for i, row in enumerate(results):
            file_path, title, content, section, similarity = row
            section_info = f" > {section}" if section else ""
            formatted_results.append(
                f"### Result {i+1}: {title}{section_info}\n"
                f"Source: {file_path}\n"
                f"Similarity: {similarity:.4f}\n"
                f"--- CONTENT ---\n"
                f"{content}\n"
            )
            
        return "\n\n".join(formatted_results)
    except Exception as e:
        logger.error(f"Error in search_kb: {e}")
        return f"Error performing search: {str(e)}"

@mcp.tool()
async def get_article(title_or_path: str) -> str:
    """
    Retrieve the full content of a specific article by its title or file path.
    
    Args:
        title_or_path: The title of the article or its file path.
    """
    try:
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT title, content, file_path, metadata 
                FROM brain.notes 
                WHERE title ILIKE %s OR file_path = %s
                LIMIT 1
            """, (title_or_path, title_or_path))
            
            row = cur.fetchone()
            if not row:
                return f"Article '{title_or_path}' not found."
            
            title, content, file_path, metadata = row
            keywords = metadata.get('keywords', [])
            keywords_str = f"Keywords: {', '.join(keywords)}\n" if keywords else ""
            
            return (
                f"# {title}\n"
                f"Path: {file_path}\n"
                f"{keywords_str}"
                f"---\n\n"
                f"{content}"
            )
    except Exception as e:
        logger.error(f"Error in get_article: {e}")
        return f"Error retrieving article: {str(e)}"

@mcp.tool()
async def list_articles(filter_text: Optional[str] = None) -> str:
    """
    List all available articles in the knowledge base.
    
    Args:
        filter_text: Optional text to filter the list of articles by title.
    """
    try:
        with db.conn.cursor() as cur:
            if filter_text:
                cur.execute("""
                    SELECT title, file_path 
                    FROM brain.notes 
                    WHERE title ILIKE %s 
                    ORDER BY title ASC
                """, (f"%{filter_text}%",))
            else:
                cur.execute("""
                    SELECT title, file_path 
                    FROM brain.notes 
                    ORDER BY title ASC
                """)
                
            rows = cur.fetchall()
            if not rows:
                return "No articles found."
            
            lines = [f"- {row[0]} ({row[1]})" for row in rows]
            return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in list_articles: {e}")
        return f"Error listing articles: {str(e)}"

@mcp.tool()
async def get_related(title_or_path: str) -> str:
    """
    Get related articles based on wikilinks found in a specific document.
    
    Args:
        title_or_path: The title or path of the article to find related links for.
    """
    try:
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT id, title FROM brain.notes 
                WHERE title ILIKE %s OR file_path = %s
                LIMIT 1
            """, (title_or_path, title_or_path))
            
            row = cur.fetchone()
            if not row:
                return f"Article '{title_or_path}' not found."
            
            note_id, title = row
            cur.execute("SELECT target_title FROM brain.links WHERE source_note_id = %s", (note_id,))
            outgoing = cur.fetchall()
            cur.execute("SELECT n.title FROM brain.links l JOIN brain.notes n ON l.source_note_id = n.id WHERE l.target_title = %s", (title,))
            incoming = cur.fetchall()
            
            result = [f"Related to '{title}':\n"]
            if outgoing:
                result.append("Outgoing Links:")
                for link in outgoing: result.append(f"- [[{link[0]}]]")
            if incoming:
                result.append("\nIncoming Links:")
                for link in incoming: result.append(f"- [[{link[0]}]]")
                
            return "\n".join(result)
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()
