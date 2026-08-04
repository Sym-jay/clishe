"""Tests for ClisheBrain's knowledge-base, logging, and prediction logic.
Run with: pytest tests/
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def brain(tmp_path, monkeypatch):
    """A ClisheBrain instance backed by a throwaway temp HOME, so tests never
    touch the real ~/.clishe_kb.json etc."""
    monkeypatch.setenv("HOME", str(tmp_path))
    import importlib
    import clishe_brain
    importlib.reload(clishe_brain)  # re-evaluate KB_FILE/DATA_FILE against new HOME
    return clishe_brain.ClisheBrain()


def test_query_miss_returns_empty_string(brain):
    assert brain.query("nonexistent phrase") == ""


def test_learn_then_query_roundtrip(brain):
    assert brain.learn("list files", "ls -la") is True
    assert brain.query("list files") == "ls -la"


def test_query_is_case_and_whitespace_insensitive(brain):
    brain.learn("list files", "ls -la")
    assert brain.query("  List Files  ") == "ls -la"


def test_learn_rejects_empty_phrase_or_command(brain):
    assert brain.learn("", "ls -la") is False
    assert brain.learn("list files", "") is False


def test_learn_persists_to_disk(brain, tmp_path):
    brain.learn("list files", "ls -la")
    kb_file = tmp_path / ".clishe_kb.json"
    assert kb_file.exists()
    with open(kb_file) as f:
        data = json.load(f)
    assert data["list files"] == "ls -la"


def test_corrupted_kb_file_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".clishe_kb.json").write_text("{not valid json")

    import importlib
    import clishe_brain
    importlib.reload(clishe_brain)
    brain = clishe_brain.ClisheBrain()
    assert brain.kb == {}  # falls back to empty instead of raising


def test_predict_needs_minimum_sequences(brain):
    # Only 2 sequences logged - below MIN_SEQUENCES_FOR_PREDICTION (3)
    brain.data["sequences"] = [["cd", "ls"], ["cd", "mkdir"]]
    assert brain.predict("cd") == ""


def test_predict_picks_most_frequent_follower(brain):
    brain.data["sequences"] = [
        ["cd", "ls", "mkdir"],
        ["cd", "ls", "ls"],
        ["cd", "ls", "mkdir"],
    ]
    # After "cd", "ls" always follows -> should predict "ls"
    assert brain.predict("cd") == "ls"
    # After "ls", "mkdir" appears twice vs "ls" once -> should predict "mkdir"
    assert brain.predict("ls") == "mkdir"


def test_predict_never_predicts_same_command(brain):
    brain.data["sequences"] = [
        ["ls", "ls"], ["ls", "ls"], ["ls", "ls"],
    ]
    # Only observed follower is itself, so there's nothing valid to predict
    assert brain.predict("ls") == ""


def test_log_flushes_current_into_sequences_at_threshold(brain):
    for i in range(10):
        brain.log(f"cmd{i}")
    assert brain.data["current"] == []
    assert len(brain.data["sequences"]) == 1
    assert len(brain.data["sequences"][0]) == 10
