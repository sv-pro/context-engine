"""
ColBERTv2-Compatible Search API.

Exposes the knowledge base as a ColBERTv2-compatible endpoint for DSPy integration.
DSPy's `dspy.ColBERTv2(url, port)` expects: GET /api/search?query=...&k=N

Response format: [{pid, long_text, score, rank}, ...]
"""

import logging
from typing import List
from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger("colbert-api")

router = APIRouter(tags=["ColBERTv2 Retrieval"])


# Response model for ColBERTv2 compatibility
class ColBERTResult(BaseModel):
    pid: int
    long_text: str
    score: float
    rank: int


@router.get("/api/search", response_model=List[ColBERTResult])
async def colbert_search(
    query: str = Query(..., description="Search query"),
    k: int = Query(10, ge=1, le=100, description="Number of results to return")
) -> List[ColBERTResult]:
    """
    ColBERTv2-compatible search endpoint.
    
    Returns ranked passages from the knowledge base matching the query.
    Compatible with DSPy's `dspy.ColBERTv2(url, port)` retriever.
    
    Example: GET /api/search?query=SSL+certificate+renewal&k=5
    """
    from db import Database
    from main import get_embedding
    
    db = Database()
    
    # Get query embedding
    query_vector = get_embedding(query)
    if not query_vector:
        logger.error(f"Failed to get embedding for query: {query}")
        return []
    
    # Perform semantic search on chunks
    try:
        results = db.semantic_search(query_vector, limit=k)
        
        colbert_results = []
        for i, r in enumerate(results):
            colbert_results.append(ColBERTResult(
                pid=r.get("chunk_id", r.get("id", i)),
                long_text=r.get("content", ""),
                score=r.get("similarity", 0.0),
                rank=i + 1
            ))
        
        logger.info(f"ColBERT search: query='{query[:50]}...' k={k} results={len(colbert_results)}")
        return colbert_results
        
    except Exception as e:
        logger.error(f"ColBERT search failed: {e}")
        return []


@router.get("/api/search/facts", response_model=List[ColBERTResult])
async def colbert_search_facts(
    query: str = Query(..., description="Subject or predicate to search for"),
    k: int = Query(10, ge=1, le=100, description="Number of results to return")
) -> List[ColBERTResult]:
    """
    Search extracted facts as ColBERTv2-compatible results.
    
    Searches the facts table and returns formatted triples.
    """
    from db import Database
    
    db = Database()
    
    try:
        # Search facts by subject or predicate
        facts = db.get_facts(subject=query, limit=k)
        if not facts:
            facts = db.get_facts(predicate=query, limit=k)
        
        results = []
        for i, fact in enumerate(facts):
            # Format fact as natural language
            text = f"{fact['subject']} {fact['predicate']} {fact['object']}"
            results.append(ColBERTResult(
                pid=fact.get("id", i),
                long_text=text,
                score=fact.get("confidence", 0.8),
                rank=i + 1
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Facts search failed: {e}")
        return []
