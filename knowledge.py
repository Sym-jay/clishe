"""
Offline knowledge base - command explanations and error-message translations
that don't require any AI provider or network call. This is the free, instant
tier that AI resolution/explanation falls back to only when this misses.
"""
import json
import re
import shlex
import shutil
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent

_COMMAND_DICT_FILE = _DATA_DIR / "command_dictionary.json"
_ERROR_PATTERNS_FILE = _DATA_DIR / "error_patterns.json"
_OUTPUT_GUIDES_FILE = _DATA_DIR / "output_guides.json"


def _load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


_COMMAND_DICT = _load_json(_COMMAND_DICT_FILE, {})
_ERROR_PATTERNS = _load_json(_ERROR_PATTERNS_FILE, [])
_OUTPUT_GUIDES = _load_json(_OUTPUT_GUIDES_FILE, [])


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


def _manual_flag(command: str, flag: str) -> str:
    """A flag that isn't in the offline notes: ask the manual installed on
    this computer."""
    from manual import flag_help, read_manual
    name = _base_name(command)
    text, source = read_manual(name)
    found = flag_help(text, flag) if text else ""
    if found:
        return f"{found} (from {source})"
    return f"(not in my offline notes - try: man {name})"


def format_explanation(entry: dict, command: str = "") -> str:
    """Turn a dictionary entry into a beginner-friendly explanation string.
    If `command` is given and uses flags, explain those specific flags
    instead of listing the common ones."""
    parts = [entry.get("summary", "").strip()]

    flags = entry.get("flags") or {}
    known, unknown = explain_flags(command, entry) if command else ([], [])
    if known or unknown:
        lines = [f"  {flag}  {desc}" for flag, desc in known]
        lines += [f"  {flag}  {_manual_flag(command, flag)}" for flag in unknown]
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


# ---------- programs that aren't installed ----------

# How each distro family installs a package.
_INSTALLERS = [
    ({"ubuntu", "debian", "linuxmint", "pop", "elementary", "kali", "raspbian", "zorin"},
     "apt", "sudo apt install {}"),
    ({"fedora", "rhel", "centos", "rocky", "almalinux", "nobara"}, "dnf", "sudo dnf install {}"),
    ({"arch", "manjaro", "endeavouros", "garuda", "cachyos"}, "pacman", "sudo pacman -S {}"),
    ({"opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse", "sles"}, "zypper",
     "sudo zypper install {}"),
    ({"alpine"}, "apk", "sudo apk add {}"),
    ({"macos"}, "brew", "brew install {}"),
]

# Where the package name differs from the command name.
_PACKAGE_NAMES = {
    "ifconfig": {"*": "net-tools"},
    "netstat": {"*": "net-tools"},
    "dig": {"apt": "dnsutils", "dnf": "bind-utils", "pacman": "bind", "zypper": "bind-utils",
            "brew": "bind"},
    "nslookup": {"apt": "dnsutils", "dnf": "bind-utils", "pacman": "bind", "zypper": "bind-utils",
                 "brew": "bind"},
    "pip3": {"apt": "python3-pip", "dnf": "python3-pip", "pacman": "python-pip", "apk": "py3-pip"},
    "rg": {"*": "ripgrep"},
    "fd": {"apt": "fd-find"},
    "7z": {"apt": "p7zip-full", "dnf": "p7zip", "pacman": "p7zip", "brew": "p7zip"},
    "convert": {"*": "imagemagick", "dnf": "ImageMagick"},
    "nvim": {"*": "neovim"},
    "node": {"apt": "nodejs", "dnf": "nodejs", "pacman": "nodejs"},
    "javac": {"apt": "default-jdk", "dnf": "java-latest-openjdk-devel", "pacman": "jdk-openjdk",
              "brew": "openjdk"},
    "java": {"apt": "default-jre", "dnf": "java-latest-openjdk", "pacman": "jre-openjdk",
             "brew": "openjdk"},
}

# Commands with a different name on most Linux systems.
_USE_INSTEAD = {
    "python": "python3",
    "pip": "pip3 (or python3 -m pip)",
}

# Well-known programs. When someone types one of these and it isn't
# installed, they meant to run it - it isn't English for the AI.
POPULAR_PROGRAMS = set("""
htop btop top neofetch fastfetch tree curl wget git vim nvim nano emacs micro
python python3 pip pip3 node npm docker podman code gcc g++ make cmake java javac
rustc cargo go ffmpeg unzip zip 7z tmux screen zsh fish ssh rsync jq fzf rg fd
bat ncdu nmap traceroute ifconfig netstat dig nslookup whois sl cowsay figlet
lolcat cmatrix tldr gparted vlc gimp firefox inxi lshw speedtest-cli
""".split())


def _installer(distro_family):
    for ids, manager, template in _INSTALLERS:
        if ids & set(distro_family):
            return manager, template
    return None, None


def missing_program_hint(name: str, distro_family=None) -> str:
    """'htop' -> "htop isn't installed. You can probably install it with:
    sudo apt install htop" (using the user's own package manager)."""
    name = (name or "").strip()
    if not name or "/" in name:
        return ""
    if name in _USE_INSTEAD:
        return (f"On most Linux systems '{name}' is called {_USE_INSTEAD[name]}. "
                f"Try that instead.")
    if distro_family is None:
        from config import detect_distro_family
        distro_family = detect_distro_family()
    manager, template = _installer(distro_family)
    if not manager:
        return (f"'{name}' isn't installed. Install it with your package manager "
                f"(the package is usually called {name}).")
    names = _PACKAGE_NAMES.get(name, {})
    package = names.get(manager) or names.get("*") or name
    hint = f"'{name}' isn't installed. You can probably install it with: {template.format(package)}"
    if manager == "brew" and not shutil.which("brew"):
        hint += " (first install Homebrew, from https://brew.sh)"
    return hint


def diagnose_error(error_text: str):
    """Match stderr text against known error patterns. Returns a hint string,
    or None if nothing matched."""
    if not error_text:
        return None
    # "bash: htop: command not found" -> name the program and say how to
    # install it on this distro, instead of a generic hint.
    m = re.search(r"([^\s:]+): command not found", error_text)
    if m:
        return missing_program_hint(m.group(1))
    lowered = error_text.lower()
    for entry in _ERROR_PATTERNS:
        if entry.get("match", "").lower() in lowered:
            return entry.get("hint")
    return None


# ---------- "what does this mean?" ----------

def output_guide(command: str):
    """A plain-English guide to reading the output of `command` (for the
    first command in a pipeline, e.g. 'du -sh * | sort -h' -> du).
    Returns (name, guide) or None."""
    first = re.split(r"\|\||&&|[|;&]", command or "", maxsplit=1)[0]
    try:
        words = shlex.split(first)
    except ValueError:
        words = first.split()
    while words and (words[0] in ("sudo", "doas", "time") or "=" in words[0]):
        words = words[1:]
    if not words:
        return None
    name = words[0].rsplit("/", 1)[-1]
    args = words[1:]
    flags = "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))
    positional = [a for a in args if not a.startswith("-")]
    for entry in _OUTPUT_GUIDES:
        if entry.get("command") != name:
            continue
        if "flag" in entry and entry["flag"] not in flags:
            continue
        if "sub" in entry and positional[:1] != [entry["sub"]]:
            continue
        label = name + (" " + entry["sub"] if "sub" in entry else "") + \
            (" -" + entry["flag"] if "flag" in entry else "")
        return label, entry["guide"]
    return None
