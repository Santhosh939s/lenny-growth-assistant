from app.services.llm.base import LLMProvider
from app.config import settings

def get_llm_provider() -> LLMProvider:
    provider = settings.MODEL_PROVIDER.lower()
    
    if provider == "ollama":
        from app.services.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    elif provider == "anthropic":
        from app.services.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    else:
        raise ValueError(f"Unknown MODEL_PROVIDER: {provider}")
