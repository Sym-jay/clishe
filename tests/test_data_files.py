"""Checks on the bundled data files and project metadata, so a bad edit to a
JSON file or a forgotten version bump fails CI instead of a user's session."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clishe_brain import normalize_phrase  # noqa: E402

SEED = json.loads((ROOT / "seed_kb.json").read_text())

# Same rule as RE_PLACEHOLDER in clishe.sh.
PLACEHOLDER = re.compile(r"<([a-z]+( [a-z]+)*)>")

# Commands that hang waiting for input, or fail, when run with no arguments.
NEEDS_ARGUMENT = {"cat", "less", "head", "tail", "wc", "cp", "mv", "rm", "mkdir",
                  "touch", "chmod", "chown", "kill", "pkill", "wget", "diff", "grep"}


@pytest.mark.parametrize("phrase,command", SEED.items())
def test_seed_commands_are_complete(phrase, command):
    """A seed entry must be runnable as-is or use <placeholders>, never a
    bare 'cat' that hangs the session waiting on stdin."""
    words = command.split()
    assert not (len(words) == 1 and words[0] in NEEDS_ARGUMENT), (
        f"{phrase!r} -> {command!r} needs an argument; use a <placeholder>")
    # Anything left that looks like <...> is a placeholder clishe.sh won't
    # recognise (capitals, digits, punctuation), so it would run literally.
    leftover = re.search(r"<[^ ]", PLACEHOLDER.sub("", command))
    assert not leftover, (
        f"{command!r} has a malformed placeholder (use lowercase words, e.g. <file name>)")


@pytest.mark.parametrize("phrase", SEED)
def test_seed_phrases_are_normalized(phrase):
    assert normalize_phrase(phrase) == phrase


def test_error_patterns_are_well_formed():
    patterns = json.loads((ROOT / "error_patterns.json").read_text())
    for entry in patterns:
        assert entry["match"] and entry["hint"]


def test_command_dictionary_is_well_formed():
    dictionary = json.loads((ROOT / "command_dictionary.json").read_text())
    for name, entry in dictionary.items():
        assert entry.get("summary"), name
        assert isinstance(entry.get("flags", {}), dict), name


def test_version_matches_between_script_and_pyproject():
    script = (ROOT / "clishe.sh").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()
    script_version = re.search(r'^CLISHE_VERSION="([^"]+)"', script, re.M).group(1)
    project_version = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert script_version == project_version


def test_specific_error_patterns_come_before_generic_ones():
    # First match wins, so "permission denied (publickey)" must be checked
    # before plain "permission denied".
    matches = [e["match"] for e in json.loads((ROOT / "error_patterns.json").read_text())]
    assert matches.index("permission denied (publickey)") < matches.index("permission denied")


def test_output_guides_are_well_formed():
    for entry in json.loads((ROOT / "output_guides.json").read_text()):
        assert entry["command"] and entry["guide"]


def test_old_configs_get_the_local_provider(tmp_path, monkeypatch):
    import json as _json
    import config as cfg
    path = tmp_path / "config.json"
    path.write_text(_json.dumps({"provider_priority": ["ollama", "anthropic"]}))
    monkeypatch.setattr(cfg, "CONFIG_FILE", path)
    loaded = cfg.load_config()
    assert loaded["provider_priority"] == ["ollama", "local", "anthropic"]
    assert loaded["anthropic"]["enabled"] is False


def test_default_config_is_local_only():
    import config as cfg
    assert cfg.DEFAULT_CONFIG["anthropic"]["enabled"] is False
    assert cfg.DEFAULT_CONFIG["allow_remote_ai"] is False
