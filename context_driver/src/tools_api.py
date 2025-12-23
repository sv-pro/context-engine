"""
OpenAPI Tool Endpoints for Open WebUI Integration.

This module exposes the knowledge base tools as REST/OpenAPI endpoints
that can be added to Open WebUI as "OpenAPI Servers" or "Function Calling Servers".

Open WebUI will auto-discover these tools via the OpenAPI spec at /openapi.json
and make them available to reasoning models for function calling.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("tools-api")

router = APIRouter(prefix="/tools", tags=["Knowledge Base Tools"])


# ==================== Request/Response Models ====================

class SearchRequest(BaseModel):
    """Request model for knowledge base search."""
    query: str = Field(..., description="Natural language search query")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of results to return")
    strategy: str = Field("super_hybrid", description="Search strategy: semantic, keyword, hybrid, super_hybrid, graph")


class SearchResult(BaseModel):
    """A single search result from the knowledge base."""
    rank: int = Field(..., description="Result ranking (1 = most relevant)")
    title: str = Field(..., description="Document title")
    section: Optional[str] = Field(None, description="Section within the document")
    file_path: str = Field(..., description="Source file path")
    similarity: float = Field(..., description="Similarity score (0-1)")
    content: str = Field(..., description="Relevant content snippet")


class SearchResponse(BaseModel):
    """Response containing search results."""
    query: str = Field(..., description="Original search query")
    strategy: str = Field(..., description="Search strategy used")
    results: List[SearchResult] = Field(..., description="List of search results")
    total_results: int = Field(..., description="Number of results returned")


class ArticleResponse(BaseModel):
    """Full article content."""
    title: str = Field(..., description="Article title")
    file_path: str = Field(..., description="Source file path")
    keywords: List[str] = Field(default_factory=list, description="Semantic keywords")
    content: str = Field(..., description="Full article content in markdown")


class ArticleListItem(BaseModel):
    """Summary of an article for listing."""
    title: str = Field(..., description="Article title")
    file_path: str = Field(..., description="Source file path")


class ArticleListResponse(BaseModel):
    """Response containing list of articles."""
    filter: Optional[str] = Field(None, description="Filter applied")
    articles: List[ArticleListItem] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles")


class RelatedArticlesResponse(BaseModel):
    """Response containing related articles."""
    source_title: str = Field(..., description="Title of the source article")
    outgoing_links: List[str] = Field(default_factory=list, description="Articles this document links to")
    incoming_links: List[str] = Field(default_factory=list, description="Articles that link to this document")


# ==================== Tool Endpoints ====================

@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search Knowledge Base",
    description="""
Search the knowledge base using semantic similarity, keyword matching, or hybrid strategies.

This tool finds relevant documents and content chunks that match your query.
Use it when you need to find information about a specific topic.

**Strategies:**
- `semantic`: Pure vector similarity search
- `keyword`: Full-text search with PostgreSQL
- `hybrid`: Combines semantic and keyword scores
- `super_hybrid`: Best quality - combines semantic, keyword, and graph traversal
- `graph`: Follow wikilinks between related documents
"""
)
async def search_knowledge_base(request: SearchRequest) -> SearchResponse:
    """Search the knowledge base for relevant information."""
    from db import Database
    from main import get_embedding
    
    db = Database()
    
    query_vector = get_embedding(request.query)
    if not query_vector:
        return SearchResponse(
            query=request.query,
            strategy=request.strategy,
            results=[],
            total_results=0
        )
    
    raw_results = db.search(
        request.query, 
        query_vector, 
        strategy=request.strategy, 
        limit=request.limit
    )
    
    results = []
    for i, row in enumerate(raw_results or []):
        file_path, title, content, section, similarity = row
        results.append(SearchResult(
            rank=i + 1,
            title=title,
            section=section,
            file_path=file_path,
            similarity=round(similarity, 4),
            content=content
        ))
    
    return SearchResponse(
        query=request.query,
        strategy=request.strategy,
        results=results,
        total_results=len(results)
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search Knowledge Base (GET)",
    description="GET version of search for simple queries. Use POST for more control."
)
async def search_knowledge_base_get(
    query: str = Query(..., description="Natural language search query"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of results"),
    strategy: str = Query("super_hybrid", description="Search strategy")
) -> SearchResponse:
    """Search the knowledge base (GET method for convenience)."""
    return await search_knowledge_base(SearchRequest(
        query=query,
        limit=limit,
        strategy=strategy
    ))


@router.get(
    "/article/{title_or_path:path}",
    response_model=ArticleResponse,
    summary="Get Full Article",
    description="""
Retrieve the complete content of a specific article by its title or file path.

