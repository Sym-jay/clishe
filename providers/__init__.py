"""
Provider registry. This is the only file that needs to change when a new
backend is added - clishe_brain.py and clishe.sh never need to know about
individual providers.
"""
import sys
from typing import List

from .base import Provider, ProviderError, Resolution, is_local_address
from .ollama_provider import OllamaProvider
from .local_provider import LocalProvider
from .anthropic_provider import AnthropicProvider

# name -> class. Add new providers here (e.g. "openai": OpenAIProvider) and
# nowhere else.
REGISTRY = {
    "ollama": OllamaProvider,
    "local": LocalProvider,
    "anthropic": AnthropicProvider,
}


def opted_in(block: dict) -> bool:
    """A cloud provider runs only if the user turned it on. Older configs had
    no "enabled" switch, so an API key typed into the config counts as
    turning it on; an API key that merely exists in the environment (for
    some other tool) does not."""
    if "enabled" in block:
        return block.get("enabled") is True
    return bool(block.get("api_key"))


def _hosts(provider: Provider) -> List[str]:
    return list(getattr(provider, "hosts", None) or
                [h for h in [getattr(provider, "host", "")] if h])


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
        block = config.get(name, {}) if isinstance(config.get(name), dict) else {}
        provider_config = dict(block)
        provider_config["distro"] = config.get("distro", "unknown")
        provider_config["distro_family"] = config.get("distro_family", [])
        instance = provider_cls(provider_config)

        # Everything stays on your machine unless you say otherwise.
        if not instance.local and not opted_in(block):
            continue
        if instance.local and not config.get("allow_remote_ai"):
            remote = [h for h in _hosts(instance) if not is_local_address(h)]
            if remote:
                print(f"[{name}] {remote[0]} isn't on this computer or your local "
                      f"network, so I won't send it anything. To allow it, set "
                      f'"allow_remote_ai": true in the config.', file=sys.stderr)
                continue
        if instance.is_available():
            chain.append(instance)
    return chain


__all__ = ["Provider", "ProviderError", "Resolution", "REGISTRY", "build_provider_chain",
           "opted_in"]
