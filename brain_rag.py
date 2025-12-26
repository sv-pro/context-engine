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
    def __init__(self):
        pass

    def search_knowledge_base(self, query: str, limit: int = 5, strategy: str = "super_hybrid") -> str:
        """
        Search the knowledge base using hybrid RAG retrieval.
        
        :param query: Natural language search query
        :param limit: Maximum number of results (default 5)
        :param strategy: Search strategy - semantic, keyword, hybrid, super_hybrid, graph
        :return: Search results with titles and content snippets
        """
        try:
            response = requests.post(
                f"{BASE_URL}/tools/search",
                json={"query": query, "limit": limit, "strategy": strategy},
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

    def list_articles(self, filter: Optional[str] = None) -> str:
        """
        List all articles in the knowledge base.
        
        :param filter: Optional title filter (partial match)
        :return: List of article titles
        """
        try:
            params = {}
            if filter:
                params["filter"] = filter
            
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