Use this when you need the full context of a document, not just a snippet.
"""
)
async def get_article(title_or_path: str) -> ArticleResponse:
    """Retrieve the full content of an article."""
    from db import Database
    
    db = Database()
    
    with db.conn.cursor() as cur:
        cur.execute("""
            SELECT title, content, file_path, metadata 
            FROM brain.notes 
            WHERE title ILIKE %s OR file_path ILIKE %s
            LIMIT 1
        """, (f"%{title_or_path}%", f"%{title_or_path}%"))
        
        row = cur.fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Article '{title_or_path}' not found")
        
        title, content, file_path, metadata = row
        keywords = metadata.get('keywords', []) if metadata else []
        
        return ArticleResponse(
            title=title,
            file_path=file_path,
            keywords=keywords,
            content=content
        )


@router.get(
    "/articles",
    response_model=ArticleListResponse,
    summary="List All Articles",
    description="""
List all available articles in the knowledge base.

Optionally filter by title text. Use this to discover what topics are available.
"""
)
async def list_articles(
    filter: Optional[str] = Query(None, description="Filter articles by title (case-insensitive)")
) -> ArticleListResponse:
    """List all articles, optionally filtered by title."""
    from db import Database
    
    db = Database()
    
    with db.conn.cursor() as cur:
        if filter:
            cur.execute("""
                SELECT title, file_path 
                FROM brain.notes 
                WHERE title ILIKE %s 
                ORDER BY title ASC
            """, (f"%{filter}%",))
        else:
            cur.execute("""
                SELECT title, file_path 
                FROM brain.notes 
                ORDER BY title ASC
            """)
        
        rows = cur.fetchall()
        articles = [ArticleListItem(title=row[0], file_path=row[1]) for row in rows]
        
        return ArticleListResponse(
            filter=filter,
            articles=articles,
            total=len(articles)
        )


@router.get(
    "/related/{title_or_path:path}",
    response_model=RelatedArticlesResponse,
    summary="Get Related Articles",
    description="""
Find articles related to a specific document via wikilinks.

Returns both outgoing links (documents this article references) and 
incoming links (documents that reference this article).
"""
)
async def get_related_articles(title_or_path: str) -> RelatedArticlesResponse:
    """Get related articles via wikilinks."""
    from db import Database
    
    db = Database()
    
    with db.conn.cursor() as cur:
        # Find the source article
        cur.execute("""
            SELECT id, title FROM brain.notes 
            WHERE title ILIKE %s OR file_path ILIKE %s
            LIMIT 1
        """, (f"%{title_or_path}%", f"%{title_or_path}%"))
        
        row = cur.fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Article '{title_or_path}' not found")
        
        note_id, title = row
        
        # Get outgoing links
        cur.execute(
            "SELECT target_title FROM brain.links WHERE source_note_id = %s", 
            (note_id,)
        )
        outgoing = [r[0] for r in cur.fetchall()]
        
        # Get incoming links
        cur.execute("""
            SELECT n.title 
            FROM brain.links l 
            JOIN brain.notes n ON l.source_note_id = n.id 
            WHERE l.target_title ILIKE %s
        """, (title,))
        incoming = [r[0] for r in cur.fetchall()]
        
        return RelatedArticlesResponse(
            source_title=title,
            outgoing_links=outgoing,
            incoming_links=incoming
        )


# ==================== OpenAPI Customization ====================

def get_tools_openapi_schema(server_url: str = None):
    """Generate a standalone OpenAPI schema for just the tools endpoints."""
    from fastapi.openapi.utils import get_openapi
    from fastapi import FastAPI
    
    # Create a minimal app with just the tools router
    tools_app = FastAPI(
        title="Brain Knowledge Base Tools",
        description="""
Knowledge Base tools for AI assistants.

These tools allow AI models to search and retrieve information from a local 
knowledge base of markdown documents.

**Available Tools:**
- **search**: Find relevant documents using semantic/hybrid search
- **get_article**: Retrieve full article content
- **list_articles**: Browse available articles
- **get_related**: Find related documents via wikilinks
""",
        version="1.0.0"
    )
    tools_app.include_router(router)
    
    schema = get_openapi(
        title=tools_app.title,
        version=tools_app.version,
        description=tools_app.description,
        routes=tools_app.routes
    )
    
    # Add servers if URL provided
    if server_url:
        schema["servers"] = [{"url": server_url}]
    
    return schema


@router.get(
    "/openapi.json",
    summary="Tools OpenAPI Spec",
    description="Get OpenAPI specification for just the knowledge base tools.",
    include_in_schema=False  # Don't include this endpoint in the spec itself
)
async def tools_openapi():
    """Return OpenAPI spec for just the tools endpoints."""
    import os
    external_url = os.environ.get("EXTERNAL_URL", "")
    return get_tools_openapi_schema(server_url=external_url if external_url else None)
