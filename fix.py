"""
"fix that": after a command fails, explain what went wrong and suggest a
fixed command. The common beginner mistakes are fixed here, offline:

    gti status            -> git status            (a typo in the command)
    cd Documnets          -> cd Documents          (a typo in a folder name)
    apt install htop      -> sudo apt install htop (needs admin rights)
    ./backup.sh           -> chmod +x backup.sh && ./backup.sh
    cp photos backup/     -> cp -r photos backup/
    apt: Unable to locate -> sudo apt update && sudo apt install ...

Anything else goes to the local AI (clishe_brain.ClisheBrain.fix).
"""
import difflib
import os
import re
import shlex
from typing import List, Optional

from knowledge import POPULAR_PROGRAMS, diagnose_error

# Commands where guessing a different file name could destroy the wrong
# file: Clishe only mentions the close match, it never puts it in a command.
_DESTRUCTIVE = {"rm", "rmdir", "mv", "shred", "truncate", "dd", "chmod", "chown", "unlink"}
_EVERYDAY = {"ls", "cd", "cp", "mv", "rm", "cat", "less", "head", "tail", "grep", "find",
             "mkdir", "touch", "nano", "sudo", "df", "du", "free", "ps", "top", "kill",
             "chmod", "tar", "man", "echo", "pwd", "ssh", "clear", "exit", "history"}

# Commands that change the whole system and fail without sudo.
_NEEDS_ROOT = {"apt", "apt-get", "dnf", "yum", "pacman", "zypper", "apk", "systemctl",
               "mount", "umount", "useradd", "usermod", "passwd", "snap", "flatpak"}
_ROOT_MESSAGES = ("permission denied", "are you root", "must be run as root",
                  "requires superuser", "operation not permitted", "access denied",
                  "you need to be root", "authentication is required")


