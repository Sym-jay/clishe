"""
Ollama provider - talks to a locally running Ollama server (default
http://localhost:11434). No API key, no internet required, which matters a
lot for a "teach beginners the terminal" tool: it should work on a plane.
"""
import json
import urllib.request
import urllib.error
from typing import Optional

from .base import (EXPLAIN_PROMPT, RESOLVE_PROMPT, Provider, ProviderError,
                   Resolution, distro_note, parse_json_reply, resolution_from_reply)

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
TIMEOUT_SECONDS = 30  # local models on modest hardware can be slow
AVAILABILITY_CHECK_TIMEOUT = 1.5  # keep the "is this even running" check snappy


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, config: dict):
        super().__init__(config)
        self.host = self.config.get("host", DEFAULT_HOST).rstrip("/")
        self.model = self.config.get("model", DEFAULT_MODEL)
        self.distro = self.config.get("distro", "unknown")
        self.family = self.config.get("distro_family", [])

    def is_available(self) -> bool:
        """Ping the server's tag list endpoint - fast, no model load needed."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=AVAILABILITY_CHECK_TIMEOUT):
                return True
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    # ---------- internal ----------

    def _generate(self, system: str, prompt: str) -> dict:
        payload = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # ask Ollama to constrain output to valid JSON
        }
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Ollama HTTP {e.code}: {detail[:200]}") from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Ollama unreachable at {self.host}: {e.reason}") from e
        except (TimeoutError, OSError) as e:
            raise ProviderError(f"Ollama timeout/network error: {e}") from e

        raw_text = body.get("response", "").strip()
        if not raw_text:
            raise ProviderError("Empty response from Ollama")

        return parse_json_reply(raw_text)

    _ask = _generate

    # ---------- public API ----------

    def resolve_with_explanation(self, phrase: str) -> Optional[Resolution]:
        system = RESOLVE_PROMPT + distro_note(self.distro, self.family)
        return resolution_from_reply(self._generate(system, f"Request: {phrase}"))

    def resolve_command(self, phrase: str) -> Optional[str]:
        result = self.resolve_with_explanation(phrase)
        return result.command if result else None

    def explain_command(self, command: str) -> Optional[str]:
        system = EXPLAIN_PROMPT + distro_note(self.distro, self.family)
        data = self._generate(system, f"Command: {command}")
        explanation = data.get("explanation")
        if not explanation or not isinstance(explanation, str):
            return None
        return explanation.strip()
