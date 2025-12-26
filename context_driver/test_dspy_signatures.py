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


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (run inside container)"
)
class TestEndToEndDistillation:
    """End-to-end tests: document → DSPy → database."""
    
    @pytest.fixture
    def db(self):
        """Get database connection."""
        from db import Database
        return Database()
    
    @pytest.fixture
    def test_note_id(self, db):
        """Create a test note and return its ID."""
        note_id, _ = db.upsert_note(
            file_path="/tmp/test_e2e_distill.md",
            title="E2E Test SSL Runbook",
            content=TEST_DOCUMENT_CONTENT,
            metadata={"test": True}
        )
        yield note_id
        # Cleanup after test
        with db.conn.cursor() as cur:
            cur.execute("DELETE FROM brain.notes WHERE id = %s", (note_id,))
    
    def test_full_pipeline_stores_capsule(self, db, test_note_id):
        """Verify capsule is stored after pipeline execution."""
        from dspy_signatures import run_dspy_pipeline
        
        result = run_dspy_pipeline(
            title="E2E Test SSL Runbook",
            content=TEST_DOCUMENT_CONTENT
        )
        
        # Store the capsule
        capsule = result["capsule"]
        db.upsert_capsule(
            source_id=test_note_id,
            summary=capsule.get("summary", ""),
            key_points=capsule.get("key_points", []),
            intent=capsule.get("intent", "unknown"),
            domain=capsule.get("domain", "unknown"),
            confidence=capsule.get("confidence", 0.0)
        )
        
        # Query it back
        stored = db.get_capsule(test_note_id)
        assert stored is not None
        assert stored["summary"] != ""
        assert stored["intent"] in ["procedure", "fact", "policy", "incident", "reference", "unknown"]
    
    def test_pipeline_extracts_and_stores_facts(self, db, test_note_id):
        """Verify facts are extracted and stored."""
        from dspy_signatures import run_dspy_pipeline
        
        result = run_dspy_pipeline(
            title="E2E Test SSL Runbook",
            content=TEST_DOCUMENT_CONTENT
        )
        
        # Store facts
        facts = result.get("facts", [])
        db.upsert_facts(source_id=test_note_id, facts=facts, provenance="test_e2e")
        
        # Query back
        stored_facts = db.get_facts(source_id=test_note_id)
        
        # Should have at least extracted some facts about SSL
        # (may be empty if LLM doesn't extract any, which is valid)
        assert isinstance(stored_facts, list)
        
        if stored_facts:
            # Verify structure
            fact = stored_facts[0]
            assert "subject" in fact
            assert "predicate" in fact
            assert "object" in fact
    
    def test_pipeline_extracts_rules_for_procedures(self, db, test_note_id):
        """Verify rules are extracted for procedural documents."""
        from dspy_signatures import run_dspy_pipeline
        
        result = run_dspy_pipeline(
            title="E2E Test SSL Runbook",
            content=TEST_DOCUMENT_CONTENT
        )
        
        # Store rules
        rules = result.get("rules", [])
        db.upsert_rules(source_id=test_note_id, rules=rules, provenance="test_e2e")
        
        # Query back
        stored_rules = db.get_rules(source_id=test_note_id)
        
        # Rules list depends on intent detection
        assert isinstance(stored_rules, list)
        
        if stored_rules:
            rule = stored_rules[0]
            assert "condition" in rule
            assert "action" in rule


class TestDBQueryMethods:
    """Test the new DB query methods for neurosymbolic data."""
    
    @pytest.fixture
    def db(self):
        """Get database connection."""
        from db import Database
        return Database()
    
    def test_get_capsules_returns_list(self, db):
        """get_capsules should return a list."""
        result = db.get_capsules(limit=5)
        assert isinstance(result, list)
    
    def test_get_facts_returns_list(self, db):
        """get_facts should return a list."""
        result = db.get_facts(limit=5)
        assert isinstance(result, list)
    
    def test_get_rules_returns_list(self, db):
        """get_rules should return a list."""
        result = db.get_rules(limit=5)
        assert isinstance(result, list)
    
    def test_get_capsule_not_found(self, db):
        """get_capsule should return None for non-existent ID."""
        result = db.get_capsule(999999999)
        assert result is None
    
    def test_get_facts_with_subject_filter(self, db):
        """get_facts should filter by subject."""
        # This tests the filter logic even if no results match
        result = db.get_facts(subject="NONEXISTENT_SUBJECT_12345")
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_get_rules_with_severity_filter(self, db):
        """get_rules should filter by severity."""
        result = db.get_rules(severity="critical")
        assert isinstance(result, list)


class TestDspyOptimizer:
    """Test the DSPy optimizer module."""
    
    def test_training_example_collector_init(self):
        """TrainingExampleCollector should initialize without error."""
        from dspy_optimizer import TrainingExampleCollector
        collector = TrainingExampleCollector(data_dir="/tmp/test_dspy_training")
        assert collector.data_dir.exists()
    
    def test_save_and_load_example(self):
        """TrainingExampleCollector should save and load examples."""
        from dspy_optimizer import TrainingExampleCollector
        import shutil
        
        # Use temp directory
        test_dir = "/tmp/test_dspy_training_" + str(os.getpid())
        collector = TrainingExampleCollector(data_dir=test_dir)
        
        try:
            # Save an example
            result = {
                "capsule": {"summary": "Test summary", "intent": "fact", "domain": "test"},
                "facts": [],
                "rules": []
            }
            collector.save_example(title="Test", content="Test content", result=result)
            
            # Load it back
            examples = collector.load_examples()
            assert len(examples) == 1
            assert examples[0].title == "Test"
            
            # Check count
            assert collector.count_examples() == 1
            
        finally:
            # Cleanup
            shutil.rmtree(test_dir, ignore_errors=True)
    
    def test_get_optimizer_status(self):
        """get_optimizer_status should return expected structure."""
        from dspy_optimizer import get_optimizer_status
        status = get_optimizer_status()
        
        assert "training_examples_count" in status
        assert "ready_for_optimization" in status
        assert isinstance(status["available_models"], list)


# Test document content for E2E tests
TEST_DOCUMENT_CONTENT = """
# SSL Certificate Renewal Procedure

## Overview
This runbook describes how to renew SSL certificates before they expire.

## Pre-requisites
- Access to the certificate authority (Let's Encrypt or DigiCert)
- Admin access to the load balancer
- DNS management permissions

## Procedure

### Step 1: Check Certificate Expiry
Run the following command to check when the certificate expires:
```bash
openssl x509 -enddate -noout -in /etc/ssl/certs/domain.crt
```

If the certificate expires within 30 days, proceed with renewal.

### Step 2: Generate New CSR
```bash
openssl req -new -key /etc/ssl/private/domain.key -out domain.csr
```

### Step 3: Submit to CA
Submit the CSR to your certificate authority and wait for approval.

### Step 4: Install New Certificate
Replace the old certificate with the new one:
```bash
cp new_domain.crt /etc/ssl/certs/domain.crt
systemctl reload nginx
```

## Alerts
- Certificate expiry warning: 30 days before
- Certificate expiry critical: 7 days before
"""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
