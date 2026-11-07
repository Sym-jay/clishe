"""
`clishe check`: "is this safe to run?" for a command or a script someone
found online. It never runs anything. It says what the command would do:
what it changes, whether it uses the internet or admin rights, whether it
installs software, and any risky patterns the safety check knows - with a
safer way to do it when there is one.

    clishe check 'curl -fsSL https://get.example.com | sudo bash'
    clishe check install.sh
"""
import os
import re
from typing import List, Optional
from urllib.parse import urlparse

from safety import _segments, _strip_wrappers, _tokenize, check_command

MAX_SCRIPT_BYTES = 200_000
MAX_LINES_SHOWN = 40

_URL = re.compile(r"https?://[^\s'\"|;&)]+")
_NETWORK = {"curl", "wget", "ssh", "scp", "rsync", "ftp", "sftp", "nc", "telnet"}
_PACKAGE_INSTALL = {
    "apt": {"install", "upgrade", "full-upgrade", "dist-upgrade"},
    "apt-get": {"install", "upgrade", "dist-upgrade"},
    "dnf": {"install", "upgrade"}, "yum": {"install", "update"},
    "pacman": {"-S", "-Syu", "-U"}, "zypper": {"install", "in", "update"},
    "apk": {"add", "upgrade"}, "brew": {"install", "upgrade"},
    "snap": {"install"}, "flatpak": {"install"},
    "pip": {"install"}, "pip3": {"install"}, "pipx": {"install"},
    "npm": {"install", "i"}, "cargo": {"install"}, "gem": {"install"},
}
_REMOVE = {"rm", "rmdir", "shred", "unlink"}
_WRITE = {"cp", "mv", "mkdir", "touch", "ln", "tee", "install", "rsync", "dd",
          "chmod", "chown", "chgrp", "unzip", "truncate", "sed"}
_EXTRACT = {"tar": "x", "unzip": ""}
_SERVICES = {"systemctl", "service", "useradd", "usermod", "userdel",
             "passwd", "mount", "umount", "ufw", "iptables", "reboot", "shutdown"}
# Files every new terminal reads when it starts.
_STARTUP_FILES = {".bashrc", ".bash_profile", ".bash_login", ".profile", ".zshrc",
                  ".zprofile", ".zshenv", "config.fish"}
# Folders whose programs can be run by name from anywhere.
_BIN_DIRS = ("/usr/local/bin", "/usr/local/sbin", "/usr/bin", "/usr/sbin", "/bin", "/sbin",
             "~/.local/bin", "~/bin")
# ssh-keygen options that only read or look up keys, never make one.
_SSH_KEYGEN_READS = {"-l", "-y", "-F", "-R", "-H", "-L", "-B", "-e", "-i", "-Q"}


def _flag_value(args: List[str], short: str, long: str = "") -> Optional[str]:
    """The value of -o FILE, -oFILE, -sSLo FILE (short flags run together) or
    --output=FILE / --output FILE."""
    letter = short[1]
    for i, a in enumerate(args):
        if long and a == long:
            return args[i + 1] if i + 1 < len(args) else None
        if long and a.startswith(long + "="):
            return a[len(long) + 1:]
        if a.startswith("-") and not a.startswith("--") and letter in a[1:]:
            rest = a[a.index(letter, 1) + 1:]
            return rest or (args[i + 1] if i + 1 < len(args) else None)
    return None


def _download_target(name: str, args: List[str]) -> Optional[str]:
    """The file curl or wget saves to, or None when it prints the download."""
    if name == "curl":
        out = _flag_value(args, "-o", "--output")
        if out:
            return out
        if "-O" in args or "--remote-name" in args:
            return "a file named after the download"
    elif name == "wget":
        out = _flag_value(args, "-O", "--output-document")
        if out:
            return None if out == "-" else out
        return "a file named after the download"
    return None


