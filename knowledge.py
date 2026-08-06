"""
Offline knowledge base - command explanations and error-message translations
that don't require any AI provider or network call. This is the free, instant
tier that AI resolution/explanation falls back to only when this misses.
"""
import json
import shlex
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent

_COMMAND_DICT_FILE = _DATA_DIR / "command_dictionary.json"
_ERROR_PATTERNS_FILE = _DATA_DIR / "error_patterns.json"


def _load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


_COMMAND_DICT = _load_json(_COMMAND_DICT_FILE, {})
_ERROR_PATTERNS = _load_json(_ERROR_PATTERNS_FILE, [])


def lookup_command(command_str: str):
    """Look up the base command (first word) in the offline dictionary.
    Returns the dict entry, or None if not found."""
    if not command_str or not command_str.strip():
        return None
    try:
        tokens = shlex.split(command_str)
    except ValueError:
        # Unbalanced quotes etc - fall back to naive split rather than crash
        tokens = command_str.split()
    if not tokens:
        return None
    base_command = tokens[0]
    return _COMMAND_DICT.get(base_command)


def format_explanation(entry: dict) -> str:
    """Turn a dictionary entry into a beginner-friendly explanation string."""
    parts = [entry.get("summary", "").strip()]

    flags = entry.get("flags") or {}
    if flags:
        flag_lines = [f"  {flag}  {desc}" for flag, desc in flags.items()]
        parts.append("Common flags:\n" + "\n".join(flag_lines))

    example = entry.get("example")
    if example:
        parts.append(f"Example: {example}")

    danger = entry.get("danger")
    if danger:
        parts.append(f"⚠ {danger}")

    return "\n".join(p for p in parts if p)


def diagnose_error(error_text: str):
    """Match stderr text against known error patterns. Returns a hint string,
    or None if nothing matched."""
    if not error_text:
        return None
    lowered = error_text.lower()
    for entry in _ERROR_PATTERNS:
        if entry.get("match", "").lower() in lowered:
            return entry.get("hint")
    return None
