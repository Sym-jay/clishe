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
    import clishe_brain
    brain.learn("list files", "ls -la")
    assert clishe_brain.KB_FILE.exists()
    with open(clishe_brain.KB_FILE) as f:
        saved = json.load(f)
    assert saved["list files"] == "ls -la"


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


# ---------- explain() offline-dictionary integration ----------

def test_explain_uses_offline_dictionary_for_known_command(brain):
    result = brain.explain("chmod 755 script.sh")
    assert result["status"] == "ok"
    assert result["provider"] == "offline dictionary"
    assert "permission" in result["explanation"].lower()


def test_explain_falls_through_to_unavailable_for_unknown_command_with_no_providers(brain):
    result = brain.explain("some-made-up-tool --flag")
    assert result["status"] == "unavailable"


# ---------- diagnose() ----------

def test_diagnose_matches_known_error(brain):
    result = brain.diagnose("Permission denied")
    assert result["status"] == "ok"
    assert "hint" in result


def test_diagnose_unmatched_error(brain):
    result = brain.diagnose("a totally novel error nobody has documented")
    assert result["status"] == "unmatched"


# ---------- phrase normalization ----------

@pytest.mark.parametrize("raw,expected", [
    ("  Show Me Disk Usage??  ", "show me disk usage"),
    ("please show me disk usage", "show me disk usage"),
    ("hey, can you list files please", "list files"),
    ("what’s my ip", "what's my ip"),
    ("list   files.", "list files"),
])
def test_normalize_phrase(raw, expected):
    import clishe_brain
    assert clishe_brain.normalize_phrase(raw) == expected


def test_query_ignores_punctuation_and_filler(brain):
    brain.learn("deploy my site", "./deploy.sh")
    assert brain.query("Please deploy my site!") == "./deploy.sh"


def test_old_unnormalized_kb_keys_still_match(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    kb_dir = tmp_path / ".local" / "share" / "clishe"
    kb_dir.mkdir(parents=True)
    (kb_dir / "kb.json").write_text(json.dumps({"Deploy My Site?": "./deploy.sh"}))
    import importlib
    import clishe_brain
    importlib.reload(clishe_brain)
    assert clishe_brain.ClisheBrain().query("deploy my site") == "./deploy.sh"


# ---------- fuzzy suggestions ----------

def test_suggest_finds_near_miss_in_seed_kb(brain):
    assert brain.suggest("show disk usage") == ("show me disk usage", "df -h")


def test_suggest_prefers_users_own_phrases(brain):
    brain.learn("show me disk usage", "duf")
    assert brain.suggest("show disk usage") == ("show me disk usage", "duf")


def test_suggest_returns_none_for_unrelated_phrase(brain):
    assert brain.suggest("book a flight to paris") is None


def test_suggest_returns_none_for_exact_match(brain):
    # Exact matches are query()'s job; suggest is only for near misses.
    assert brain.suggest("show me disk usage") is None


# ---------- forget / learned ----------

def test_forget_removes_taught_phrase(brain):
    brain.learn("deploy", "./deploy.sh")
    assert brain.forget("Deploy") is True
    assert brain.query("deploy") == ""


def test_forget_unknown_phrase(brain):
    assert brain.forget("never taught") is False


def test_teaching_a_seed_phrase_overrides_it(brain):
    brain.learn("list files", "ls -1")
    assert brain.query("list files") == "ls -1"
    brain.forget("list files")
    assert brain.query("list files") == "ls -la"  # seed value is back


def test_learned_lists_only_user_phrases(brain):
    brain.learn("b phrase", "cmd-b")
    brain.learn("a phrase", "cmd-a")
    assert brain.learned() == [("a phrase", "cmd-a"), ("b phrase", "cmd-b")]


# ---------- storage hygiene ----------

def test_saved_files_are_private(brain):
    import clishe_brain
    brain.learn("list files", "ls -la")
    brain.log("ls")
    assert (clishe_brain.KB_FILE.stat().st_mode & 0o777) == 0o600
    assert (clishe_brain.DATA_FILE.stat().st_mode & 0o777) == 0o600


def test_history_is_capped(brain):
    import clishe_brain
    brain.data["sequences"] = [["a", "b"]] * (clishe_brain.MAX_SEQUENCES + 50)
    brain.data["current"] = ["x"] * (clishe_brain.SEQUENCE_FLUSH_LENGTH - 1)
    brain.log("newest")  # fills "current", which flushes and trims
    assert len(brain.data["sequences"]) == clishe_brain.MAX_SEQUENCES
    assert brain.data["sequences"][-1][-1] == "newest"


# ---------- resolve() keeps the model's explanation ----------

def test_resolve_returns_command_and_explanation(brain, monkeypatch):
    import clishe_brain
    from providers.base import Resolution

    class Fake:
        name = "fake"

        def resolve_with_explanation(self, phrase):
            return Resolution("df -h", "Shows free disk space.")

    monkeypatch.setattr(clishe_brain, "build_provider_chain", lambda config: [Fake()])
    result = brain.resolve("disk space")
    assert result == {"status": "ok", "command": "df -h",
                      "explanation": "Shows free disk space.", "provider": "fake"}


def test_resolve_falls_through_failing_provider(brain, monkeypatch):
    import clishe_brain
    from providers import ProviderError
    from providers.base import Resolution

    class Broken:
        name = "broken"

        def resolve_with_explanation(self, phrase):
            raise ProviderError("down")

    class Works:
        name = "works"

        def resolve_with_explanation(self, phrase):
            return Resolution("uptime")

    monkeypatch.setattr(clishe_brain, "build_provider_chain", lambda c: [Broken(), Works()])
    assert brain.resolve("how long up")["provider"] == "works"


def test_check_action(brain):
    assert brain.check("ls")["status"] == "safe"
    result = brain.check("rm -rf build")
    assert result["status"] == "danger" and result["reasons"]


def test_one_line_output_keeps_what_runs_visible():
    import clishe_brain
    assert clishe_brain._one_line("cd /tmp\nls") == "cd /tmp; ls"
    assert clishe_brain._encoded("a\nb") == "a\\nb"
