"""
Provider - the common interface every AI backend (local or cloud) must implement.

Keeping this interface tiny on purpose: two operations, both optional-returning.
Anything provider-specific (auth, prompt format, HTTP client) lives inside the
provider subclass, never leaks into clishe_brain.py.
"""
from abc import ABC, abstractmethod
from typing import Optional


class ProviderError(Exception):
    """Raised for expected failures (timeout, bad auth, empty response).
    Callers catch this and fall through to the next provider."""
    pass


class Provider(ABC):
    #: short machine name, e.g. "ollama", "anthropic" - used in config & logs
    name = "base"

    def __init__(self, config: dict):
        self.config = config or {}

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap, local check - do we even have what's needed to try this
        provider (an API key present, a local server reachable)? Should NOT
        make a real generation request."""
        raise NotImplementedError

    @abstractmethod
    def resolve_command(self, phrase: str) -> Optional[str]:
        """Translate a natural-language phrase into a single shell command.
        Return None (not raise) if the model declines/is unsure - that's a
        normal outcome, not an error. Raise ProviderError for actual failures
        (network, auth, malformed response) so the caller can try the next
        provider in the chain."""
        raise NotImplementedError

    @abstractmethod
    def explain_command(self, command: str) -> Optional[str]:
        """Return a short, beginner-friendly explanation of what a shell
        command does. Return None if unsure; raise ProviderError on failure."""
        raise NotImplementedError
