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
    priority = config.get("provider_priority", ["ollama", "anthropic"])
    chain = []
    for name in priority:
        provider_cls = REGISTRY.get(name)
        if provider_cls is None:
            continue
        # Each provider gets its own config block PLUS the detected distro,
        # so prompts can give distro-correct package-manager commands
        # without every provider needing its own os-release detection.
        provider_config = dict(config.get(name, {}))
        provider_config["distro"] = config.get("distro", "unknown")
        instance = provider_cls(provider_config)
        if instance.is_available():
            chain.append(instance)
    return chain


__all__ = ["Provider", "ProviderError", "REGISTRY", "build_provider_chain"]
