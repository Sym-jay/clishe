"""Tests for the provider abstraction: registry, chain building, and the
Anthropic provider's request/response handling (mocked - no real network
calls or API keys needed)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers import build_provider_chain, ProviderError
from providers.base import Provider
from providers.anthropic_provider import AnthropicProvider
from providers.ollama_provider import OllamaProvider


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _anthropic_body(text: str) -> bytes:
    return json.dumps({"content": [{"type": "text", "text": text}]}).encode()


# ---------- registry / chain ----------

def test_chain_skips_unavailable_providers():
    config = {
        "provider_priority": ["ollama", "anthropic"],
        "ollama": {"host": "http://localhost:1"},  # nothing listening there
        "anthropic": {"api_key": ""},  # no key
    }
    chain = build_provider_chain(config)
    assert chain == []


def test_chain_includes_available_providers_in_priority_order():
    config = {
        "provider_priority": ["anthropic"],
        "anthropic": {"api_key": "fake-key"},
    }
    chain = build_provider_chain(config)
    assert len(chain) == 1
    assert chain[0].name == "anthropic"


def test_chain_ignores_unknown_provider_names():
    config = {"provider_priority": ["not_a_real_provider"]}
    assert build_provider_chain(config) == []


# ---------- Anthropic provider ----------

def test_anthropic_is_available_requires_key():
    assert AnthropicProvider({"api_key": "sk-x"}).is_available() is True
    assert AnthropicProvider({}).is_available() is False


def test_anthropic_resolve_command_success():
    provider = AnthropicProvider({"api_key": "sk-x"})
    body = _anthropic_body('{"command": "df -h", "explanation": "disk usage"}')
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        assert provider.resolve_command("show disk usage") == "df -h"


def test_anthropic_resolve_command_decline_returns_none():
    provider = AnthropicProvider({"api_key": "sk-x"})
    body = _anthropic_body('{"command": null, "explanation": "too risky"}')
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        assert provider.resolve_command("wipe everything") is None


def test_anthropic_handles_markdown_fenced_json():
    provider = AnthropicProvider({"api_key": "sk-x"})
    body = _anthropic_body('```json\n{"command": "ls -la", "explanation": "list"}\n```')
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        assert provider.resolve_command("list files") == "ls -la"


def test_anthropic_malformed_response_raises_provider_error():
    provider = AnthropicProvider({"api_key": "sk-x"})
    body = _anthropic_body("this is not json")
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        with pytest.raises(ProviderError):
            provider.resolve_command("anything")


def test_anthropic_explain_command_success():
    provider = AnthropicProvider({"api_key": "sk-x"})
    body = _anthropic_body('{"explanation": "Lists files including hidden ones."}')
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        result = provider.explain_command("ls -la")
        assert result == "Lists files including hidden ones."


# ---------- Ollama provider ----------

def test_ollama_is_available_false_when_unreachable():
    provider = OllamaProvider({"host": "http://localhost:1"})
    assert provider.is_available() is False


def test_ollama_resolve_command_success():
    provider = OllamaProvider({"host": "http://localhost:11434"})
    body = json.dumps({
        "response": json.dumps({"command": "df -h", "explanation": "disk usage"})
    }).encode()
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        assert provider.resolve_command("show disk usage") == "df -h"


def test_ollama_empty_response_raises_provider_error():
    provider = OllamaProvider({"host": "http://localhost:11434"})
    body = json.dumps({"response": ""}).encode()
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        with pytest.raises(ProviderError):
            provider.resolve_command("anything")


# ---------- Provider interface contract ----------

def test_provider_is_abstract():
    with pytest.raises(TypeError):
        Provider({})  # can't instantiate the ABC directly


# ---------- explanations and JSON tolerance ----------

from providers.base import Resolution, parse_json_reply


def test_anthropic_resolve_with_explanation():
    provider = AnthropicProvider({"api_key": "sk-x"})
    body = _anthropic_body('{"command": "df -h", "explanation": "Shows disk space."}')
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        assert provider.resolve_with_explanation("disk") == Resolution("df -h", "Shows disk space.")


def test_ollama_tolerates_chatter_around_json():
    provider = OllamaProvider({"host": "http://localhost:11434"})
    body = json.dumps({
        "response": 'Sure! Here you go: {"command": "uptime", "explanation": "How long it has run."} Hope that helps'
    }).encode()
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        assert provider.resolve_with_explanation("up") == Resolution("uptime", "How long it has run.")


@pytest.mark.parametrize("text", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    '```\n{"a": 1}\n```',
    'Here: {"a": 1}',
])
def test_parse_json_reply_variants(text):
    assert parse_json_reply(text) == {"a": 1}


def test_parse_json_reply_rejects_non_objects():
    with pytest.raises(ProviderError):
        parse_json_reply("[1, 2]")
    with pytest.raises(ProviderError):
        parse_json_reply("no json here")


def test_distro_is_added_to_prompt():
    provider = AnthropicProvider({"api_key": "sk-x", "distro": "fedora"})
    captured = {}

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data)
        return _FakeResp(_anthropic_body('{"command": "sudo dnf install htop"}'))

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider.resolve_command("install htop")
    assert "fedora" in captured["payload"]["system"]


def test_third_party_provider_gets_default_resolve_with_explanation():
    class Minimal(Provider):
        name = "minimal"

        def is_available(self):
            return True

        def resolve_command(self, phrase):
            return "ls"

        def explain_command(self, command):
            return None

    assert Minimal({}).resolve_with_explanation("x") == Resolution("ls", "")
