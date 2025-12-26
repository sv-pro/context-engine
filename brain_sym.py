"""
title: Brain Symbolic
author: context-engine
version: 0.1.0
description: Neurosymbolic knowledge - extracted facts, rules, and document capsules
"""

import requests
from typing import Optional

BASE_URL = "http://context-driver:8000"


class Tools:
    def __init__(self):
        pass

    def list_facts(self, subject: Optional[str] = None, predicate: Optional[str] = None, limit: int = 20) -> str:
        """
        List extracted facts (subject-predicate-object triples) from documents.
        
        :param subject: Optional subject filter (partial match)
        :param predicate: Optional predicate filter (partial match)
        :param limit: Maximum number of facts (default 20)
        :return: List of structured facts
        """
        try:
            params = {"limit": limit}
            if subject:
                params["subject"] = subject
            if predicate:
                params["predicate"] = predicate
            
            response = requests.get(
                f"{BASE_URL}/tools/facts",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            facts = []
            for f in data.get("facts", []):
                facts.append(f"• **{f['subject']}** → {f['predicate']} → **{f['object']}**\n  _(from: {f['source_title']}, confidence: {f['confidence']:.2f})_")
            
            if not facts:
                return "No facts found matching your query."
            
            return f"**{data['total']} facts found:**\n\n" + "\n\n".join(facts)
        except Exception as e:
            return f"Error listing facts: {str(e)}"

    def list_rules(self, severity: Optional[str] = None, limit: int = 20) -> str:
        """
        List extracted IF-THEN rules from procedural documents.
        
        :param severity: Optional filter: critical, high, normal, low
        :param limit: Maximum number of rules (default 20)
        :return: List of executable rules
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
                sev_emoji = {"critical": "🔴", "high": "🟠", "normal": "🟢", "low": "⚪"}.get(r['severity'], "⚪")
                rules.append(f"{sev_emoji} **IF** {r['condition']}\n   **THEN** {r['action']}\n   _(from: {r['source_title']})_")
            
            if not rules:
                return "No rules found matching your query."
            
            return f"**{data['total']} rules found:**\n\n" + "\n\n".join(rules)
        except Exception as e:
            return f"Error listing rules: {str(e)}"

    def list_capsules(self, domain: Optional[str] = None, intent: Optional[str] = None, limit: int = 20) -> str:
        """
        List document capsules (condensed summaries with metadata).
        
        :param domain: Optional domain filter: ssl, networking, auth, database, infrastructure, security
        :param intent: Optional intent filter: procedure, fact, policy, incident, reference
        :param limit: Maximum number of capsules (default 20)
        :return: List of document summaries
        """
        try:
            params = {"limit": limit}
            if domain:
                params["domain"] = domain
            if intent:
                params["intent"] = intent
            
            response = requests.get(
                f"{BASE_URL}/tools/capsules",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            capsules = []
            for c in data.get("capsules", []):
                intent_emoji = {
                    "procedure": "📋", "fact": "📄", "policy": "📜", 
                    "incident": "🚨", "reference": "📚"
                }.get(c['intent'], "📝")
                
                key_points = "\n".join([f"  • {kp}" for kp in c.get('key_points', [])[:3]])
                capsules.append(
                    f"{intent_emoji} **{c['source_title']}** [{c['domain']}]\n"
                    f"  _{c['summary']}_\n"
                    f"{key_points}"
                )
            
            if not capsules:
                return "No capsules found matching your query."
            
            return f"**{data['total']} document capsules:**\n\n" + "\n\n".join(capsules)
        except Exception as e:
            return f"Error listing capsules: {str(e)}"

    def get_capsule(self, note_id: int) -> str:
        """
        Get detailed capsule for a specific document.
        
        :param note_id: The note ID to get capsule for
        :return: Full capsule with summary, key points, intent, and domain
        """
        try:
            response = requests.get(
                f"{BASE_URL}/tools/capsule/{note_id}",
                timeout=30
            )
            response.raise_for_status()
            c = response.json()
            
            key_points = "\n".join([f"• {kp}" for kp in c.get('key_points', [])])
            
            return (
                f"# {c['source_title']}\n\n"
                f"**Intent:** {c['intent']} | **Domain:** {c['domain']} | **Confidence:** {c['confidence']:.2f}\n\n"
                f"## Summary\n{c['summary']}\n\n"
                f"## Key Points\n{key_points}"
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"Capsule for note {note_id} not found."
            return f"Error getting capsule: {str(e)}"
        except Exception as e:
            return f"Error getting capsule: {str(e)}"
