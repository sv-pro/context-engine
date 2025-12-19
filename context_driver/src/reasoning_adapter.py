"""
Reasoning Model Adapter for OpenAI o1/o3 models.

Adapts OpenAI reasoning models to work with existing RAG pipeline by:
1. Merging system messages into user messages (o1/o3 don't support system role)
2. Converting max_tokens to max_completion_tokens
3. Removing unsupported parameters (temperature, top_p)
"""

from typing import Dict, List, Any


class ReasoningModelAdapter:
    """Adapts OpenAI reasoning models (o1/o3) to work with existing RAG pipeline."""
    
    REASONING_MODELS = {'o1-preview', 'o1-mini', 'o3-mini', 'o1', 'o3'}
    
    def is_reasoning_model(self, model: str) -> bool:
        """Check if the model is a reasoning model."""
        return any(model.startswith(rm) for rm in self.REASONING_MODELS)
    
    def adapt_request(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Convert standard chat request to reasoning model format.
        
        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters (max_tokens, temperature, etc.)
        
        Returns:
            Adapted request dict ready for LiteLLM
        """
        if not self.is_reasoning_model(model):
            # Not a reasoning model, return as-is
            return {"model": model, "messages": messages, **kwargs}
        
        # Reasoning models don't support system messages
        # Merge system prompt into first user message
        adapted_messages = []
        system_content = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n\n"
            elif msg["role"] == "user" and system_content:
                # Prepend system content to first user message
                adapted_messages.append({
                    "role": "user",
                    "content": system_content + msg["content"]
                })
                system_content = ""  # Clear after first use
            else:
                adapted_messages.append(msg)
        
        # If system content remains (no user message yet), add it as first user message
        if system_content:
            adapted_messages.insert(0, {
                "role": "user",
                "content": system_content.strip()
            })
        
        # Reasoning models use max_completion_tokens instead of max_tokens
        adapted_kwargs = kwargs.copy()
        if "max_tokens" in adapted_kwargs:
            adapted_kwargs["max_completion_tokens"] = adapted_kwargs.pop("max_tokens")
        
        # Reasoning models don't support temperature/top_p
        # They use internal reasoning and don't expose these parameters
        adapted_kwargs.pop("temperature", None)
        adapted_kwargs.pop("top_p", None)
        
        # Reasoning models don't support streaming in the same way
        # Keep stream parameter but be aware of different behavior
        
        return {
            "model": model,
            "messages": adapted_messages,
            **adapted_kwargs
        }


# Global instance
adapter = ReasoningModelAdapter()
