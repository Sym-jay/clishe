"""
Config loading for clishe's AI providers.

Reads ~/.clishe_config.json. If it doesn't exist, writes a commented-out
template so first-run users see exactly what to fill in instead of hitting
a wall of "provider not configured" errors with no next step.

Also detects the running Linux distro from /etc/os-release so AI providers
can give distro-correct package-manager commands (apt vs dnf vs pacman)
instead of defaulting to one distro for everyone.
"""
import json
import os
from pathlib import Path

XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_DIR = XDG_CONFIG_HOME / "clishe"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"
OS_RELEASE_FILE = Path('/etc/os-release')

def _migrate_legacy_file(old_name: str, new_path: Path):
    """One-time migration from the old ~/.clishe_* locations to the new
    XDG-compliant paths, so upgrading doesn't silently lose existing data."""
    old_path = Path.home() / old_name
    if old_path.exists() and not new_path.exists():
        try:
            old_path.rename(new_path)
        except OSError:
            pass

_migrate_legacy_file(".clishe_kb.json", KB_FILE)
_migrate_legacy_file(".clishe_data.json", DATA_FILE)

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


def detect_distro() -> str:
    """Read the ID field from /etc/os-release (e.g. 'ubuntu', 'fedora',
    'arch', 'debian'). Returns 'unknown' if the file is missing or
    unparseable (e.g. non-Linux systems), so callers never need to
    special-case a missing value."""
    if not OS_RELEASE_FILE.exists():
        return "unknown"
    try:
        with open(OS_RELEASE_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ID='):
                    value = line.split('=', 1)[1].strip()
                    return value.strip('"').lower()
    except OSError:
        pass
    return "unknown"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        _write_default_config()
        config = dict(DEFAULT_CONFIG)
    else:
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
            # Merge shallowly over defaults so a partial user config still works.
            config = dict(DEFAULT_CONFIG)
            config.update(user_config)
        except (json.JSONDecodeError, OSError):
            # Corrupted config shouldn't take down the whole tool - fall back to
            # KB-only behavior (empty priority list means no providers get built).
            config = {"provider_priority": []}

    # Always computed live, never persisted to disk - the distro can't
    # change without a fresh install anyway, and this keeps it accurate
    # without a stale cached value surviving an OS upgrade.
    config["distro"] = detect_distro()
    return config


def _write_default_config():
    """Create the config file with owner-only read/write permissions (0600).

    This file may eventually hold a plaintext Anthropic API key, so it
    should never be created with default (often world-readable) permissions
    on shared or multi-user systems. os.O_EXCL also means this safely does
    nothing if another process created the file between our exists() check
    and this call, instead of clobbering it.
    """
    try:
        fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    except OSError:
        pass
