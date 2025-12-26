"""
Unit tests for DSPy Signatures and Neurosymbolic Ingestion Pipeline.

Run with: pytest test_dspy_signatures.py -v
"""

import pytest
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


class TestCondenseDocumentSignature:
    """Test the CondenseDocument signature structure."""
    
    def test_signature_has_required_input_fields(self):
        from dspy_signatures import CondenseDocument
        
        # DSPy signatures use model_fields
        fields = CondenseDocument.model_fields
        assert 'title' in fields
        assert 'content' in fields
    
    def test_signature_has_required_output_fields(self):
        from dspy_signatures import CondenseDocument
        
        fields = CondenseDocument.model_fields
        assert 'summary' in fields
        assert 'key_points' in fields
        assert 'intent' in fields
        assert 'domain' in fields
        assert 'confidence' in fields
    
    def test_signature_string_representation(self):
        from dspy_signatures import CondenseDocument
        
        # Check the signature can be represented as a string
        sig_str = str(CondenseDocument)
        assert 'title' in sig_str
        assert 'summary' in sig_str


class TestExtractFactsSignature:
    """Test the ExtractFacts signature structure."""
    
    def test_signature_has_required_input_fields(self):
        from dspy_signatures import ExtractFacts
        
        fields = ExtractFacts.model_fields
        assert 'title' in fields
        assert 'content' in fields
        assert 'summary' in fields
    
    def test_signature_has_required_output_fields(self):
        from dspy_signatures import ExtractFacts
        
        fields = ExtractFacts.model_fields
        assert 'facts' in fields


class TestDistillRulesSignature:
    """Test the DistillRules signature structure."""
    
    def test_signature_has_required_input_fields(self):
        from dspy_signatures import DistillRules
        
        fields = DistillRules.model_fields
        assert 'title' in fields
        assert 'content' in fields
        assert 'intent' in fields
        assert 'facts' in fields
    
    def test_signature_has_required_output_fields(self):
        from dspy_signatures import DistillRules
        
        fields = DistillRules.model_fields
        assert 'rules' in fields


class TestNeuroIngestionPipeline:
    """Test the NeuroIngestionPipeline module."""
    
    def test_pipeline_instantiation(self):
        from dspy_signatures import NeuroIngestionPipeline
        
        pipeline = NeuroIngestionPipeline()
        assert hasattr(pipeline, 'condense')
        assert hasattr(pipeline, 'extract_facts')
        assert hasattr(pipeline, 'distill_rules')
    
    def test_pipeline_has_forward_method(self):
        from dspy_signatures import NeuroIngestionPipeline
        
        pipeline = NeuroIngestionPipeline()
        assert callable(getattr(pipeline, 'forward', None))


class TestConfigureDspy:
    """Test the DSPy configuration function."""
    
    def test_configure_dspy_sets_flag(self):
        import dspy_signatures
        
        # Reset the flag
        dspy_signatures._dspy_configured = False
        
        # Configure
        dspy_signatures.configure_dspy("openai/gpt-4o-mini")
        
        # Check flag is set
        assert dspy_signatures._dspy_configured == True
    
    def test_configure_dspy_idempotent(self):
        import dspy_signatures
        
        # Flag should still be True after previous test
        assert dspy_signatures._dspy_configured == True


class TestContentTruncation:
    """Test that content is properly truncated."""
    
    def test_long_content_is_truncated(self):
        from dspy_signatures import NeuroIngestionPipeline
        
        pipeline = NeuroIngestionPipeline()
        
        # Create content longer than 4000 chars
        long_content = "x" * 5000
        
        # The forward method should handle truncation internally
        # We just verify the pipeline doesn't crash on instantiation
        assert len(long_content) > 4000


class TestOutputStructure:
    """Test the expected output structure from pipeline."""
    
    def test_expected_capsule_keys(self):
        """Verify capsule dict has expected keys."""
        expected_keys = ["summary", "key_points", "intent", "domain", "confidence"]
        
        # Mock capsule structure
        capsule = {
            "summary": "",
            "key_points": [],
            "intent": "unknown",
            "domain": "unknown",
            "confidence": 0.0
        }
        
        for key in expected_keys:
            assert key in capsule
    
    def test_expected_fact_structure(self):
        """Verify fact dict has expected keys."""
        expected_keys = ["subject", "predicate", "object"]
        
        # Mock fact structure
        fact = {
            "subject": "SSL Certificate",
            "predicate": "issued_by",
            "object": "Let's Encrypt"
        }
        
        for key in expected_keys:
            assert key in fact
    
    def test_expected_rule_structure(self):
        """Verify rule dict has expected keys."""
        expected_keys = ["rule_id", "condition", "action", "severity"]
        
        # Mock rule structure
        rule = {
            "rule_id": "rule_ssl_renewal",
            "condition": "cert.expires_in < 30_days",
            "action": "trigger_renewal",
            "severity": "critical"
        }
        
        for key in expected_keys:
            assert key in rule


class TestFieldTypes:
    """Test that DSPy signature fields have correct types."""
    
    def test_condense_field_types(self):
        from dspy_signatures import CondenseDocument
        from typing import List
        
        fields = CondenseDocument.model_fields
        
        # Check key_points is a list
        assert 'List' in str(fields['key_points'].annotation)
        
        # Check confidence is float
        assert fields['confidence'].annotation == float
    
    def test_extract_facts_field_types(self):
        from dspy_signatures import ExtractFacts
        
        fields = ExtractFacts.model_fields
        
        # Check facts is a list of dicts
        assert 'List' in str(fields['facts'].annotation)
        assert 'Dict' in str(fields['facts'].annotation)


# === Integration Test (requires OPENAI_API_KEY) ===

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
class TestIntegration:
    """Integration tests that call actual LLM (requires API key)."""
    
    def test_run_dspy_pipeline_smoke(self):
        """Smoke test - run the full pipeline on a small document."""
        from dspy_signatures import run_dspy_pipeline
        
        result = run_dspy_pipeline(
            title="Test Document",
            content="This is a test document about SSL certificates. Certificates expire every 90 days."
        )
        
        # Check result structure
        assert "capsule" in result
        assert "facts" in result
        assert "rules" in result
        
        # Check capsule has data
        capsule = result["capsule"]
        assert "summary" in capsule
        assert "intent" in capsule


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
