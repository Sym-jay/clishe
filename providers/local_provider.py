"""
Local provider - any model server on your own machine that speaks the
OpenAI-style chat API: llama.cpp's llama-server, LM Studio, Jan, LocalAI,
vLLM and others. No API key and no internet.

With no "host" in the config it looks for a server on the usual ports, and
with no "model" it uses the first model the server lists, so most people
don't need to configure anything: start the server and Clishe finds it.
"""
import json
import urllib.request
import urllib.error
from typing import List, Optional

from .base import (EXPLAIN_PROMPT, RESOLVE_PROMPT, Provider, ProviderError,
                   Resolution, distro_note, parse_json_reply, resolution_from_reply)

# Where the popular local servers listen by default.
DEFAULT_HOSTS = [
    "http://localhost:8080",   # llama.cpp llama-server, LocalAI
    "http://localhost:1234",   # LM Studio
    "http://localhost:1337",   # Jan
    "http://localhost:8000",   # vLLM
]
TIMEOUT_SECONDS = 60  # local models on modest hardware can be slow
AVAILABILITY_CHECK_TIMEOUT = 1.0


class LocalProvider(Provider):
    name = "local"

    def __init__(self, config: dict):
        super().__init__(config)
        host = (self.config.get("host") or "").rstrip("/")
        self.hosts: List[str] = [host] if host else list(DEFAULT_HOSTS)
        self.host = host
        self.model = self.config.get("model", "")
        self.api_key = self.config.get("api_key", "")  # some servers want any token
        self.distro = self.config.get("distro", "unknown")
        self.family = self.config.get("distro_family", [])

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def is_available(self) -> bool:
        """Find the first server that answers /v1/models, and pick its first
        model if none is configured."""
        for host in self.hosts:
            req = urllib.request.Request(f"{host}/v1/models", headers=self._headers())
            try:
                with urllib.request.urlopen(req, timeout=AVAILABILITY_CHECK_TIMEOUT) as resp:
                    body = json.loads(resp.read().decode("utf-8") or "{}")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                continue
            models = [m.get("id") for m in body.get("data", []) if isinstance(m, dict)]
            if not self.model and models and models[0]:
                self.model = models[0]
            self.host = host
            return True
        return False

    # ---------- internal ----------

    def _chat(self, system: str, user: str) -> dict:
        payload = {
            "model": self.model or "default",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": 300,
            "stream": False,
        }
        req = urllib.request.Request(
            f"{self.host}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Local model HTTP {e.code}: {detail[:200]}") from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Local model unreachable at {self.host}: {e.reason}") from e
        except (TimeoutError, OSError) as e:
            raise ProviderError(f"Local model timeout/network error: {e}") from e

        try:
            raw_text = (body["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"Unexpected response from local model: {e}") from e
        if not raw_text:
            raise ProviderError("Empty response from local model")
        return parse_json_reply(raw_text)

    _ask = _chat

    # ---------- public API ----------

    def resolve_with_explanation(self, phrase: str) -> Optional[Resolution]:
        system = RESOLVE_PROMPT + distro_note(self.distro, self.family)
        return resolution_from_reply(self._chat(system, f"Request: {phrase}"))

    def resolve_command(self, phrase: str) -> Optional[str]:
        result = self.resolve_with_explanation(phrase)
        return result.command if result else None

    def explain_command(self, command: str) -> Optional[str]:
        system = EXPLAIN_PROMPT + distro_note(self.distro, self.family)
        data = self._chat(system, f"Command: {command}")
        explanation = data.get("explanation")
        if not explanation or not isinstance(explanation, str):
            return None
        return explanation.strip()
