"""
Safety check for commands before Clishe runs them.

Every command Clishe is about to run (from your KB, an AI suggestion, or
something you typed) goes through `check_command`. If it looks destructive,
the shell asks you to type YES, and shows you *why* in plain English, so
the warning teaches something instead of just blocking.

This is a best-effort guard, not a sandbox. It catches common ways to lose
data or break a system; it can't catch everything. Read what you run.
"""
import os
import re
import shlex
from typing import List

# Tokens that separate one command from the next on a single line.
_SEPARATORS = {";", "&&", "||", "|", "&", "|&", "\n"}

# Wrappers that run the *next* word as the real command.
_WRAPPERS = {"sudo", "doas", "env", "nice", "nohup", "time", "command",
             "exec", "builtin", "xargs", "ionice", "stdbuf", "timeout"}

_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}

# Interpreters that run whatever script arrives on stdin.
_INTERPRETERS = _SHELLS | {"python", "python3", "perl", "ruby", "node"}

# rm targets that match everything in a folder (rm *.log is deliberate, so
# it isn't flagged).
_EVERYTHING_GLOBS = {"*", ".*", "./*", "*.*"}

# How deep to follow "bash -c '...'" / eval inside each other.
_MAX_NESTING = 3

_DISK_TOOLS = {"fdisk", "sfdisk", "gdisk", "sgdisk", "parted", "wipefs",
               "mkswap", "cfdisk"}

_POWER_TOOLS = {"shutdown", "reboot", "poweroff", "halt"}

_DISK_DEVICE = re.compile(r"^/dev/(sd[a-z]|nvme\d|hd[a-z]|vd[a-z]|mmcblk\d|xvd[a-z]|disk\d)")

# name(){ name|name& };name  -- works for any function name, not just ":".
_FORK_BOMB = re.compile(r"(\S+)\s*\(\)\s*\{[^}]*\1\s*\|\s*\1")

# Unquoted system-wide targets that are almost never what a beginner means.
_ROOT_TARGETS = {"/", "/*", "~", "~/", "$HOME", "/home", "/etc", "/usr",
                 "/bin", "/boot", "/var", "/lib"}

REASONS = {
    "rm_recursive": "deletes a folder and everything inside it, permanently (there's no trash bin)",
    "rm_root": "deletes files in a system-wide or home location",
    "mkfs": "formats a disk or partition, erasing everything on it",
    "disk_tool": "changes disk partitions, which can make data unreadable",
    "dd": "writes raw data to a file or device and can overwrite a whole disk",
    "disk_write": "writes directly to a disk device, destroying what's on it",
    "shred": "overwrites files so they can never be recovered",
    "chmod_recursive": "changes permissions on a folder and everything inside it",
    "chown_recursive": "changes the owner of a folder and everything inside it",
    "perm_root": "changes permissions or ownership on a system location",
    "find_delete": "deletes every file that matches the search",
    "pipe_to_shell": "runs a script it downloads or generates without letting you read it first",
    "fork_bomb": "is a 'fork bomb' that freezes the system by spawning processes forever",
    "git_reset_hard": "throws away your uncommitted changes in this git repo",
    "git_clean": "deletes untracked files from this git repo",
    "git_force_push": "overwrites history on the remote git repo",
    "power": "shuts down or restarts the computer",
    "crontab_remove": "deletes all of your scheduled (cron) jobs",
    "dev_null_move": "moves files into /dev/null, which deletes them",
    "rm_all": "deletes every file in the folder",
    "truncate": "empties the file, erasing everything that was in it",
}


