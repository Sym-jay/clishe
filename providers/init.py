"""
Provider registry. This is the only file that needs to change when a new
backend is added - clishe_brain.py and clishe.sh never need to know about
individual providers.
"""
from typing import List

from .base import Provider, ProviderError
from .ollama_provider import OllamaProvider
from .anthropic_provider import AnthropicProvider

# name -> class. Add new providers here (e.g. "openai": OpenAIProvider) and
# nowhere else.
REGISTRY = {
    "ollama": OllamaProvider,
    "anthropic": AnthropicProvider,
}


def build_provider_chain(config: dict) -> List[Provider]:
    """Build the ordered list of provider instances to try, based on
    config['provider_priority'], skipping any whose is_available() is False
    (missing key, server not running, etc). Order matters: put free/local/fast
    options first."""
    priority = config.get("provider_priority", ["ollama", "anthropic"])
    chain = []
    for name in priority:
        provider_cls = REGISTRY.get(name)
        if provider_cls is None:
            continue
        provider_config = config.get(name, {})
        instance = provider_cls(provider_config)
        if instance.is_available():
            chain.append(instance)
    return chain


__all__ = ["Provider", "ProviderError", "REGISTRY", "build_provider_chain"]
