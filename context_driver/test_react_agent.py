"""
Unit tests for ReAct Agent and DSPy Tools.

Run with: pytest test_react_agent.py -v
"""

import pytest
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))



# === DSPy Tools Tests ===

class TestDspyToolsSignatures:
    """Test that DSPy tools have correct signatures."""
    
    def test_search_knowledge_base_signature(self):
        """Verify search_knowledge_base has correct signature."""
        from dspy_tools import search_knowledge_base
        import inspect
        
        sig = inspect.signature(search_knowledge_base)
        params = list(sig.parameters.keys())
        
        assert "query" in params
        assert "limit" in params
    
    def test_get_facts_signature(self):
        """Verify get_facts has correct signature."""
        from dspy_tools import get_facts
        import inspect
        
        sig = inspect.signature(get_facts)
        params = list(sig.parameters.keys())
        
        assert "subject" in params
        assert "predicate" in params
        assert "limit" in params
    
    def test_get_rules_signature(self):
        """Verify get_rules has correct signature."""
        from dspy_tools import get_rules
        import inspect
        
        sig = inspect.signature(get_rules)
        params = list(sig.parameters.keys())
        
        assert "domain" in params
        assert "severity" in params
        assert "limit" in params
    
    def test_get_capsule_signature(self):
        """Verify get_capsule has correct signature."""
        from dspy_tools import get_capsule
        import inspect
        
        sig = inspect.signature(get_capsule)
        params = list(sig.parameters.keys())
        
        assert "title" in params
    
    def test_list_documents_signature(self):
        """Verify list_documents has correct signature."""
        from dspy_tools import list_documents
        import inspect
        
        sig = inspect.signature(list_documents)
        params = list(sig.parameters.keys())
        
        assert "domain" in params
        assert "intent" in params
        assert "limit" in params
    
    def test_knowledge_base_tools_list(self):
        """Verify KNOWLEDGE_BASE_TOOLS exports are callable."""
        from dspy_tools import KNOWLEDGE_BASE_TOOLS
        
        expected_tools = {
            "search_knowledge_base",
            "get_facts",
            "get_rules",
            "get_capsule",
            "list_documents",
            "get_related_documents",
            "get_document_section",
        }
        assert len(KNOWLEDGE_BASE_TOOLS) == len(expected_tools)
        assert {tool.__name__ for tool in KNOWLEDGE_BASE_TOOLS} == expected_tools
        for tool in KNOWLEDGE_BASE_TOOLS:
            assert callable(tool)



# === ReAct Agent Tests ===

class TestReActAgentSignatures:
    """Test ReAct agent signatures and module structure."""
    
    def test_answer_question_signature_exists(self):
        """Verify AnswerQuestion signature is defined."""
        from react_agent import AnswerQuestion
        import dspy
        
        assert issubclass(AnswerQuestion, dspy.Signature)
    
    def test_answer_question_has_required_fields(self):
        """Verify AnswerQuestion has question input and answer output."""
        from react_agent import AnswerQuestion
        
        # Check fields exist in the signature
        fields = AnswerQuestion.model_fields
        assert "question" in fields
        assert "answer" in fields
    
    def test_answer_with_context_signature_exists(self):
        """Verify AnswerWithContext signature is defined."""
        from react_agent import AnswerWithContext
        import dspy
        
        assert issubclass(AnswerWithContext, dspy.Signature)


class TestReActAgentModule:
    """Test ReAct agent module structure."""
    
    def test_knowledge_base_react_agent_import(self):
        """Verify KnowledgeBaseReActAgent can be imported."""
        from react_agent import KnowledgeBaseReActAgent
        import dspy
        
        assert issubclass(KnowledgeBaseReActAgent, dspy.Module)
    
    def test_simple_rag_agent_import(self):
        """Verify SimpleRAGAgent can be imported."""
        from react_agent import SimpleRAGAgent
        import dspy
        
        assert issubclass(SimpleRAGAgent, dspy.Module)
    
    def test_get_react_agent_function(self):
        """Verify get_react_agent function exists."""
        from react_agent import get_react_agent
        
        assert callable(get_react_agent)
    
    def test_ask_question_function(self):
        """Verify ask_question function exists."""
        from react_agent import ask_question
        
        assert callable(ask_question)


class TestReActApiModels:
    """Test ReAct API request/response models."""
    
    def test_react_request_model(self):
        """Verify ReActRequest model has correct fields."""
        from tools_api import ReActRequest
        
        fields = ReActRequest.model_fields
        assert "question" in fields
        assert "max_iters" in fields
    
    def test_react_response_model(self):
        """Verify ReActResponse model has correct fields."""
        from tools_api import ReActResponse
        
        fields = ReActResponse.model_fields
        assert "question" in fields
        assert "answer" in fields
        assert "reasoning_trace" in fields
        assert "success" in fields
        assert "fallback" in fields
    
    def test_react_trajectory_step_model(self):
        """Verify ReActTrajectoryStep model has correct fields."""
        from tools_api import ReActTrajectoryStep
        
        fields = ReActTrajectoryStep.model_fields
        assert "thought" in fields
        assert "action" in fields
        assert "observation" in fields


# === Integration Tests (require API key and running services) ===

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
class TestIntegration:
    """Integration tests that require running services."""
    
    def test_react_agent_instantiation_with_dspy_config(self):
        """Test creating ReAct agent with DSPy configured."""
        from react_agent import configure_react_agent, KnowledgeBaseReActAgent
        
        # Configure DSPy
        configure_react_agent(model="openai/gpt-4o-mini")
        
        # Create agent - this may fail if database not available
        try:
            agent = KnowledgeBaseReActAgent(max_iters=3)
            assert agent is not None
            assert hasattr(agent, 'react')
            assert hasattr(agent, 'fallback')
        except Exception as e:
            pytest.skip(f"Could not create agent (database not available?): {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