def _bind_mounts(args: List[str]) -> List[str]:
    """Folders of this computer that docker/podman run gives the container."""
    sources = []
    for i, a in enumerate(args):
        if a in ("-v", "--volume", "--mount") and i + 1 < len(args):
            value = args[i + 1]
        elif a.startswith("--volume=") or a.startswith("--mount="):
            value = a.split("=", 1)[1]
        elif a.startswith("-v") and len(a) > 2 and not a.startswith("--"):
            value = a[2:]
        else:
            continue
        if a.startswith("--mount"):     # type=bind,source=/,target=/host
            source = next((p.split("=", 1)[1] for p in value.split(",")
                           if p.startswith(("source=", "src="))), "")
        else:                           # /:/host
            source = value.split(":", 1)[0]
        # A named volume ("data:/data") is Docker's own storage, not a folder here.
        if source.startswith(("/", "~", ".", "$")):
            sources.append(source)
    return sources


def _opens_to_everyone(mode: str) -> bool:
    """chmod modes that let every user change the file: 777, 666, o+w, a+w."""
    if mode.isdigit():
        return len(mode) >= 3 and mode[-1] in "2367"
    return any(re.match(r"[ugoa]*[ao][ugoa]*[+=][rwxXst]*w", part) for part in mode.split(","))


def _notes(name: str, args: List[str], targets: List[str]) -> List[str]:
    """Special things worth a line of their own, beyond 'creates or changes'."""
    notes = []
    if name in ("docker", "podman") and args[:1] == ["run"]:
        for source in _bind_mounts(args):
            where = "every file" if source == "/" else source
            notes.append(f"Lets the container see and change {where} on this computer "
                         f"(-v {source}).")
        if "--privileged" in args:
            notes.append("Gives the container full control of this computer (--privileged).")
    elif name == "crontab" and not ({"-l", "-r"} & set(args)):
        notes.append("Schedules jobs that run later on their own (crontab). "
                     "Check them with: crontab -l")
    elif name == "ssh-keygen" and not ({"-f"} | _SSH_KEYGEN_READS) & set(args) \
            and not any(a.startswith("-f") for a in args):
        notes.append("Makes a new SSH key in the usual place (~/.ssh). If you already have "
                     "one there, answering yes to its question replaces it, and logins "
                     "that use the old key stop working.")
    elif name == "chmod" and len(targets) > 1 and _opens_to_everyone(targets[0]):
        inside = " and everything inside" if any(a in ("-R", "--recursive") for a in args) else ""
        notes.append(f"Lets every user on this computer change {', '.join(targets[1:])}"
                     f"{inside} (chmod {targets[0]}).")
    return notes


def _changed_notes(changed: List[str]) -> List[str]:
    notes = []
    for entry in changed:
        path = entry.split(" (")[0]
        if os.path.basename(path) in _STARTUP_FILES:
            notes.append(f"Changes {path}, which every new terminal reads when it starts.")
        # "cp x /usr/local/bin", ".../bin/" or ".../bin/x" all land in the folder.
        path = path.rstrip("/")
        folder = path if path in _BIN_DIRS else os.path.dirname(path)
        if folder in _BIN_DIRS:
            notes.append(f"Puts a program in {folder}, where it can be run by name from anywhere.")
    return notes


def _hosts(text: str) -> List[str]:
    hosts = []
    for url in _URL.findall(text):
        host = urlparse(url).hostname
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def _targets(args: List[str]) -> List[str]:
    return [a for a in args if not a.startswith("-")]


