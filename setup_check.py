"""
`clishe setup`: look at this computer and say how to get a local AI model
running for Clishe - which servers are already here, which model fits the
memory, and the exact command to get it. Everything it checks is local.
"""
import json
import os
import shutil
import urllib.request
import urllib.error
from typing import List, Optional

from config import CONFIG_FILE, load_config

OLLAMA_HOST = "http://localhost:11434"

# (minimum RAM in GB, Ollama model, what it is). Small instruct models are
# enough to turn a phrase into one command; bigger ones are better at it.
MODEL_SIZES = [
    (16, "qwen2.5-coder:7b", "7B, good with shell commands, about 5 GB"),
    (8, "llama3.2", "3B, a good balance, about 2 GB"),
    (0, "llama3.2:1b", "1B, small and quick, about 1.3 GB"),
]


def memory_gb() -> Optional[float]:
    """Total RAM, from /proc/meminfo (Linux). None if unknown."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 / 1024
    except (OSError, ValueError, IndexError):
        pass
    try:  # macOS and the BSDs, so the check also works there
        pages, size = os.sysconf("SC_PHYS_PAGES"), os.sysconf("SC_PAGE_SIZE")
        return pages * size / 1024 ** 3
    except (ValueError, OSError, AttributeError):
        return None


def recommend(ram_gb: Optional[float]):
    """(model, description) that fits this much memory."""
    if ram_gb is None:
        return MODEL_SIZES[1][1:]
    for minimum, model, description in MODEL_SIZES:
        if ram_gb >= minimum:
            return model, description
    return MODEL_SIZES[-1][1:]


def _get_json(url: str, timeout: float = 1.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def ollama_models() -> Optional[List[str]]:
    """Models Ollama has downloaded, or None if Ollama isn't running."""
    body = _get_json(f"{OLLAMA_HOST}/api/tags")
    if body is None:
        return None
    return [m.get("name", "") for m in body.get("models", []) if isinstance(m, dict)]


def other_local_servers() -> List[str]:
    """OpenAI-style servers (llama.cpp, LM Studio, Jan...) answering on the
    usual ports."""
    from providers.local_provider import DEFAULT_HOSTS
    return [h for h in DEFAULT_HOSTS if _get_json(f"{h}/v1/models") is not None]


def _has_model(models: List[str], model: str) -> bool:
    """'llama3.2' is stored as 'llama3.2:latest'."""
    want = model if ":" in model else f"{model}:latest"
    return any(m == model or m == want for m in models)


def check() -> dict:
    config = load_config()
    ram = memory_gb()
    model, description = recommend(ram)
    models = ollama_models()
    from providers import opted_in
    return {
        "ram_gb": ram,
        "model": model,
        "model_description": description,
        "ollama_installed": bool(shutil.which("ollama")),
        "ollama_running": models is not None,
        "ollama_models": models or [],
        "model_ready": models is not None and _has_model(models, model),
        "configured_model": config.get("ollama", {}).get("model", ""),
        "other_servers": other_local_servers(),
        "cloud_on": opted_in(config.get("anthropic", {})
                             if isinstance(config.get("anthropic"), dict) else {}),
    }


def report(result: dict) -> List[str]:
    """The setup check as lines of plain English."""
    lines = []
    ram = result["ram_gb"]
    lines.append(f"Memory: {ram:.0f} GB" if ram else "Memory: couldn't tell")
    lines.append(f"A model that fits: {result['model']} ({result['model_description']})")
    lines.append("")

    if result["ollama_running"]:
        have = ", ".join(result["ollama_models"]) or "none yet"
        lines.append(f"✓ Ollama is running. Models downloaded: {have}")
        if not result["model_ready"]:
            lines.append(f"  Get the suggested model with: ollama pull {result['model']}")
    elif result["ollama_installed"]:
        lines.append("• Ollama is installed but not running. Start it with: ollama serve")
        lines.append(f"  Then get a model with: ollama pull {result['model']}")
    else:
        lines.append("• Ollama isn't installed. It's the easiest way to run a model "
                     "locally: https://ollama.com/download")
        lines.append(f"  Then get a model with: ollama pull {result['model']}")

    for host in result["other_servers"]:
        lines.append(f"✓ A local model server is answering at {host} "
                     "(llama.cpp, LM Studio, Jan or similar). Clishe will use it too.")

    lines.append("")
    if result["cloud_on"]:
        lines.append("⚠ The cloud provider (Anthropic) is turned on, so phrases your local "
                     "model can't answer may be sent over the internet. Turn it off with "
                     '"enabled": false under "anthropic" in ' + str(CONFIG_FILE))
    else:
        lines.append("✓ Local only: nothing you type is sent to the internet.")
    return lines


def set_ollama_model(model: str) -> bool:
    """Save the Ollama model in the config, keeping everything else."""
    load_config()  # creates the file with defaults if it doesn't exist yet
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(config, dict):
        return False
    block = config.get("ollama") if isinstance(config.get("ollama"), dict) else {}
    block["model"] = model
    config["ollama"] = block
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(config, f, indent=2)
        tmp.replace(CONFIG_FILE)
    except OSError:
        return False
    return True
