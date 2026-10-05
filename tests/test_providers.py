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


# ---------- local first ----------

from providers import opted_in
from providers.base import distro_note, is_local_address
from providers.local_provider import LocalProvider


def test_cloud_provider_is_off_unless_enabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-another-tool")
    config = {"provider_priority": ["anthropic"], "anthropic": {"enabled": False}}
    assert build_provider_chain(config) == []
    # A key in the environment alone is not an opt-in.
    config = {"provider_priority": ["anthropic"], "anthropic": {}}
    assert build_provider_chain(config) == []


def test_cloud_provider_runs_once_enabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    config = {"provider_priority": ["anthropic"], "anthropic": {"enabled": True}}
    assert [p.name for p in build_provider_chain(config)] == ["anthropic"]


@pytest.mark.parametrize("block,expected", [
    ({}, False),
    ({"api_key": ""}, False),
    ({"api_key": "sk-x"}, True),            # older configs: a typed-in key
    ({"api_key": "sk-x", "enabled": False}, False),
    ({"enabled": True}, True),
])
def test_opted_in(block, expected):
    assert opted_in(block) is expected


@pytest.mark.parametrize("url,expected", [
    ("http://localhost:11434", True),
    ("http://127.0.0.1:8080", True),
    ("http://[::1]:8080", True),
    ("http://192.168.1.20:11434", True),     # a home server
    ("http://10.0.0.5:1234", True),
    ("http://mybox.local:11434", True),
    ("http://8.8.8.8:11434", False),
    ("https://api.example.com", False),
    ("", False),
])
def test_is_local_address(url, expected, monkeypatch):
    import socket
    def fake_getaddrinfo(host, port):
        if host == "api.example.com":
            return [(None, None, None, "", ("93.184.216.34", 0))]
        raise OSError("no DNS in tests")
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    assert is_local_address(url) is expected


def test_remote_ollama_host_is_refused(capsys):
    config = {"provider_priority": ["ollama"], "ollama": {"host": "http://8.8.8.8:11434"}}
    with patch("urllib.request.urlopen") as urlopen:
        assert build_provider_chain(config) == []
        urlopen.assert_not_called()  # nothing is sent, not even a ping
    assert "allow_remote_ai" in capsys.readouterr().err


def test_remote_host_allowed_when_user_says_so():
    config = {"provider_priority": ["ollama"], "allow_remote_ai": True,
              "ollama": {"host": "http://8.8.8.8:11434"}}
    with patch("urllib.request.urlopen", return_value=_FakeResp(b"{}")):
        assert [p.name for p in build_provider_chain(config)] == ["ollama"]


def test_distro_family_names_the_package_manager():
    note = distro_note("linuxmint", ["linuxmint", "ubuntu", "debian"])
    assert "based on ubuntu, debian" in note
    assert "apt" in note
    assert "dnf" in distro_note("fedora", ["fedora"])
    assert distro_note("unknown") == ""


def test_ollama_sends_safety_rules_and_distro_as_system_prompt():
    provider = OllamaProvider({"distro": "pop", "distro_family": ["pop", "ubuntu", "debian"]})
    captured = {}

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data)
        return _FakeResp(json.dumps({"response": '{"command": "sudo apt install htop"}'}).encode())

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider.resolve_command("install htop")
    assert "unsafe" in captured["payload"]["system"]
    assert "apt" in captured["payload"]["system"]
    assert captured["payload"]["prompt"] == "Request: install htop"


# ---------- OpenAI-style local servers (llama.cpp, LM Studio, Jan...) ----------

def _chat_body(text: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode()


def test_local_provider_finds_a_server_and_its_model():
    provider = LocalProvider({})
    tried = []

    def fake_urlopen(req, timeout):
        tried.append(req.full_url)
        if ":1234" not in req.full_url:
            raise urllib.error.URLError("connection refused")
        return _FakeResp(json.dumps({"data": [{"id": "qwen2.5-3b-instruct"}]}).encode())

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert provider.is_available() is True
    assert provider.host == "http://localhost:1234"
    assert provider.model == "qwen2.5-3b-instruct"
    assert tried[0] == "http://localhost:8080/v1/models"


def test_local_provider_unavailable_when_nothing_listens():
    provider = LocalProvider({"host": "http://localhost:1"})
    assert provider.is_available() is False


def test_local_provider_resolve():
    provider = LocalProvider({"host": "http://localhost:8080", "model": "m"})
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data)
        return _FakeResp(_chat_body('Sure: {"command": "du -sh *", "explanation": "Folder sizes."}'))

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert provider.resolve_with_explanation("folder sizes") == Resolution("du -sh *", "Folder sizes.")
    assert captured["url"] == "http://localhost:8080/v1/chat/completions"
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["model"] == "m"


def test_local_provider_bad_response_raises_provider_error():
    provider = LocalProvider({"host": "http://localhost:8080"})
    with patch("urllib.request.urlopen", return_value=_FakeResp(b'{"oops": 1}')):
        with pytest.raises(ProviderError):
            provider.resolve_command("anything")


import urllib.error  # noqa: E402  (used by the fakes above)
