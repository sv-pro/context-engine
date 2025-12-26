"""
DSPy Optimizer Module for Neurosymbolic Pipeline.

This module provides:
1. TrainingExampleCollector - Captures successful extractions for optimization
2. Optimizer runner - Executes DSPy optimizers (MIPROv2, BootstrapFewShot)
3. Optimized pipeline loader - Loads pre-optimized prompts
"""

import os
import json
import logging
import dspy
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default storage location for training examples and optimized models
TRAINING_DATA_DIR = os.environ.get("DSPY_TRAINING_DIR", "/app/dspy_training")
OPTIMIZED_MODELS_DIR = os.environ.get("DSPY_MODELS_DIR", "/app/dspy_models")


class TrainingExample:
    """A single training example for DSPy optimization."""
    
    def __init__(self, title: str, content: str, result: Dict[str, Any], timestamp: str = None):
        self.title = title
        self.content = content
        self.result = result
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content[:2000],  # Truncate for storage
            "result": self.result,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingExample":
        return cls(
            title=data["title"],
            content=data["content"],
            result=data["result"],
            timestamp=data.get("timestamp")
        )


class TrainingExampleCollector:
    """
    Collects successful extraction examples for DSPy optimization.
    
    Examples are stored as JSON files in TRAINING_DATA_DIR.
    """
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or TRAINING_DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._examples_file = self.data_dir / "training_examples.jsonl"
    
    def save_example(self, title: str, content: str, result: Dict[str, Any]) -> bool:
        """
        Save a successful extraction as a training example.
        
        Args:
            title: Document title
            content: Document content
            result: The extraction result from NeuroIngestionPipeline
            
        Returns:
            True if saved successfully
        """
        try:
            example = TrainingExample(title=title, content=content, result=result)
            
            with open(self._examples_file, "a") as f:
                f.write(json.dumps(example.to_dict()) + "\n")
            
            logger.info(f"[DSPy Optimizer] Saved training example: {title}")
            return True
            
        except Exception as e:
            logger.error(f"[DSPy Optimizer] Failed to save example: {e}")
            return False
    
    def load_examples(self, limit: int = None) -> List[TrainingExample]:
        """
        Load training examples from storage.
        
        Args:
            limit: Maximum number of examples to load (None = all)
            
        Returns:
            List of TrainingExample objects
        """
        examples = []
        
        if not self._examples_file.exists():
            return examples
        
        try:
            with open(self._examples_file, "r") as f:
                for i, line in enumerate(f):
                    if limit and i >= limit:
                        break
                    if line.strip():
                        data = json.loads(line)
                        examples.append(TrainingExample.from_dict(data))
            
            logger.info(f"[DSPy Optimizer] Loaded {len(examples)} training examples")
            return examples
            
        except Exception as e:
            logger.error(f"[DSPy Optimizer] Failed to load examples: {e}")
            return []
    
    def count_examples(self) -> int:
        """Count the number of stored examples."""
        if not self._examples_file.exists():
            return 0
        
        with open(self._examples_file, "r") as f:
            return sum(1 for line in f if line.strip())
    
    def clear_examples(self):
        """Clear all stored training examples."""
        if self._examples_file.exists():
            self._examples_file.unlink()
            logger.info("[DSPy Optimizer] Cleared training examples")


def create_dspy_trainset(examples: List[TrainingExample]) -> List[dspy.Example]:
    """
    Convert TrainingExamples to DSPy Example format for optimization.
    
    Args:
        examples: List of TrainingExample objects
        
    Returns:
        List of dspy.Example objects
    """
    trainset = []
    
    for ex in examples:
        capsule = ex.result.get("capsule", {})
        
        # Create DSPy example with input/output fields
        dspy_ex = dspy.Example(
            title=ex.title,
            content=ex.content[:4000],
            summary=capsule.get("summary", ""),
            key_points=capsule.get("key_points", []),
            intent=capsule.get("intent", "unknown"),
            domain=capsule.get("domain", "unknown"),
            confidence=capsule.get("confidence", 0.0)
        ).with_inputs("title", "content")
        
        trainset.append(dspy_ex)
    
    return trainset


