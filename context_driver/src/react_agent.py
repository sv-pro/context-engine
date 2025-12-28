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
        
        # DSPy ReAct stores trajectory as a dict with thought_N, tool_name_N, observation_N keys
        if hasattr(result, 'trajectory') and isinstance(result.trajectory, dict):
            traj_dict = result.trajectory
            
            # Find all steps by looking for thought_N keys
            step_nums = set()
            for key in traj_dict.keys():
                if key.startswith('thought_'):
                    try:
                        step_num = int(key.split('_')[1])
                        step_nums.add(step_num)
                    except (ValueError, IndexError):
                        pass
            
            # Extract each step
            for i in sorted(step_nums):
                thought = traj_dict.get(f'thought_{i}', '')
                tool_name = traj_dict.get(f'tool_name_{i}', '')
                tool_args = traj_dict.get(f'tool_args_{i}', {})
                observation = traj_dict.get(f'observation_{i}', '')
                
                # Format action as "tool_name(args)" if present
                if tool_name and tool_name != 'finish':
                    action = f"{tool_name}({tool_args})" if tool_args else tool_name
                else:
                    action = tool_name or ''
                
                trajectory.append({
                    "thought": thought,
                    "action": action,
                    "observation": observation
                })
        
        # Also include final reasoning if present
        elif hasattr(result, 'reasoning') and result.reasoning:
            trajectory.append({
                "thought": result.reasoning,
                "action": "final_answer",
                "observation": getattr(result, 'answer', '')
            })
        
        return trajectory



# === Configuration ===

import threading
import os

_agent_lock = threading.Lock()
_agent_instance: Optional[KnowledgeBaseReActAgent] = None
_dspy_configured = False


def _ensure_dspy_configured():
    """Ensure DSPy is configured (thread-safe, only once)."""
    global _dspy_configured
    
    if _dspy_configured:
        return
    
    # Determine model based on available API keys
    if os.environ.get("OPENAI_API_KEY"):
        model = "openai/gpt-4o-mini"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        model = "anthropic/claude-3-haiku-20240307"
    else:
        model = "ollama/llama3"  # Fallback to local
    
    try:
        lm = dspy.LM(model=model)
        dspy.configure(lm=lm)
        _dspy_configured = True
        logger.info(f"DSPy configured with model: {model}")
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        raise


def configure_react_agent(model: str = None):
    """
    Configure DSPy and create the ReAct agent.
    
    Args:
        model: LiteLLM-compatible model name (optional, auto-detected if not provided)
    """
    global _dspy_configured
    
    if model:
        try:
            lm = dspy.LM(model=model)
            dspy.configure(lm=lm)
            _dspy_configured = True
            logger.info(f"ReAct agent configured with model: {model}")
        except Exception as e:
            logger.error(f"Failed to configure DSPy with {model}: {e}")
            raise
    else:
        _ensure_dspy_configured()


def get_react_agent(max_iters: int = 5) -> KnowledgeBaseReActAgent:
    """
    Get or create the ReAct agent singleton (thread-safe).
    
    Args:
        max_iters: Maximum reasoning iterations
        
    Returns:
        Configured KnowledgeBaseReActAgent
    """
    global _agent_instance
    
    _ensure_dspy_configured()
    
    with _agent_lock:
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
