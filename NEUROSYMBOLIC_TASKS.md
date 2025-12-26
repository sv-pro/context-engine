# Neurosymbolic Ingestion Tasks

## Overview
3-pass knowledge distillation from raw sources into executable lore, using DSPy for predictable prompt execution.

## Tasks

### Phase 0: DSPy Setup
- [ ] **T0.0**: Add `dspy-ai` to `requirements.txt`
- [ ] **T0.1**: Configure DSPy LM (OpenAI via LiteLLM)
- [x] **T0.2**: Create `brain.capsules` table ✅
- [x] **T0.3**: Create `brain.facts` table ✅
- [x] **T0.4**: Create `brain.rules` table ✅

### Phase 1: DSPy Signatures
- [ ] **T1.1**: Define `CondenseDocument` signature
- [ ] **T1.2**: Define `ExtractFacts` signature
- [ ] **T1.3**: Define `DistillRules` signature

### Phase 2: DSPy Modules
- [ ] **T2.1**: Create `NeuroIngestionPipeline` module
- [ ] **T2.2**: Replace `condense_document()` with DSPy predictor
- [ ] **T2.3**: Replace `extract_facts()` with DSPy predictor
- [ ] **T2.4**: Replace `distill_rules()` with DSPy predictor

### Phase 3: Integration
- [ ] **T3.1**: Wire DSPy pipeline into `neurosymbolic_distill()`
- [ ] **T3.2**: Add fallback to litellm if DSPy fails
- [ ] **T3.3**: Test with sample documents

### Phase 4: Optimization (Future)
- [ ] **T4.1**: Collect training examples from successful extractions
- [ ] **T4.2**: Run DSPy optimizer (MIPROv2 / BootstrapFewShot)
- [ ] **T4.3**: Save optimized prompts

## Current: T0.0 - Add dspy-ai to requirements.txt
