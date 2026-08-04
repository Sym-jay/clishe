"""
Ollama provider - talks to a locally running Ollama server (default
http://localhost:11434). No API key, no internet required, which matters a
lot for a "teach beginners the terminal" tool: it should work on a plane.
"""
import json
import urllib.request
import urllib.error
from typing import Optional

from .base import Provider, ProviderError

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
TIMEOUT_SECONDS = 30  # local models on modest hardware can be slow
AVAILABILITY_CHECK_TIMEOUT = 1.5  # keep the "is this even running" check snappy


RESOLVE_PROMPT_TEMPLATE = (
    "You translate a beginner's plain-English request into a single Linux "
    "shell command. Respond with ONLY raw JSON, no markdown fences, no "
    "commentary, in exactly this shape: "
    '{{"command": "<the shell command or null>", "explanation": "<one short sentence>"}}. '
    "Use null for command if the request is unclear, unsafe, or not a shell task.\n\n"
    "Request: {phrase}"
)

EXPLAIN_PROMPT_TEMPLATE = (
    "Explain this Linux shell command to a beginner in one or two short "
    "plain-English sentences. Respond with ONLY raw JSON: "
    '{{"explanation": "<text>"}}.\n\n'
    "Command: {command}"
)


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, config: dict):
        super().__init__(config)
        self.host = self.config.get("host", DEFAULT_HOST).rstrip("/")
        self.model = self.config.get("model", DEFAULT_MODEL)

    def is_available(self) -> bool:
        """Ping the server's tag list endpoint - fast, no model load needed."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=AVAILABILITY_CHECK_TIMEOUT):
                return True
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    # ---------- internal ----------

    def _generate(self, prompt: str) -> dict:
        payload = {
            "model": self.model,
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

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ProviderError(f"Could not parse Ollama response as JSON: {e}") from e

    # ---------- public API ----------

    def resolve_command(self, phrase: str) -> Optional[str]:
        data = self._generate(RESOLVE_PROMPT_TEMPLATE.format(phrase=phrase))
        command = data.get("command")
        if not command or not isinstance(command, str):
            return None
        return command.strip()

    def explain_command(self, command: str) -> Optional[str]:
        data = self._generate(EXPLAIN_PROMPT_TEMPLATE.format(command=command))
        explanation = data.get("explanation")
        if not explanation or not isinstance(explanation, str):
            return None
        return explanation.strip()
