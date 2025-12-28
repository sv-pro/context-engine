"""
title: Brain RAG
author: context-engine
version: 0.1.0
description: Knowledge base search using hybrid RAG (semantic + keyword + graph)
"""

import requests
from typing import Optional

BASE_URL = "http://context-driver:8000"


class Tools:
    def __init__(self, sub_path: Optional[str] = None):
        """
        Initialize Tools with optional sub-brain scoping.
        
        Args:
            sub_path: Optional path prefix to scope all operations to a sub-brain.
                     Example: "projects/myapp" or "modes/debug"
        """
        self.sub_path = sub_path

    def scoped(self, sub_path: str) -> "Tools":
        """
        Create a new Tools instance scoped to a specific sub-brain.
        
        Args:
            sub_path: Path prefix relative to brain root (e.g., "projects/myapp")
        
        Returns:
            A new Tools instance that will only search within the specified path.
        """
        return Tools(sub_path=sub_path)

    def search_knowledge_base(self, query: str, limit: int = 5, strategy: str = "super_hybrid", sub_path: Optional[str] = None) -> str:
        """
        Search the knowledge base using hybrid RAG retrieval.
        
        :param query: Natural language search query
        :param limit: Maximum number of results (default 5)
        :param strategy: Search strategy - semantic, keyword, hybrid, super_hybrid, graph
        :param sub_path: Optional override for sub-brain path (uses instance sub_path if not specified)
        :return: Search results with titles and content snippets
        """
        # Use provided sub_path or fall back to instance default
        effective_sub_path = sub_path or self.sub_path
        
        try:
            payload = {
                "query": query, 
                "limit": limit, 
                "strategy": strategy
            }
            if effective_sub_path:
                payload["sub_path"] = effective_sub_path
            
            response = requests.post(
                f"{BASE_URL}/tools/search",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for r in data.get("results", []):
                results.append(f"**[{r['rank']}] {r['title']}** (score: {r['similarity']:.2f})\n{r['content'][:500]}")
            
            if not results:
                return "No results found."
            
            return "\n\n---\n\n".join(results)
        except Exception as e:
            return f"Error searching knowledge base: {str(e)}"

    def get_article(self, title: str) -> str:
        """
        Get the full content of an article by title.
        
        :param title: Article title or partial title to search for
        :return: Full article content in markdown
        """
        try:
            response = requests.get(
                f"{BASE_URL}/tools/article/{title}",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return f"# {data['title']}\n\n{data['content']}"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"Article '{title}' not found."
            return f"Error getting article: {str(e)}"
        except Exception as e:
            return f"Error getting article: {str(e)}"

    def list_articles(self, filter: Optional[str] = None, sub_path: Optional[str] = None) -> str:
        """
        List all articles in the knowledge base.
        
        :param filter: Optional title filter (partial match)
        :param sub_path: Optional sub-brain path to scope listing
        :return: List of article titles
        """
        # Use provided sub_path or fall back to instance default
        effective_sub_path = sub_path or self.sub_path
        
        try:
            params = {}
            if filter:
                params["filter"] = filter
            if effective_sub_path:
                params["sub_path"] = effective_sub_path
            
            response = requests.get(
                f"{BASE_URL}/tools/articles",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            articles = [f"- {a['title']}" for a in data.get("articles", [])]
            
            if not articles:
                return "No articles found."
            
            return f"**{data['total']} articles:**\n" + "\n".join(articles[:50])
        except Exception as e:
            return f"Error listing articles: {str(e)}"

    def get_related_articles(self, title: str) -> str:
        """
        Get articles related to a specific document via wikilinks.
        
        :param title: Article title to find relations for
        :return: Outgoing and incoming links
        """
        try:
            response = requests.get(
                f"{BASE_URL}/tools/related/{title}",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            result = f"**Related to: {data['source_title']}**\n\n"
            
            if data.get("outgoing_links"):
                result += "**Links to:**\n" + "\n".join([f"- {l}" for l in data["outgoing_links"]]) + "\n\n"
            
            if data.get("incoming_links"):
                result += "**Linked from:**\n" + "\n".join([f"- {l}" for l in data["incoming_links"]])
            
            if not data.get("outgoing_links") and not data.get("incoming_links"):
                result += "No related articles found."
            
            return result
        except Exception as e:
            return f"Error getting related articles: {str(e)}"
