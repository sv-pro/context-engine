"""
DSPy ReAct Agent for Knowledge Base Q&A.

Implements a ReAct (Reasoning + Acting) agent that iteratively reasons
and uses knowledge base tools to answer complex questions.
"""

import dspy
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("react-agent")


# === Signatures ===

class AnswerQuestion(dspy.Signature):
    """Answer a question comprehensively using the knowledge base tools.
    
    Use the available tools to search for relevant information, extract facts,
    and find applicable rules. Reason step-by-step before providing the final answer.
    """
    
    question: str = dspy.InputField(desc="The question to answer")
    answer: str = dspy.OutputField(desc="Comprehensive answer based on retrieved knowledge")


class AnswerWithContext(dspy.Signature):
    """Answer a question using provided context from the knowledge base."""
    
    question: str = dspy.InputField(desc="The question to answer")
    context: str = dspy.InputField(desc="Relevant context from knowledge base")
    answer: str = dspy.OutputField(desc="Answer based on the provided context")


# === ReAct Agent ===

class KnowledgeBaseReActAgent(dspy.Module):
    """
    ReAct agent that uses knowledge base tools to answer questions.
    
    The agent iteratively:
    1. Reasons about what information is needed
    2. Calls appropriate tools to gather information
    3. Observes the results
    4. Decides whether to continue or provide final answer
    """
    
    def __init__(self, max_iters: int = 5):
        super().__init__()
        
        # Import tools
        from dspy_tools import KNOWLEDGE_BASE_TOOLS
        
        self.react = dspy.ReAct(
            signature=AnswerQuestion,
            tools=KNOWLEDGE_BASE_TOOLS,
            max_iters=max_iters
        )
        
        # Fallback if ReAct doesn't find enough info
        self.fallback = dspy.Predict(AnswerWithContext)
    
    def forward(self, question: str) -> Dict[str, Any]:
        """
        Answer a question using ReAct reasoning.
        
        Args:
            question: The question to answer
            
        Returns:
            Dict with 'answer' and 'trajectory' (reasoning trace)
        """
        try:
            result = self.react(question=question)
            
            return {
                "answer": result.answer,
                "trajectory": self._extract_trajectory(result),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"ReAct failed: {e}")
            
            # Fallback: do a simple search and generate answer
            try:
                from dspy_tools import search_knowledge_base
                context = search_knowledge_base(question, limit=5)
                
                fallback_result = self.fallback(
                    question=question,
                    context=context
                )
                
                return {
                    "answer": fallback_result.answer,
                    "trajectory": [{"type": "fallback", "observation": context}],
                    "success": True,
                    "fallback": True
                }
            except Exception as fallback_e:
                logger.error(f"Fallback also failed: {fallback_e}")
                return {
                    "answer": f"I was unable to answer the question due to an error: {e}",
                    "trajectory": [],
                    "success": False,
                    "error": str(e)
                }
    
    def _extract_trajectory(self, result) -> List[Dict[str, Any]]:
        """Extract the reasoning trajectory from a ReAct result."""
        trajectory = []
        
        # DSPy ReAct stores trajectory in result.trajectory or similar
        if hasattr(result, 'trajectory'):
            for step in result.trajectory:
                trajectory.append({
                    "thought": getattr(step, 'thought', ''),
                    "action": getattr(step, 'action', ''),
                    "observation": getattr(step, 'observation', '')
                })
        elif hasattr(result, 'reasoning'):
            trajectory.append({
                "thought": result.reasoning,
                "action": "final_answer",
                "observation": result.answer
            })
        
        return trajectory


# === Configuration ===

_agent_configured = False
_agent_instance: Optional[KnowledgeBaseReActAgent] = None


def configure_react_agent(model: str = "openai/gpt-4o-mini"):
    """
    Configure DSPy and create the ReAct agent.
    
    Args:
        model: LiteLLM-compatible model name
    """
    global _agent_configured
    
    from dspy_signatures import configure_dspy
    configure_dspy(model)
    _agent_configured = True
    logger.info(f"ReAct agent configured with model: {model}")


def get_react_agent(max_iters: int = 5) -> KnowledgeBaseReActAgent:
    """
    Get or create the ReAct agent singleton.
    
    Args:
        max_iters: Maximum reasoning iterations
        
    Returns:
        Configured KnowledgeBaseReActAgent
    """
    global _agent_instance, _agent_configured
    
    if not _agent_configured:
        configure_react_agent()
    
    if _agent_instance is None:
        _agent_instance = KnowledgeBaseReActAgent(max_iters=max_iters)
        logger.info(f"Created ReAct agent with max_iters={max_iters}")
    
    return _agent_instance


def ask_question(question: str, max_iters: int = 5) -> Dict[str, Any]:
    """
    Convenience function to ask a question using the ReAct agent.
    
    Args:
        question: The question to answer
        max_iters: Maximum reasoning iterations
        
    Returns:
        Dict with 'answer', 'trajectory', and 'success' keys
    """
    agent = get_react_agent(max_iters=max_iters)
    return agent(question=question)


# === Simple RAG Alternative ===

class SimpleRAGAgent(dspy.Module):
    """
    Simple RAG agent for comparison/fallback.
    
    This agent does a single retrieval step followed by generation,
    without iterative reasoning.
    """
    
    def __init__(self):
        super().__init__()
        self.generate = dspy.Predict(AnswerWithContext)
    
    def forward(self, question: str) -> Dict[str, Any]:
        """Answer using simple retrieve-then-generate."""
        from dspy_tools import search_knowledge_base
        
        context = search_knowledge_base(question, limit=5)
        result = self.generate(question=question, context=context)
        
        return {
            "answer": result.answer,
            "context": context,
            "success": True
        }
