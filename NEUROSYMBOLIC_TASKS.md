# Neurosymbolic Ingestion Tasks

## Overview
3-pass knowledge distillation from raw sources into executable lore, using DSPy for predictable prompt execution.

## Tasks

### Phase 0: DSPy Setup
- [x] **T0.0**: Add `dspy-ai` to `requirements.txt` ✅
- [x] **T0.1**: Configure DSPy LM (OpenAI via LiteLLM) ✅
- [x] **T0.2**: Create `brain.capsules` table ✅
- [x] **T0.3**: Create `brain.facts` table ✅
- [x] **T0.4**: Create `brain.rules` table ✅

### Phase 1: DSPy Signatures
- [x] **T1.1**: Define `CondenseDocument` signature ✅
- [x] **T1.2**: Define `ExtractFacts` signature ✅
- [x] **T1.3**: Define `DistillRules` signature ✅

### Phase 2: DSPy Modules
- [x] **T2.1**: Create `NeuroIngestionPipeline` module ✅
- [x] **T2.2**: Replace `condense_document()` with DSPy predictor ✅
- [x] **T2.3**: Replace `extract_facts()` with DSPy predictor ✅
- [x] **T2.4**: Replace `distill_rules()` with DSPy predictor ✅

### Phase 3: Integration
- [x] **T3.1**: Wire DSPy pipeline into `neurosymbolic_distill()` ✅
- [x] **T3.2**: Add fallback to litellm if DSPy fails ✅
- [x] **T3.3**: Test with sample documents ✅

### Phase 4: Optimization (Future)
- [ ] **T4.1**: Collect training examples from successful extractions
- [ ] **T4.2**: Run DSPy optimizer (MIPROv2 / BootstrapFewShot)
- [ ] **T4.3**: Save optimized prompts

## Current: Phase 4 - Optimization (In Progress)
