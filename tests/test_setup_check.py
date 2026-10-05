"""Tests for setup_check.py - `clishe setup`. Nothing here talks to a real
model server."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import setup_check  # noqa: E402


@pytest.mark.parametrize("ram,model", [
    (2, "llama3.2:1b"),
    (7.6, "llama3.2:1b"),
    (8, "llama3.2"),
    (15.5, "llama3.2"),
    (32, "qwen2.5-coder:7b"),
    (None, "llama3.2"),
])
def test_recommend_fits_memory(ram, model):
    assert setup_check.recommend(ram)[0] == model


def test_has_model_understands_latest_tag():
    assert setup_check._has_model(["llama3.2:latest"], "llama3.2")
    assert setup_check._has_model(["llama3.2:1b"], "llama3.2:1b")
    assert not setup_check._has_model(["llama3.2:1b"], "llama3.2")


def _result(**changes):
    result = {"ram_gb": 8.0, "model": "llama3.2", "model_description": "3B",
              "ollama_installed": False, "ollama_running": False, "ollama_models": [],
              "model_ready": False, "configured_model": "llama3.2",
              "other_servers": [], "cloud_on": False}
    result.update(changes)
    return "\n".join(setup_check.report(result))


def test_report_without_ollama_points_to_the_download():
    text = _result()
    assert "https://ollama.com/download" in text
    assert "ollama pull llama3.2" in text
    assert "Local only" in text


def test_report_with_ollama_running():
    text = _result(ollama_installed=True, ollama_running=True,
                   ollama_models=["llama3.2:latest"], model_ready=True)
    assert "Ollama is running. Models downloaded: llama3.2:latest" in text
    assert "ollama pull" not in text


def test_report_mentions_other_local_servers_and_cloud():
    text = _result(other_servers=["http://localhost:1234"], cloud_on=True)
    assert "http://localhost:1234" in text
    assert "cloud provider (Anthropic) is turned on" in text


def test_set_ollama_model_keeps_the_rest_of_the_config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"trash": "never", "ollama": {"host": "http://localhost:11434"}}))
    monkeypatch.setattr(setup_check, "CONFIG_FILE", path)
    monkeypatch.setattr(setup_check, "load_config", lambda: {})
    assert setup_check.set_ollama_model("llama3.2:1b") is True
    saved = json.loads(path.read_text())
    assert saved == {"trash": "never",
                     "ollama": {"host": "http://localhost:11434", "model": "llama3.2:1b"}}
    assert (path.stat().st_mode & 0o777) == 0o600
