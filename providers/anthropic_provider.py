"""
Anthropic provider - calls the Claude Messages API.

Uses urllib from the standard library only, so clishe doesn't force users to
pip install an SDK just to get cloud fallback working.
"""
import json
import urllib.request
import urllib.error
from typing import Optional

from .base import Provider, ProviderError

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # fast + cheap, good fit for this task
TIMEOUT_SECONDS = 15


RESOLVE_SYSTEM_PROMPT = (
    "You translate a beginner's plain-English request into a single Linux "
    "shell command. Reply with ONLY a JSON object, no markdown fences, no "
    "extra text, in this exact shape: "
    '{"command": "<the shell command>", "explanation": "<one short sentence>"}. '
    "If the request is unclear, unsafe (e.g. would delete/overwrite data, "
    "modify permissions recursively, or affect the whole system), or isn't "
    "really a shell task, reply with "
    '{"command": null, "explanation": "<why, in one short sentence>"}. '
    "Never include an explanation of the JSON format itself, only the values."
)

EXPLAIN_SYSTEM_PROMPT = (
    "You explain Linux shell commands to a beginner in one or two short, "
    "plain-English sentences. Reply with ONLY a JSON object, no markdown "
    'fences: {"explanation": "<text>"}. Be concrete about what the command '
    "does and flag anything destructive or irreversible."
)


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", DEFAULT_MODEL)

    def is_available(self) -> bool:
        return bool(self.api_key)

    # ---------- internal ----------

    def _call(self, system_prompt: str, user_content: str) -> dict:
        payload = {
            "model": self.model,
            "max_tokens": 300,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        }
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": API_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Anthropic API HTTP {e.code}: {detail[:200]}") from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Anthropic API unreachable: {e.reason}") from e
        except (TimeoutError, OSError) as e:
            raise ProviderError(f"Anthropic API timeout/network error: {e}") from e

        try:
            text_blocks = [b["text"] for b in body["content"] if b.get("type") == "text"]
            raw_text = "".join(text_blocks).strip()
        except (KeyError, TypeError) as e:
            raise ProviderError(f"Unexpected Anthropic response shape: {e}") from e

        # Be tolerant of the model wrapping JSON in a code fence anyway.
        cleaned = raw_text.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ProviderError(f"Could not parse Anthropic response as JSON: {e}") from e

    # ---------- public API ----------

    def resolve_command(self, phrase: str) -> Optional[str]:
        data = self._call(RESOLVE_SYSTEM_PROMPT, phrase)
        command = data.get("command")
        if not command or not isinstance(command, str):
            return None
        return command.strip()

    def explain_command(self, command: str) -> Optional[str]:
        data = self._call(EXPLAIN_SYSTEM_PROMPT, command)
        explanation = data.get("explanation")
        if not explanation or not isinstance(explanation, str):
            return None
        return explanation.strip()
