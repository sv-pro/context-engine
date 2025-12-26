"""
title: Brain Knowledge Base
author: context-engine
version: 0.1.0
"""

import requests
from typing import Optional

BASE_URL = "http://context-driver:8000"


class Tools:
    def __init__(self):
        pass

    def search_knowledge_base(self, query: str, limit: int = 5) -> str:
        """
        Search the knowledge base for relevant documents.
        
        :param query: Natural language search query
        :param limit: Maximum number of results (default 5)
        :return: Search results with titles and content snippets
        """
        try:
            response = requests.post(
                f"{BASE_URL}/tools/search",
                json={"query": query, "limit": limit, "strategy": "super_hybrid"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for r in data.get("results", []):
                results.append(f"**{r['title']}** (score: {r['similarity']:.2f})\n{r['content'][:500]}")
            
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
        except Exception as e:
            return f"Error getting article: {str(e)}"

    def list_facts(self, subject: Optional[str] = None, limit: int = 20) -> str:
        """
        List extracted facts from the knowledge base.
        
        :param subject: Optional subject filter
        :param limit: Maximum number of facts (default 20)
        :return: List of subject-predicate-object facts
        """
        try:
            params = {"limit": limit}
            if subject:
                params["subject"] = subject
            
            response = requests.get(
                f"{BASE_URL}/tools/facts",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            facts = []
            for f in data.get("facts", []):
                facts.append(f"- {f['subject']} → {f['predicate']} → {f['object']}")
            
            if not facts:
                return "No facts found."
            
            return "\n".join(facts)
        except Exception as e:
            return f"Error listing facts: {str(e)}"

    def list_rules(self, severity: Optional[str] = None, limit: int = 20) -> str:
        """
        List extracted IF-THEN rules from the knowledge base.
        
        :param severity: Optional filter: critical, high, normal, low
        :param limit: Maximum number of rules (default 20)
        :return: List of condition-action rules
        """
        try:
            params = {"limit": limit}
            if severity:
                params["severity"] = severity
            
            response = requests.get(
                f"{BASE_URL}/tools/rules",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            rules = []
            for r in data.get("rules", []):
                rules.append(f"- IF {r['condition']} THEN {r['action']} [{r['severity']}]")
            
            if not rules:
                return "No rules found."
            
            return "\n".join(rules)
        except Exception as e:
            return f"Error listing rules: {str(e)}"
