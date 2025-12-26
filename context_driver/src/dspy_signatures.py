"""
DSPy Signatures and Modules for Neurosymbolic Ingestion Pipeline.

This module provides type-safe, optimizable LLM calls using DSPy signatures.
"""

import dspy
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# === SIGNATURES ===

class CondenseDocument(dspy.Signature):
    """Extract the core meaning from a document into a condensed capsule."""
    
    title: str = dspy.InputField(desc="Document title")
    content: str = dspy.InputField(desc="Document content (may be truncated)")
    
    summary: str = dspy.OutputField(desc="2-3 sentence summary of essential information")
    key_points: List[str] = dspy.OutputField(desc="3-7 most important facts as bullet points")
    intent: str = dspy.OutputField(desc="One of: procedure, fact, policy, incident, reference, unknown")
    domain: str = dspy.OutputField(desc="Primary domain: ssl, networking, auth, database, infrastructure, security, or other")
    confidence: float = dspy.OutputField(desc="Confidence in extraction from 0.0 to 1.0")


class ExtractFacts(dspy.Signature):
    """Extract subject-predicate-object facts from a document."""
    
    title: str = dspy.InputField(desc="Document title")
    content: str = dspy.InputField(desc="Document content")
    summary: str = dspy.InputField(desc="Summary from condensation pass")
    
    facts: List[Dict[str, str]] = dspy.OutputField(
        desc="List of facts as {subject: str, predicate: str, object: str}"
    )


class DistillRules(dspy.Signature):
    """Extract IF-THEN rules from procedural or policy documents."""
    
    title: str = dspy.InputField(desc="Document title")
    content: str = dspy.InputField(desc="Document content")
    intent: str = dspy.InputField(desc="Document intent: procedure, policy, or incident")
    facts: List[Dict[str, str]] = dspy.InputField(desc="Previously extracted facts")
    
    rules: List[Dict[str, str]] = dspy.OutputField(
        desc="List of rules as {rule_id: str, condition: str, action: str, severity: str}"
    )


# === MODULES ===

class NeuroIngestionPipeline(dspy.Module):
    """
    3-pass neurosymbolic knowledge distillation pipeline.
    
    Pass #1: CONDENSE - Extract summary, key points, intent, domain
    Pass #2: STRUCTURE - Extract subject-predicate-object facts
    Pass #3: DISTILL RULES - Extract IF-THEN logic (for procedures/policies only)
    """
    
    def __init__(self):
        super().__init__()
        self.condense = dspy.Predict(CondenseDocument)
        self.extract_facts = dspy.Predict(ExtractFacts)
        self.distill_rules = dspy.Predict(DistillRules)
    
    def forward(self, title: str, content: str) -> Dict[str, Any]:
        """
        Execute the 3-pass pipeline.
        
        Args:
            title: Document title
            content: Document content (will be truncated if too long)
            
        Returns:
            Dict with capsule, facts, and rules
        """
        # Truncate content to avoid token limits
        max_content = 4000
        truncated_content = content[:max_content] if len(content) > max_content else content
        
        # Pass #1: CONDENSE
        try:
            capsule = self.condense(title=title, content=truncated_content)
            logger.info(f"[DSPy] Condensed '{title}' -> intent={capsule.intent}, domain={capsule.domain}")
        except Exception as e:
            logger.error(f"[DSPy] Condense failed for '{title}': {e}")
            capsule = type('obj', (object,), {
                'summary': '',
                'key_points': [],
                'intent': 'unknown',
                'domain': 'unknown',
                'confidence': 0.0
            })()
        
        # Pass #2: STRUCTURE
        try:
            facts_result = self.extract_facts(
                title=title,
                content=truncated_content,
                summary=capsule.summary
            )
            facts = facts_result.facts if hasattr(facts_result, 'facts') else []
            logger.info(f"[DSPy] Extracted {len(facts)} facts from '{title}'")
        except Exception as e:
            logger.error(f"[DSPy] Extract facts failed for '{title}': {e}")
            facts = []
        
        # Pass #3: DISTILL RULES (only for procedures/policies)
        rules = []
        if capsule.intent in ["procedure", "policy", "incident"]:
            try:
                rules_result = self.distill_rules(
                    title=title,
                    content=truncated_content,
                    intent=capsule.intent,
                    facts=facts
                )
                rules = rules_result.rules if hasattr(rules_result, 'rules') else []
                logger.info(f"[DSPy] Distilled {len(rules)} rules from '{title}'")
            except Exception as e:
                logger.error(f"[DSPy] Distill rules failed for '{title}': {e}")
        
        return {
            "capsule": {
                "summary": capsule.summary,
                "key_points": capsule.key_points if hasattr(capsule, 'key_points') else [],
                "intent": capsule.intent,
                "domain": capsule.domain,
                "confidence": float(capsule.confidence) if hasattr(capsule, 'confidence') else 0.0
            },
            "facts": facts,
            "rules": rules
        }


# === CONFIGURATION ===

_dspy_configured = False

def configure_dspy(model: str = "openai/gpt-4o-mini"):
    """
    Configure DSPy to use LiteLLM-compatible models.
    
    Args:
        model: Model name in LiteLLM format (e.g., "openai/gpt-4o-mini")
    """
    global _dspy_configured
    import os
    
    # DSPy supports LiteLLM natively
    lm = dspy.LM(model=model)
    dspy.configure(lm=lm)
    _dspy_configured = True
    logger.info(f"[DSPy] Configured with model: {model}")


# === HELPER FUNCTION ===

def run_dspy_pipeline(title: str, content: str) -> Dict[str, Any]:
    """
    Convenience function to run the full pipeline.
    Ensures DSPy is configured before execution.
    """
    global _dspy_configured
    
    # Configure on first call
    if not _dspy_configured:
        configure_dspy()
    
    pipeline = NeuroIngestionPipeline()
    return pipeline(title=title, content=content)
