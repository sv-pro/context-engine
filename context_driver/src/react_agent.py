"""
DSPy ReAct Agent for Knowledge Base Q&A.

Implements a ReAct (Reasoning + Acting) agent that iteratively reasons
and uses knowledge base tools to answer complex questions.
"""

import dspy
import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger("react-agent")


# === Signatures ===

class AnswerQuestion(dspy.Signature):
    """Answer a question comprehensively using the knowledge base tools.
    
    Use the available tools to search for relevant information, extract facts,
    and find applicable rules. Reason step-by-step before providing the final answer.
    
    IMPORTANT: When you find a relevant document, always check its relationships using
    get_related_documents() to discover specific procedures, emergency guides, or policies
    that might not surface in direct search results.
    """
    
    question: str = dspy.InputField(desc="The question to answer")
    answer: str = dspy.OutputField(desc="Comprehensive answer based on retrieved knowledge")


class AnswerWithContext(dspy.Signature):
    """Answer a question using provided context from the knowledge base."""
    
    question: str = dspy.InputField(desc="The question to answer")
    context: str = dspy.InputField(desc="Relevant context from knowledge base")
    answer: str = dspy.OutputField(desc="Answer based on the provided context")


class VerifyAnswer(dspy.Signature):
    """Verify and potentially correct a draft answer using the knowledge base"""
    
    question: str = dspy.InputField(desc="Original question")
    draft_answer: str = dspy.InputField(desc="Draft answer from ReAct agent")
    knowledge_context: str = dspy.InputField(desc="Relevant facts and rules for verification")
    
    verified_answer: str = dspy.OutputField(desc="Verified/corrected answer")
    verification_status: str = dspy.OutputField(desc="Verification status: 'Correct', 'Partial', or 'Incorrect'")

class EstimateConfidence(dspy.Signature):
    """Estimate confidence in the current answer based on information gathered"""
    
    question: str = dspy.InputField(desc="Original question being investigated")
    gathered_info: str = dspy.InputField(desc="Summary of information gathered so far from all observations")
    current_answer: str = dspy.InputField(desc="Current draft answer based on gathered information")
    
    confidence_score: float = dspy.OutputField(desc="Confidence score between 0.0 and 1.0, where 1.0 means complete certainty")
    missing_aspects: str = dspy.OutputField(desc="Key aspects or information still missing from the answer, if any")
    recommendation: str = dspy.OutputField(desc="Recommendation: 'finish' if confident, or specific next steps to improve confidence")


# === ReAct Agent ===