def _tokenize(command: str) -> List[str]:
    """Split a command line into words and operators, respecting quotes.
    Falls back to a plain split on unbalanced quotes rather than failing."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return re.findall(r"[;&|<>]+|[^\s;&|<>]+", command)


def _segments(tokens: List[str]):
    """Yield (words, redirects, piped_into) for each simple command.
    `redirects` is a list of (operator, target) for output redirections.
    `piped_into` is True when the previous separator was a pipe."""
    words, redirects = [], []
    piped = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _SEPARATORS:
            if words or redirects:
                yield words, redirects, piped
            words, redirects = [], []
            piped = tok in ("|", "|&")
        elif tok and set(tok) <= set("<>&") and ">" in tok:
            # Output redirection: remember where it points.
            if i + 1 < len(tokens):
                redirects.append((tok, tokens[i + 1]))
                i += 1
        elif tok and set(tok) <= set("<"):
            i += 1  # input redirection: skip its target
        else:
            words.append(tok)
        i += 1
    if words or redirects:
        yield words, redirects, piped


def _strip_wrappers(words: List[str]) -> List[str]:
    """Drop `sudo`, `env FOO=bar`, `timeout 5` and the like so we look at the
    command that actually runs."""
    words = list(words)
    while words:
        first = os.path.basename(words[0])
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            words.pop(0)
        elif first in _WRAPPERS:
            words.pop(0)
            # Skip the wrapper's own options (sudo -u root, timeout 5, nice -n 10).
            while words and (words[0].startswith("-") or words[0].isdigit()):
                opt = words.pop(0)
                if opt in ("-u", "-g", "-n", "-c", "-s") and words:
                    words.pop(0)
        else:
            break
    return words


def _short_flags(args: List[str]) -> str:
    """All single-letter flags, e.g. ['-rf', '-v'] -> 'rfv'."""
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))


def _truncates_to_zero(args: List[str]) -> bool:
    """truncate -s 0 / -s0 / --size=0 / --size 0"""
    for i, a in enumerate(args):
        if a in ("-s0", "--size=0"):
            return True
        if a in ("-s", "--size") and args[i + 1:i + 2] == ["0"]:
            return True
    return False


def _check_segment(words: List[str], redirects, piped: bool, depth: int) -> List[str]:
    found = []
    for _op, target in redirects:
        if _DISK_DEVICE.match(target):
            found.append("disk_write")

    words = _strip_wrappers(words)
    # "> notes.txt" or ": > notes.txt" with nothing else empties the file.
    # ("echo hi > out.txt" is normal use and isn't flagged.)
    if (not words or words == [":"]) and any(
            op in (">", ">|", "&>") and not _DISK_DEVICE.match(t) for op, t in redirects):
        found.append("truncate")
    if not words:
        return found
    name = os.path.basename(words[0])
    args = words[1:]
    flags = _short_flags(args)
    long_flags = {a.split("=")[0] for a in args if a.startswith("--")}
    positional = [a for a in args if not a.startswith("-")]

    if piped and name in _INTERPRETERS and (
            not [p for p in positional if p != "-"] or (name in _SHELLS and "s" in flags)):
        found.append("pipe_to_shell")

    # Commands hidden in a string: bash -c '...', su -c '...', eval ...
    if depth < _MAX_NESTING:
        inner = None
        if name in _SHELLS | {"su"} and "c" in flags and positional:
            inner = positional[0]
        elif name == "eval" and args:
            inner = " ".join(args)
        if inner:
            found.extend(_check_keys(inner, depth + 1))

    if name == "rm":
        if "r" in flags or "R" in flags or "--recursive" in long_flags:
            found.append("rm_recursive")
        if any(p.rstrip("/") in {t.rstrip("/") for t in _ROOT_TARGETS} for p in positional):
            found.append("rm_root")
        if "--no-preserve-root" in long_flags:
            found.append("rm_root")
        if any(p in _EVERYTHING_GLOBS or p.endswith("/*") for p in positional):
            found.append("rm_all")
    elif name.startswith("mkfs"):
        found.append("mkfs")
    elif name in _DISK_TOOLS:
        found.append("disk_tool")
    elif name == "dd" and any(a.startswith("of=") for a in args):
        target = next(a[3:] for a in args if a.startswith("of="))
        found.append("disk_write" if _DISK_DEVICE.match(target) else "dd")
    elif name == "cp" and len(positional) >= 2 and _DISK_DEVICE.match(positional[-1]):
        found.append("disk_write")
    elif name == "tee" and any(_DISK_DEVICE.match(p) for p in positional):
        found.append("disk_write")
    elif name == "truncate" and _truncates_to_zero(args):
        found.append("truncate")
    elif name == "shred":
        found.append("shred")
    elif name in ("chmod", "chown", "chgrp"):
        if "R" in flags or "--recursive" in long_flags:
            found.append("chmod_recursive" if name == "chmod" else "chown_recursive")
        elif any(p in _ROOT_TARGETS for p in positional):
            found.append("perm_root")
    elif name == "find":
        if "-delete" in args or ("-exec" in args and any(
                os.path.basename(a) == "rm" for a in args)):
            found.append("find_delete")
    elif name == "git" and args:
        sub = args[0]
        if sub == "reset" and "--hard" in args:
            found.append("git_reset_hard")
        elif sub == "clean" and ("f" in flags or "--force" in long_flags):
            found.append("git_clean")
        elif sub == "push" and ("f" in flags or "--force" in long_flags
                                or "--force-with-lease" in long_flags):
            found.append("git_force_push")
    elif name in _POWER_TOOLS or (name == "init" and positional[:1] in (["0"], ["6"])):
        found.append("power")
    elif name == "crontab" and "r" in flags:
        found.append("crontab_remove")
    elif name == "mv" and positional and positional[-1] == "/dev/null":
        found.append("dev_null_move")
    return found


def _check_keys(command: str, depth: int = 0) -> List[str]:
    keys: List[str] = []
    if ":(){" in command.replace(" ", "") or _FORK_BOMB.search(command):
        keys.append("fork_bomb")
    for words, redirects, piped in _segments(_tokenize(command)):
        keys.extend(_check_segment(words, redirects, piped, depth))
    return keys


def check_command(command: str) -> List[str]:
    """Return a list of plain-English reasons this command looks dangerous.
    An empty list means nothing risky was recognised."""
    if not command or not command.strip():
        return []
    # De-duplicate, keeping order.
    seen, reasons = set(), []
    for k in _check_keys(command):
        if k not in seen:
            seen.add(k)
            reasons.append(REASONS[k])
    return reasons