def _facts(command: str) -> dict:
    """What a command line touches, as data (see describe() for the words)."""
    facts = {"sudo": False, "network": False, "hosts": _hosts(command), "installs": [],
             "removed": [], "changed": [], "services": [], "notes": []}
    for words, redirects, piped in _segments(_tokenize(command)):
        if words and words[0] in ("sudo", "doas"):
            facts["sudo"] = True
        for op, target in redirects:
            # ">&2", "2>&1" and /dev/null only move output around; "< <(...)" is input.
            if op == "<" or target == "/dev/null" or target.isdigit() or target.startswith("&") or op.endswith("&"):
                continue
            facts["changed"].append(f"{target} ({'adds to it' if op == '>>' else 'replaces it'})")
        words = _strip_wrappers(words)
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        targets = _targets(args)
        facts["notes"].extend(_notes(name, args, targets))
        if name in _NETWORK or (name == "git" and args[:1] in (["clone"], ["pull"], ["push"])):
            facts["network"] = True
        saved = _download_target(name, args)
        if saved:
            facts["changed"].append(saved)
        if name in _PACKAGE_INSTALL and any(a in _PACKAGE_INSTALL[name] for a in args[:2]):
            pkgs = [a for a in args[1:] if not a.startswith("-")]
            facts["installs"].append(f"{name}: {' '.join(pkgs) or 'updates'}")
        elif name in _REMOVE:
            facts["removed"].extend(targets or ["(nothing named)"])
        elif name in _WRITE and not (name == "sed" and "-i" not in args):
            if name in ("cp", "mv", "ln", "install", "rsync"):
                targets = targets[-1:]       # the destination
            elif name in ("sed", "chmod", "chown", "chgrp"):
                targets = targets[1:]        # skip the expression, mode or owner
            facts["changed"].extend(targets)
        elif name == "tar" and "x" in "".join(a.lstrip("-") for a in args[:1]):
            facts["changed"].append("files unpacked from the archive")
        elif name in _SERVICES or (name == "crontab" and "-l" not in args):
            facts["services"].append(" ".join([name] + args[:2]))
    facts["notes"].extend(_changed_notes(facts["changed"]))
    return facts


def _merge(all_facts: List[dict]) -> dict:
    merged = {"sudo": False, "network": False, "hosts": [], "installs": [],
              "removed": [], "changed": [], "services": [], "notes": []}
    for facts in all_facts:
        for key, value in facts.items():
            if isinstance(value, bool):
                merged[key] = merged[key] or value
            else:
                merged[key].extend(v for v in value if v not in merged[key])
    return merged


def describe(facts: dict) -> List[str]:
    """The facts in plain English, most important first."""
    effects = []
    if facts["sudo"]:
        effects.append("Runs as the administrator (sudo), so it can change anything on "
                       "this computer.")
    if facts["network"] or facts["hosts"]:
        where = f": {', '.join(facts['hosts'])}" if facts["hosts"] else ""
        effects.append(f"Uses the internet{where}.")
    if facts["installs"]:
        effects.append("Installs or updates software (downloaded from the internet): "
                       + "; ".join(facts["installs"]) + ".")
    if facts["removed"]:
        effects.append("Deletes: " + ", ".join(facts["removed"]) + ".")
    if facts["changed"]:
        effects.append("Creates or changes: " + ", ".join(dict.fromkeys(facts["changed"])) + ".")
    if facts["services"]:
        effects.append("Changes how the system runs: " + ", ".join(facts["services"]) + ".")
    effects.extend(dict.fromkeys(facts["notes"]))
    return effects or ["Only reads or shows things. It doesn't change any files."]


def inspect(command: str) -> dict:
    """What one command line would do. Returns
    {"command", "warnings": [...], "effects": [...], "safer": [steps], "facts"}."""
    warnings = check_command(command)
    facts = _facts(command)
    safer = []
    if any("runs a script it downloads" in w for w in warnings) and facts["hosts"]:
        url = _URL.search(command).group(0)
        name = os.path.basename(urlparse(url).path) or "script.sh"
        safer = [f"curl -fsSL {url} -o {name}", f"less {name}", f"clishe check {name}"]
    return {"command": command, "warnings": warnings, "effects": describe(facts),
            "safer": safer, "facts": facts}


def script_lines(text: str) -> List[str]:
    """The commands in a script: comments and blank lines dropped,
    backslash-continued lines joined."""
    lines, current = [], ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if current:
            line = current + " " + line.lstrip()
            current = ""
        if line.endswith("\\"):
            current = line[:-1].rstrip()
            continue
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    if current.strip():
        lines.append(current.strip())
    return lines


def read_script(path: str) -> Optional[str]:
    """The text of a script file, or None if it isn't a readable text file."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_SCRIPT_BYTES:
            return None
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def check_script(text: str) -> dict:
    """Every command in a script, plus one summary for the whole script."""
    results = [inspect(line) for line in script_lines(text)]
    return {"results": results, "risky": [r for r in results if r["warnings"]],
            "effects": describe(_merge([r["facts"] for r in results]))}
