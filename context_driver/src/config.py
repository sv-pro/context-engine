import os

class EmbeddingConfig:
    def __init__(self, provider, model, dimensions):
        self.provider = provider
        self.model = model
        self.dimensions = dimensions

# Registry of supported configurations
# Format: "name": EmbeddingConfig(provider, model, dimensions)
EMBEDDING_CONFIGS = {
    "ollama-nomic": EmbeddingConfig(
        provider="ollama", 
        model="nomic-embed-text", 
        dimensions=768
    ),
    "ollama-mxbai": EmbeddingConfig(
        provider="ollama", 
        model="mxbai-embed-large:latest", 
        dimensions=1024
    ),
    "openai-small": EmbeddingConfig(
        provider="openai", 
        model="text-embedding-3-small", 
        dimensions=1536
    ),
    "openai-large": EmbeddingConfig(
        provider="openai", 
        model="text-embedding-3-large", 
        dimensions=3072
    ),
}

def get_current_config():
    config_name = os.environ.get("EMBEDDING_CONFIGURATION", "ollama-nomic")
    if config_name not in EMBEDDING_CONFIGS:
        raise ValueError(f"Unknown EMBEDDING_CONFIGURATION: {config_name}. Available: {list(EMBEDDING_CONFIGS.keys())}")
    return EMBEDDING_CONFIGS[config_name]

# Global instance to be imported
current_config = get_current_config()
