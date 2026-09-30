"""
Provider - the common interface every AI backend (local or cloud) must implement.

Keeping this interface tiny on purpose: two operations, both optional-returning.
Anything provider-specific (auth, prompt format, HTTP client) lives inside the
provider subclass, never leaks into clishe_brain.py.
"""
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class ProviderError(Exception):
    """Raised for expected failures (timeout, bad auth, empty response).
    Callers catch this and fall through to the next provider."""
    pass


@dataclass
class Resolution:
    """A suggested command plus the model's one-line reason for it."""
    command: str
    explanation: str = ""


def parse_json_reply(text: str) -> dict:
    """Parse a model's JSON reply, tolerating markdown fences or chatter
    around the object (small local models add both). Raises ProviderError
    if there's no JSON object in it at all."""
    cleaned = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ProviderError(f"No JSON object in model reply: {cleaned[:80]!r}")
        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as e:
            raise ProviderError(f"Could not parse model reply as JSON: {e}") from e
    if not isinstance(data, dict):
        raise ProviderError("Model reply was JSON but not an object")
    return data


def distro_note(distro: str) -> str:
    """Extra prompt text so package-manager answers fit the user's distro."""
    if not distro or distro == "unknown":
        return ""
    return (f" The user's system is running the '{distro}' Linux distribution - "
            f"use its native package manager and conventions (e.g. apt for "
            f"debian/ubuntu, dnf for fedora, pacman for arch) when relevant.")


def resolution_from_reply(data: dict) -> Optional[Resolution]:
    """Turn {"command": ..., "explanation": ...} into a Resolution, or None
    if the model declined (null/empty command)."""
    command = data.get("command")
    if not command or not isinstance(command, str) or not command.strip():
        return None
    explanation = data.get("explanation")
    if not isinstance(explanation, str):
        explanation = ""
    return Resolution(command.strip(), explanation.strip())


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

    def resolve_with_explanation(self, phrase: str) -> Optional[Resolution]:
        """Like resolve_command, but also returns the model's short reason so
        the user learns *why* this command does what they asked. Providers
        that can't give a reason don't need to override this."""
        command = self.resolve_command(phrase)
        return Resolution(command) if command else None

    @abstractmethod
    def explain_command(self, command: str) -> Optional[str]:
        """Return a short, beginner-friendly explanation of what a shell
        command does. Return None if unsure; raise ProviderError on failure."""
        raise NotImplementedError
