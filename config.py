"""
Config loading for clishe's AI providers.

Reads ~/.clishe_config.json. If it doesn't exist, writes a commented-out
template so first-run users see exactly what to fill in instead of hitting
a wall of "provider not configured" errors with no next step.
"""
import json
from pathlib import Path

CONFIG_FILE = Path.home() / '.clishe_config.json'

DEFAULT_CONFIG = {
    "provider_priority": ["ollama", "anthropic"],
    "ollama": {
        "host": "http://localhost:11434",
        "model": "llama3.2"
    },
    "anthropic": {
        "api_key": "",
        "model": "claude-haiku-4-5-20251001"
    }
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        _write_default_config()
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, 'r') as f:
            user_config = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrupted config shouldn't take down the whole tool - fall back to
        # KB-only behavior (empty priority list means no providers get built).
        return {"provider_priority": []}

    # Merge shallowly over defaults so a partial user config still works.
    merged = dict(DEFAULT_CONFIG)
    merged.update(user_config)
    return merged


def _write_default_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    except OSError:
        pass