def _words(command: str) -> List[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _quote(word: str) -> str:
    return shlex.quote(word) if word else word


def _replace_word(command: str, old: str, new: str) -> str:
    """Swap one word of the command, keeping the rest exactly as typed."""
    pattern = r"(?<![\w./-])" + re.escape(old) + r"(?![\w./-])"
    if re.search(pattern, command):
        return re.sub(pattern, lambda m: _quote(new), command, count=1)
    return " ".join(_quote(new) if w == old else _quote(w) for w in _words(command))


def _programs(path_dirs: Optional[List[str]] = None) -> List[str]:
    names = set()
    for folder in path_dirs if path_dirs is not None else os.environ.get("PATH", "").split(":"):
        try:
            names.update(os.listdir(folder))
        except OSError:
            continue
    return sorted(names)


def _typo_in_command(command: str, error: str, path_dirs) -> Optional[dict]:
    m = re.search(r"([^\s:]+): (?:command )?not found", error)
    if not m:
        return None
    name = m.group(1)
    # Swapped letters ("gti", "sl") among well-known commands first, then
    # anything similar that's installed.
    known = sorted(POPULAR_PROGRAMS | _EVERYDAY)
    installed = set(_programs(path_dirs))
    close = [p for p in known if p in installed and len(p) == len(name)
             and sorted(p) == sorted(name) and p != name][:1]
    close = close or difflib.get_close_matches(
        name, [p for p in known if p in installed], n=1, cutoff=0.66)
    close = close or difflib.get_close_matches(name, sorted(installed), n=1, cutoff=0.8)
    if close:
        return {"explanation": f"There's no program called '{name}'. "
                               f"You probably meant '{close[0]}'.",
                "command": _replace_word(command, name, close[0])}
    return None


def _typo_in_path(command: str, error: str, cwd: str) -> Optional[dict]:
    if "no such file or directory" not in error.lower():
        return None
    for word in _words(command)[1:]:
        if word.startswith("-") or os.path.exists(os.path.join(cwd, os.path.expanduser(word))):
            continue
        folder, name = os.path.split(os.path.expanduser(word))
        try:
            entries = os.listdir(os.path.join(cwd, folder) if folder else cwd)
        except OSError:
            continue
        close = difflib.get_close_matches(name, entries, n=1, cutoff=0.7) or [
            e for e in entries if e.lower() == name.lower()]
        if close:
            fixed = os.path.join(os.path.dirname(word), close[0]) if folder else close[0]
            if os.path.basename(_words(command)[0]) in _DESTRUCTIVE:
                return {"explanation": f"There's nothing called '{word}' here. Did you mean "
                                       f"'{fixed}'? Check carefully before running "
                                       f"{_words(command)[0]} on it.",
                        "command": ""}
            return {"explanation": f"There's nothing called '{word}' here, but there is "
                                   f"'{fixed}'. Names are case-sensitive on Linux.",
                    "command": _replace_word(command, word, fixed)}
        return {"explanation": f"There's nothing called '{word}' in this folder. "
                               "Type ls to see what's here, or pwd to see where you are.",
                "command": ""}
    return None


def _needs_sudo(command: str, error: str) -> Optional[dict]:
    words = _words(command)
    if not words or words[0] == "sudo":
        return None
    lowered = error.lower()
    if "(publickey)" in lowered:
        return None
    if words[0] in _NEEDS_ROOT or any(m in lowered for m in _ROOT_MESSAGES):
        if words[0].startswith("./") and "permission denied" in lowered:
            return None  # a script that isn't executable, not a sudo problem
        return {"explanation": "This changes the whole system, so it needs admin rights. "
                               "sudo runs it as the administrator and asks for your password.",
                "command": f"sudo {command}"}
    return None


def _not_executable(command: str, error: str) -> Optional[dict]:
    words = _words(command)
    if words and words[0].startswith("./") and "permission denied" in error.lower():
        script = words[0][2:]
        return {"explanation": f"'{script}' isn't marked as a program you can run. "
                               "chmod +x marks it as runnable (you only need to do this once).",
                "command": f"chmod +x {_quote(script)} && {command}"}
    return None


def _folder_needs_r(command: str, error: str) -> Optional[dict]:
    words = _words(command)
    lowered = error.lower()
    if not words:
        return None
    if words[0] == "cp" and ("-r not specified" in lowered or "is a directory" in lowered):
        return {"explanation": "That's a folder. cp copies folders only with -r "
                               "(recursive: the folder and everything inside it).",
                "command": f"cp -r {command[len('cp'):].strip()}"}
    if words[0] in ("cat", "less", "head", "tail") and "is a directory" in lowered:
        target = next((w for w in words[1:] if not w.startswith("-")), "")
        return {"explanation": f"'{target}' is a folder, not a file. ls shows what's inside it.",
                "command": f"ls {_quote(target)}"}
    return None


def _apt_update(command: str, error: str) -> Optional[dict]:
    m = re.search(r"unable to locate package (\S+)", error, re.I)
    if m and "apt" in command:
        return {"explanation": f"apt doesn't know '{m.group(1)}' yet. Its list of packages "
                               "may be out of date: apt update refreshes it. If it still "
                               "isn't found, the name may be different (try: apt search "
                               f"{m.group(1)}).",
                "command": f"sudo apt update && {command if command.startswith('sudo') else 'sudo ' + command}"}
    return None


RULES = [_typo_in_command, _not_executable, _apt_update, _needs_sudo, _folder_needs_r]


def offline_fix(command: str, error: str, cwd: Optional[str] = None,
                path_dirs: Optional[List[str]] = None) -> Optional[dict]:
    """{"explanation", "command"} for a failed command, or None if no rule
    fits. "command" may be empty when there's advice but no single fix."""
    command, error = (command or "").strip(), error or ""
    if not command:
        return None
    for rule in RULES:
        result = (rule(command, error, path_dirs) if rule is _typo_in_command
                  else rule(command, error))
        if result:
            return result
    result = _typo_in_path(command, error, cwd or os.getcwd())
    if result:
        return result
    hint = diagnose_error(error)
    if hint:
        return {"explanation": hint, "command": ""}
    return None
