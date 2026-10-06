"""
Anthropic provider - calls the Claude Messages API.

This is the one provider that sends your phrases over the internet, so it is
off unless you turn it on: "anthropic": {"enabled": true} in the config.

Uses urllib from the standard library only, so clishe doesn't force users to
pip install an SDK just to get cloud fallback working.
"""
import json
import os
import urllib.request
import urllib.error
from typing import Optional

from .base import (EXPLAIN_PROMPT, RESOLVE_PROMPT, Provider, ProviderError,
                   Resolution, distro_note, parse_json_reply, resolution_from_reply)

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # fast + cheap, good fit for this task
TIMEOUT_SECONDS = 15


class AnthropicProvider(Provider):
    name = "anthropic"
    local = False

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = self.config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = self.config.get("model", DEFAULT_MODEL)
        self.distro = self.config.get("distro", "unknown")
        self.family = self.config.get("distro_family", [])

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

        return parse_json_reply(raw_text)

    _ask = _call

    # ---------- public API ----------

    def resolve_with_explanation(self, phrase: str) -> Optional[Resolution]:
        data = self._call(RESOLVE_PROMPT + distro_note(self.distro, self.family), phrase)
        return resolution_from_reply(data)

    def resolve_command(self, phrase: str) -> Optional[str]:
        result = self.resolve_with_explanation(phrase)
        return result.command if result else None

    def explain_command(self, command: str) -> Optional[str]:
        data = self._call(EXPLAIN_PROMPT + distro_note(self.distro, self.family), command)
        explanation = data.get("explanation")
        if not explanation or not isinstance(explanation, str):
            return None
        return explanation.strip()
