"""Tests for knowledge.py - the offline command dictionary and error-pattern
matcher. No network, no providers, no AI - these should be fast and free."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge import lookup_command, format_explanation, diagnose_error


# ---------- lookup_command ----------

def test_lookup_known_command():
    entry = lookup_command("ls -la")
    assert entry is not None
    assert "summary" in entry


def test_lookup_uses_first_word_only():
    entry = lookup_command("chmod 755 script.sh")
    assert entry is not None
    assert "permission" in entry["summary"].lower()


def test_lookup_unknown_command_returns_none():
    assert lookup_command("some-made-up-tool --flag") is None


def test_lookup_empty_string_returns_none():
    assert lookup_command("") is None
    assert lookup_command("   ") is None


def test_lookup_handles_unbalanced_quotes_without_crashing():
    # shlex.split raises ValueError on unbalanced quotes - make sure we
    # degrade gracefully instead of propagating the exception.
    result = lookup_command('echo "unterminated')
    assert result is None or isinstance(result, dict)


# ---------- format_explanation ----------

def test_format_explanation_includes_summary():
    entry = {"summary": "Does a thing.", "flags": {}, "example": None}
    text = format_explanation(entry)
    assert "Does a thing." in text


def test_format_explanation_includes_danger_warning():
    entry = {"summary": "Deletes stuff.", "danger": "Be careful!"}
    text = format_explanation(entry)
    assert "Be careful!" in text
    assert "⚠" in text


def test_format_explanation_includes_flags():
    entry = {"summary": "Lists things.", "flags": {"-l": "long format"}}
    text = format_explanation(entry)
    assert "-l" in text
    assert "long format" in text


# ---------- diagnose_error ----------

def test_diagnose_permission_denied():
    hint = diagnose_error("bash: ./script.sh: Permission denied")
    assert hint is not None
    assert "permission" in hint.lower()


def test_diagnose_no_such_file():
    hint = diagnose_error("cat: missing.txt: No such file or directory")
    assert hint is not None


def test_diagnose_is_case_insensitive():
    hint_lower = diagnose_error("permission denied")
    hint_upper = diagnose_error("PERMISSION DENIED")
    assert hint_lower is not None
    assert hint_lower == hint_upper


def test_diagnose_unmatched_error_returns_none():
    assert diagnose_error("a completely novel error string xyz123") is None


def test_diagnose_empty_string_returns_none():
    assert diagnose_error("") is None
    assert diagnose_error(None) is None