class KnowledgeBaseVerifier(dspy.Module):
    """Module to verify answers against the knowledge graph."""
    
    def __init__(self):
        super().__init__()
        self.verify = dspy.ChainOfThought(VerifyAnswer)
        
    def forward(self, question: str, draft_answer: str):
        # 1. Extract potential entities from answer (simple heuristic or LLM)
        # For simplicity, we'll verify against a broad fact search for now.
        # In a production system, we'd extract specific entities first.
        from dspy_tools import get_facts, get_rules
        
        # Heuristic: search facts for capitalized words (Entities) in draft
        # This is a basic implementation.
        import re
        entities = set(re.findall(r'\b[A-Z][a-zA-Z0-9_]*\b', draft_answer))
        
        facts = []
        for entity in list(entities)[:5]: # Limit lookup
            f = get_facts(subject=entity, limit=2)
            if f: facts.extend([str(x) for x in f])
            
        # Also grab general rules
        rules = get_rules(limit=5)
        
        context = "\n".join(facts) + "\n" + "\n".join([str(r) for r in rules])
        
        return self.verify(
            question=question,
            draft_answer=draft_answer,
            knowledge_context=context
        )


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
        
        self.verifier = KnowledgeBaseVerifier()
        
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
            
            logger.info("Verifying draft answer...")
            
            # extract answer safely
            draft_answer = getattr(result, 'answer', None)
            if not draft_answer:
                 logger.warning("ReAct did not produce a final answer.")
                 draft_answer = "No answer produced."
            
            # Estimate confidence in the answer
            try:
                conf_predictor = dspy.Predict(EstimateConfidence)
                conf_result = conf_predictor(
                    question=question,
                    gathered_info=self._extract_trajectory(result),
                    current_answer=draft_answer
                )
                
                try:
                    confidence = float(conf_result.confidence_score)
                    # Clamp to valid range
                    confidence = max(0.0, min(1.0, confidence))
                except (ValueError, TypeError):
                    confidence = 0.5  # Default if parsing fails
                
                logger.info(f"📊 Answer Confidence: {confidence:.2f}")
                logger.info(f"📋 Missing Aspects: {conf_result.missing_aspects}")
                logger.info(f"💡 Recommendation: {conf_result.recommendation}")
                
                # Warn if confidence is low
                if confidence < 0.8:
                    logger.warning(f"⚠️  Low confidence ({confidence:.2f}) - answer may be incomplete!")
                    
            except Exception as e:
                logger.warning(f"Confidence estimation failed: {e}")
                confidence = None

            verification = self.verifier(question=question, draft_answer=draft_answer)
            
            final_answer = getattr(verification, "verified_answer", None) or draft_answer
            verification_status = getattr(verification, "verification_status", None)
            verification_note = f"\n\n(Verified: {verification_status})" if verification_status else ""
            if verification_status:
                logger.info(f"Verification status: {verification_status}")
            
            return {
                "answer": final_answer + verification_note,
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

        def _coerce_text(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            try:
                return json.dumps(value, ensure_ascii=True)
            except TypeError:
                return str(value)

        def _normalize_action(action: Any, tool_args: Any) -> str:
            action_text = _coerce_text(action)
            if not action_text.strip():
                return ""
            if tool_args in (None, "", {}, []):
                return action_text
            args_text = _coerce_text(tool_args)
            return f"{action_text}({args_text})"

        def _build_step(thought: Any, action: Any, tool_args: Any, observation: Any) -> Optional[Dict[str, Any]]:
            thought_text = _coerce_text(thought).strip()
            action_text = _normalize_action(action, tool_args).strip()
            observation_text = _coerce_text(observation).strip()
            if not (thought_text or action_text or observation_text):
                return None
            return {
                "thought": thought_text,
                "action": action_text,
                "observation": observation_text
            }

        def _pluck(source: Any, *keys: str) -> Any:
            for key in keys:
                if isinstance(source, dict) and key in source:
                    return source.get(key)
                if hasattr(source, key):
                    return getattr(source, key)
            return None

        def _parse_step(step: Any) -> Optional[Dict[str, Any]]:
            if step is None:
                return None
            if isinstance(step, dict):
                thought = _pluck(step, "thought", "reasoning", "rationale", "analysis")
                action = _pluck(step, "action", "tool", "tool_name", "toolname")
                tool_args = _pluck(step, "tool_args", "action_input", "args", "input", "tool_input")
                observation = _pluck(step, "observation", "result", "output", "response")

                if isinstance(action, dict):
                    tool_name = _pluck(action, "tool", "tool_name", "name")
                    tool_args = tool_args or _pluck(action, "args", "input")
                    action = tool_name or action

                return _build_step(thought, action, tool_args, observation)

            if isinstance(step, (list, tuple)) and len(step) >= 3:
                thought, action, observation = step[0], step[1], step[2]
                tool_args = step[3] if len(step) > 3 else None
                return _build_step(thought, action, tool_args, observation)

            if hasattr(step, "__dict__"):
                return _parse_step(step.__dict__)

            step_text = _coerce_text(step).strip()
            if step_text:
                return {
                    "thought": step_text,
                    "action": "",
                    "observation": ""
                }
            return None
        
        # Debug: log what we're receiving
        logger.debug(f"Extracting trajectory from result type: {type(result)}")
        if hasattr(result, '__dict__'):
            logger.debug(f"Result attributes: {list(result.__dict__.keys())}")
        
        raw_traj = None
        if isinstance(result, dict):
            raw_traj = result.get("trajectory") or result.get("trace") or result.get("traces")
        if raw_traj is None and hasattr(result, "trajectory"):
            raw_traj = result.trajectory
        if raw_traj is None and hasattr(result, "trace"):
            raw_traj = result.trace
        if raw_traj is None and hasattr(result, "traces"):
            raw_traj = result.traces

        # DSPy ReAct may store trajectory as dict with thought_N/tool_name_N keys
        if isinstance(raw_traj, dict):
            traj_dict = raw_traj
            logger.debug(f"Trajectory dict keys: {list(traj_dict.keys())[:10]}")

            step_nums = set()
            for key in traj_dict.keys():
                match = re.search(r'_(\d+)$', key)
                if match:
                    try:
                        step_nums.add(int(match.group(1)))
                    except ValueError:
                        pass

            if step_nums:
                logger.info(f"Found {len(step_nums)} steps in trajectory")
                for i in sorted(step_nums):
                    thought = _pluck(
                        traj_dict,
                        f"thought_{i}",
                        f"thoughts_{i}",
                        f"reasoning_{i}"
                    )
                    action = _pluck(
                        traj_dict,
                        f"action_{i}",
                        f"tool_name_{i}",
                        f"tool_{i}",
                        f"toolname_{i}"
                    )
                    tool_args = _pluck(
                        traj_dict,
                        f"tool_args_{i}",
                        f"action_input_{i}",
                        f"args_{i}",
                        f"input_{i}"
                    )
                    observation = _pluck(
                        traj_dict,
                        f"observation_{i}",
                        f"result_{i}",
                        f"output_{i}"
                    )
                    step = _build_step(thought, action, tool_args, observation)
                    if step:
                        trajectory.append(step)
            else:
                steps = None
                if isinstance(traj_dict.get("steps"), list):
                    steps = traj_dict.get("steps")
                elif isinstance(traj_dict.get("trajectory"), list):
                    steps = traj_dict.get("trajectory")
                if steps:
                    for step in steps:
                        parsed = _parse_step(step)
                        if parsed:
                            trajectory.append(parsed)
        elif isinstance(raw_traj, (list, tuple)):
            for step in raw_traj:
                parsed = _parse_step(step)
                if parsed:
                    trajectory.append(parsed)
        else:
            logger.warning("No trajectory data found in result")
        
        # Also include final reasoning if present
        if not trajectory and hasattr(result, "reasoning") and result.reasoning:
            final_step = _build_step(result.reasoning, "final_answer", None, getattr(result, "answer", ""))
            if final_step:
                trajectory.append(final_step)
        
        logger.info(f"Extracted trajectory with {len(trajectory)} steps")
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
        
    Note: Caller must ensure DSPy is configured (via dspy.context() or dspy.configure())
    """
    global _agent_instance
    
    # Don't call _ensure_dspy_configured() here - caller is responsible
    # This allows using dspy.context() for thread-safe configuration
    
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
    # Configure DSPy for this thread using context manager
    # This avoids the "can only be changed by the thread that initially configured it" error
    if os.environ.get("OPENAI_API_KEY"):
        model = "openai/gpt-4o-mini"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        model = "anthropic/claude-3-haiku-20240307"
    else:
        model = "ollama/llama3"
    
    lm = dspy.LM(model=model)
    
    # Use context manager for thread-safe configuration
    with dspy.context(lm=lm):
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
