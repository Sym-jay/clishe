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
    # Falls back to a naive split on unbalanced quotes rather than crashing.
    tokens = _split_args(command_str)
    # "sudo apt install x" should explain apt, not sudo.
    while len(tokens) > 1 and tokens[0] == "sudo":
        tokens = tokens[1:]
    if not tokens:
        return None
    base_command = tokens[0]
    return _COMMAND_DICT.get(base_command)


def _split_args(command_str: str):
    try:
        return shlex.split(command_str)
    except ValueError:
        return command_str.split()


def _base_name(command_str: str) -> str:
    tokens = [t for t in _split_args(command_str) if t != "sudo"]
    return tokens[0] if tokens else ""


def explain_flags(command_str: str, entry: dict):
    """Match the flags/subcommands actually used in `command_str` against the
    entry's notes. Combined short flags are split, so 'tar -xzvf' explains
    -x, -z, -v and -f one by one.

    Returns (known, unknown): known is a list of (flag, description), unknown
    is a list of dash-flags that aren't in the dictionary."""
    flags = entry.get("flags") or {}
    tokens = _split_args(command_str)
    while len(tokens) > 1 and tokens[0] == "sudo":
        tokens = tokens[1:]
    tokens = tokens[1:]
    known, unknown = [], []

    def add(flag):
        if flag in flags:
            if all(flag != k for k, _ in known):
                known.append((flag, flags[flag]))
            return True
        return False

    for i, tok in enumerate(tokens):
        if tok in ("-", "--") or (tok.startswith("-") and tok[1:].isdigit()):
            continue
        if add(tok) or add(tok.split("=", 1)[0]):
            continue
        if tok.startswith("--"):
            unknown.append(tok.split("=", 1)[0])
        elif tok.startswith("-") and len(tok) > 2:
            for letter in tok[1:]:
                if not add(f"-{letter}"):
                    unknown.append(f"-{letter}")
        elif tok.startswith("-"):
            unknown.append(tok)
        elif i == 0 and tok.isalpha() and all(f"-{c}" in flags for c in tok):
            # Old-style bundled flags without a dash: "tar xzvf file.tgz"
            for letter in tok:
                add(f"-{letter}")
    return known, unknown


def format_explanation(entry: dict, command: str = "") -> str:
    """Turn a dictionary entry into a beginner-friendly explanation string.
    If `command` is given and uses flags, explain those specific flags
    instead of listing the common ones."""
    parts = [entry.get("summary", "").strip()]

    flags = entry.get("flags") or {}
    known, unknown = explain_flags(command, entry) if command else ([], [])
    if known or unknown:
        lines = [f"  {flag}  {desc}" for flag, desc in known]
        lines += [f"  {flag}  (not in my offline notes - try: man {_base_name(command)})"
                  for flag in unknown]
        parts.append(f"In '{command.strip()}':\n" + "\n".join(lines))
    elif flags:
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