def run_optimization(
    optimizer_type: str = "BootstrapFewShot",
    num_examples: int = 20,
    save_path: str = None
) -> Optional[dspy.Module]:
    """
    Run DSPy optimization on collected training examples.
    
    Args:
        optimizer_type: "BootstrapFewShot" or "MIPROv2"
        num_examples: Number of training examples to use
        save_path: Path to save the optimized module
        
    Returns:
        Optimized dspy.Module or None if optimization fails
    """
    from dspy_signatures import NeuroIngestionPipeline, configure_dspy
    
    # Ensure DSPy is configured
    configure_dspy()
    
    # Load training examples
    collector = TrainingExampleCollector()
    examples = collector.load_examples(limit=num_examples)
    
    if len(examples) < 5:
        logger.warning(f"[DSPy Optimizer] Not enough examples ({len(examples)}). Need at least 5.")
        return None
    
    trainset = create_dspy_trainset(examples)
    logger.info(f"[DSPy Optimizer] Created trainset with {len(trainset)} examples")
    
    # Create base module
    module = NeuroIngestionPipeline()
    
    # Select and run optimizer
    try:
        if optimizer_type == "BootstrapFewShot":
            from dspy.teleprompt import BootstrapFewShot
            
            # Simple metric: check if summary is non-empty
            def simple_metric(example, pred, trace=None):
                if hasattr(pred, 'capsule'):
                    return len(pred.capsule.get("summary", "")) > 10
                return False
            
            optimizer = BootstrapFewShot(metric=simple_metric, max_bootstrapped_demos=3)
            optimized = optimizer.compile(module, trainset=trainset)
            
        elif optimizer_type == "MIPROv2":
            from dspy.teleprompt import MIPROv2
            
            def simple_metric(example, pred, trace=None):
                if hasattr(pred, 'capsule'):
                    return len(pred.capsule.get("summary", "")) > 10
                return False
            
            optimizer = MIPROv2(metric=simple_metric, num_candidates=5)
            optimized = optimizer.compile(module, trainset=trainset)
            
        else:
            logger.error(f"[DSPy Optimizer] Unknown optimizer type: {optimizer_type}")
            return None
        
        # Save optimized module
        if save_path is None:
            models_dir = Path(OPTIMIZED_MODELS_DIR)
            models_dir.mkdir(parents=True, exist_ok=True)
            save_path = str(models_dir / f"optimized_{optimizer_type.lower()}.json")
        
        optimized.save(save_path)
        logger.info(f"[DSPy Optimizer] Saved optimized module to: {save_path}")
        
        return optimized
        
    except Exception as e:
        logger.error(f"[DSPy Optimizer] Optimization failed: {e}")
        return None


def load_optimized_pipeline(model_path: str = None) -> Optional[dspy.Module]:
    """
    Load a pre-optimized pipeline.
    
    Args:
        model_path: Path to the optimized model JSON file
        
    Returns:
        Loaded dspy.Module or None if loading fails
    """
    from dspy_signatures import NeuroIngestionPipeline, configure_dspy
    
    # Ensure DSPy is configured
    configure_dspy()
    
    # Find model file
    if model_path is None:
        models_dir = Path(OPTIMIZED_MODELS_DIR)
        candidates = list(models_dir.glob("optimized_*.json"))
        if not candidates:
            logger.warning("[DSPy Optimizer] No optimized models found")
            return None
        model_path = str(candidates[0])
    
    try:
        module = NeuroIngestionPipeline()
        module.load(model_path)
        logger.info(f"[DSPy Optimizer] Loaded optimized module from: {model_path}")
        return module
        
    except Exception as e:
        logger.error(f"[DSPy Optimizer] Failed to load optimized module: {e}")
        return None


def get_optimizer_status() -> Dict[str, Any]:
    """
    Get the current status of the optimizer.
    
    Returns:
        Dict with example count, available models, etc.
    """
    collector = TrainingExampleCollector()
    models_dir = Path(OPTIMIZED_MODELS_DIR)
    
    available_models = []
    if models_dir.exists():
        available_models = [f.name for f in models_dir.glob("optimized_*.json")]
    
    return {
        "training_examples_count": collector.count_examples(),
        "training_data_dir": str(collector.data_dir),
        "models_dir": str(models_dir),
        "available_models": available_models,
        "ready_for_optimization": collector.count_examples() >= 5
    }
