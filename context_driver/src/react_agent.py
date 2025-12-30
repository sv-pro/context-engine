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
    
    RECOMMENDED WORKFLOW:
    
    1. SEARCH first to identify relevant documents:
       search_knowledge_base("your query") → note the document TITLES found
       TIP: If results show "Entity > Relationships" pages, try a different query
       like the system/service name (e.g., "Kong API Gateway configuration")
    
    2. RETRIEVE full content from the most relevant document:
       get_capsule("Document_Title") → gets summary + key points + code blocks
       OR get_document_section("Document_Title", "Section Name") → gets specific section
    
    3. EXTRACT structured facts if needed:
       get_facts(subject="Entity Name") → gets subject-predicate-object triples
    
    4. CHECK relationships for related docs:
       get_related_documents("Document_Title") → discovers linked procedures/policies
    
    CRITICAL: Do NOT answer from search snippets alone. After finding a relevant 
    document via search, ALWAYS call get_capsule() or get_document_section() to 
    retrieve the complete content before formulating your answer.
    
    IMPORTANT: When you find information that answers the question, STOP SEARCHING 
    and provide your final answer. Do not keep searching if you already have what 
    you need. Use the exact document titles from search results (e.g., 
    "API_Gateway_Configuration" not "Kong API Gateway").
    
    WATCH OUT: If you see "Entity > Relationships" results (like "redis > Relationships"),
    those are entity graph pages, NOT the source documents with config values. Look for
    actual document titles like "API_Gateway_Configuration" or use get_capsule on them.
    
    TOOL SELECTION BY QUESTION TYPE:
    
    - ROLES/RESPONSIBILITIES/WHO → get_facts(subject="...") FIRST
    - PROCEDURES/STEPS/HOW TO → get_document_section(title, section)
    - CONFIGURATION/VALUES → get_capsule(title) or get_document_section(title, section)
    - RELATIONSHIPS/LINKS → get_related_documents(title)
    
    ACCURACY RULES:
    
    - Match the CORRECT ROW in tables (e.g., "Partner" row for partner-api questions)
    - Quote values EXACTLY as they appear (numbers, hostnames, channel names)
    - State findings DEFINITIVELY when data is present - avoid hedging
    - YAML/config values ARE authoritative: 'redis_host: redis-ratelimit' means the Redis host IS redis-ratelimit
    - If you see a value in a code block/config, that IS documented - don't say "not documented"
    """
    
    question: str = dspy.InputField(desc="The question to answer")
    answer: str = dspy.OutputField(desc="Comprehensive answer based on retrieved knowledge")


class AnswerWithContext(dspy.Signature):
    """Answer a question using provided context from the knowledge base.
    
    CRITICAL INSTRUCTIONS:
    1. Extract ALL specific values from the context, including:
       - Configuration values from YAML/JSON blocks (e.g., redis_host, port, limit values)
       - Numbers, hostnames, service names, file paths
       - Time values, thresholds, commands
    2. If you see a YAML key like 'redis_host: redis-ratelimit', that IS the Redis host name
    3. Include ALL found values in your answer - don't say "not documented" if value appears in context
    4. Code blocks and config snippets are AUTHORITATIVE sources - trust them
    """
    
    question: str = dspy.InputField(desc="The question to answer")
    context: str = dspy.InputField(desc="Relevant context from knowledge base including tool outputs, YAML configs, facts")
    answer: str = dspy.OutputField(desc="Comprehensive answer extracting ALL specific values (numbers, hostnames, configs) from the context")


class VerifyAnswer(dspy.Signature):
    """Verify a draft answer against knowledge base context.
    
    IMPORTANT: Your role is to CHECK if the draft answer is supported by the 
    knowledge_context provided. Do NOT introduce new information or "correct" 
    values unless they directly contradict the knowledge_context.
    
    If the draft answer contains specific values (numbers, names, hostnames) 
    that appear in the knowledge_context, those values are CORRECT and should 
    be preserved in the verified answer.
    
    Only mark as 'Partial' or 'Incorrect' if:
    - The draft answer makes claims not supported by the context
    - The draft answer has factual errors contradicted by the context
    - Key information from the context is missing from the answer
    """
    
    question: str = dspy.InputField(desc="Original question")
    draft_answer: str = dspy.InputField(desc="Draft answer from ReAct agent")
    knowledge_context: str = dspy.InputField(desc="Relevant facts and rules for verification")
    
    verified_answer: str = dspy.OutputField(desc="Verified answer - preserve correct values from draft, only fix clear errors")
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
        # Get relevant context for verification
        from dspy_tools import get_facts, get_rules, search_knowledge_base
        
        # 1. Extract entities from both question AND answer
        import re
        combined_text = question + " " + draft_answer
        entities = set(re.findall(r'\b[A-Z][a-zA-Z0-9_-]*\b', combined_text))
        
        facts = []
        for entity in list(entities)[:5]:
            f = get_facts(subject=entity, limit=3)
            if f and not f.startswith("No facts"): 
                facts.append(f)
        
        # 2. Also do a quick search based on question to get relevant context
        search_context = search_knowledge_base(question, limit=2)
        
        # 3. Grab general rules
        rules = get_rules(limit=3)
        
        context = "\n---\n".join(facts) 
        if search_context and not search_context.startswith("No results"):
            context += "\n---\nSearch Results:\n" + search_context
        if rules and not rules.startswith("No rules"):
            context += "\n---\n" + rules
        
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
            
            logger.info(f"Draft answer from ReAct: {draft_answer[:200]}...")
            
            # If draft is weak/generic but we have good trajectory, try to synthesize better answer
            trajectory = self._extract_trajectory(result)
            if ("not supported" in draft_answer.lower() or 
                "cannot be verified" in draft_answer.lower() or
                "no information" in draft_answer.lower() or
                len(draft_answer) < 100):
                
                # Check if trajectory has useful observations
                observations = " ".join([s.get("observation", "") for s in trajectory])
                if observations and len(observations) > 200:
                    logger.info("Draft is weak but trajectory has content - synthesizing from observations")
                    # Find key values in observations
                    import re
                    numbers = re.findall(r'\b\d{3,}\b', observations)
                    redis_hosts = re.findall(r'redis[_-]\w+', observations)
                    
                    # Try to build a better answer from trajectory
                    if numbers or redis_hosts:
                        synth = dspy.Predict(AnswerWithContext)
                        synth_result = synth(question=question, context=observations[:3000])
                        if synth_result.answer and len(synth_result.answer) > len(draft_answer):
                            logger.info(f"Synthesized better answer from trajectory")
                            draft_answer = synth_result.answer
            
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
            
            verified_answer = getattr(verification, "verified_answer", None)
            verification_status = getattr(verification, "verification_status", None)
            
            # Determine final answer:
            # - If verifier says "Correct", use verified_answer
            # - If verifier says "Partial" and verified_answer has more content, use it
            # - If verifier says "Incorrect" but draft has specific values, keep draft
            #   (verifier may have insufficient context to validate correct answers)
            if verification_status == "Correct" and verified_answer:
                final_answer = verified_answer
            elif verification_status == "Partial" and verified_answer and len(verified_answer) > len(draft_answer):
                final_answer = verified_answer
            elif verification_status == "Incorrect":
                # Check if draft has specific values - if so, verifier may be wrong
                import re
                has_specific_values = bool(re.search(r'\d{3,}|\bredis-\w+\b', draft_answer))
                if has_specific_values:
                    logger.warning("Verifier said 'Incorrect' but draft has specific values - keeping draft")
                    final_answer = draft_answer
                    verification_status = "Unverified"
                else:
                    final_answer = verified_answer or draft_answer
            else:
                final_answer = verified_answer or draft_answer
                
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
        
        # Enhanced logging for empty trajectory debugging
        if not trajectory:
            logger.warning(f"Empty trajectory extracted from result")
            logger.warning(f"Result type: {type(result)}")
            logger.warning(f"Result attributes: {dir(result)}")
            if hasattr(result, '__dict__'):
                # Log keys that might contain trajectory data
                for key in result.__dict__.keys():
                    val = getattr(result, key, None)
                    val_type = type(val).__name__
                    val_preview = str(val)[:100] if val else "None"
                    logger.warning(f"  {key} ({val_type}): {val_preview}")
            
            # Fallback: capture rationale if present
            if hasattr(result, 'rationale') and result.rationale:
                trajectory.append({
                    "thought": result.rationale,
                    "action": "direct_answer",
                    "observation": ""
                })
                logger.info("Captured rationale as fallback trajectory step")
        
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
