"""
Reads the manual pages already installed on this computer, so Clishe can
explain any installed command offline, and check an AI suggestion against
the real documentation for your version of the tool.

Nothing here touches the network: it runs `man` (or, when there's no man
page, `<command> --help`) and picks out the lines that matter.
"""
import functools
import os
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

from safety import check_command

MAN_TIMEOUT = 4
HELP_TIMEOUT = 2
MAX_DESCRIPTION = 160

# Overstrike bold/underline ("b\bb", "_\bx") and colour codes in man output.
_OVERSTRIKE = re.compile(r".\x08")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._+-]+$")
# Words that join commands on one line: only the first command of each part
# is looked up.
_COMMAND_JOINERS = re.compile(r"\|\||&&|[|;&]")
_WRAPPERS = {"sudo", "doas", "env", "nice", "nohup", "time", "command", "exec"}
# Never run these, even with --help: an old or unusual version might not
# know the flag and do its real job instead.
_NEVER_RUN = {"reboot", "shutdown", "poweroff", "halt", "init", "telinit",
              "dd", "shred", "wipefs", "fdisk", "sfdisk", "gdisk", "sgdisk",
              "parted", "cfdisk", "mkswap", "rm", "rmdir", "kill", "killall",
              "pkill", "xkill"}


def _clean(text: str) -> str:
    return _ANSI.sub("", _OVERSTRIKE.sub("", text or ""))


@functools.lru_cache(maxsize=32)
def read_manual(name: str) -> Tuple[str, str]:
    """(text, source) for a command: its man page, else its --help output.
    source is "man <name>" or "<name> --help"; both empty if neither exists."""
    if not name or not _SAFE_NAME.match(name):
        return "", ""
    env = dict(os.environ, MANPAGER="cat", PAGER="cat", MANWIDTH="80",
               GROFF_NO_SGR="1", MAN_KEEP_FORMATTING="")
    if shutil.which("man"):
        try:
            out = subprocess.run(["man", name], capture_output=True, text=True,
                                 env=env, timeout=MAN_TIMEOUT, stdin=subprocess.DEVNULL)
            if out.returncode == 0 and out.stdout.strip():
                return _clean(out.stdout), f"man {name}"
        except (OSError, subprocess.SubprocessError):
            pass

    if (name in _NEVER_RUN or name.startswith("mkfs") or not shutil.which(name)
            or check_command(name)):
        return "", ""
    try:
        out = subprocess.run([name, "--help"], capture_output=True, text=True,
                             env=env, timeout=HELP_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return "", ""
    text = out.stdout if out.stdout.strip() else out.stderr
    if "--help" in text or "usage" in text.lower():
        return _clean(text), f"{name} --help"
    return "", ""


def summary(text: str) -> str:
    """The one-line description from the NAME section ("ls - list directory
    contents"), or "" if there isn't one."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "NAME":
            parts = []
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    if parts:
                        break
                    continue
                if not nxt.startswith((" ", "\t")):
                    break
                parts.append(nxt.strip())
            return " ".join(parts)
    return ""


def _first_sentence(text: str) -> str:
    """Beginners need the gist: the first sentence, kept short."""
    m = re.search(r"(?<=[a-z0-9)'\"”])\.(\s|$)", text[20:])
    if m:
        text = text[:20 + m.start() + 1]
    if len(text) > MAX_DESCRIPTION:
        text = text[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "..."
    return text


def _option_names(spec: str) -> List[str]:
    """'-h, --human-readable' -> ['-h', '--human-readable'];
    '--block-size=SIZE' -> ['--block-size']; '-size n[cwbkMG]' -> ['-size']."""
    names = []
    for part in re.split(r"[,\s]+", spec):
        part = re.split(r"[=\[<]", part, maxsplit=1)[0]
        if part.startswith("-") and len(part) > 1:
            names.append(part)
    return names


def flag_help(text: str, flag: str) -> str:
    """The manual's description of one option, as a single short line, or ""
    if the manual doesn't mention it."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("-"):
            continue
        # "-l     use a long listing format": options, a gap, then the text.
        # "-x, --extract" alone: the text is on the indented lines below.
        m = re.match(r"(\S.*?)(?:\s{2,}|\t)(.*)$", stripped)
        spec, rest = (m.group(1), m.group(2)) if m else (stripped, "")
        if flag not in _option_names(spec):
            continue
        # The text continues on the lines below that are indented further.
        description = rest.strip()
        indent = len(line) - len(stripped)
        for nxt in lines[i + 1:]:
            if not nxt.strip():
                if description:
                    break
                continue
            if len(nxt) - len(nxt.lstrip()) <= indent or nxt.lstrip().startswith("-"):
                break
            description += " " + nxt.strip()
            if len(description) > MAX_DESCRIPTION * 2:
                break
        description = _first_sentence(" ".join(description.split()))
        if not description:
            continue
        return description
    return ""


def _simple_commands(command: str) -> List[List[str]]:
    """Words of each command on the line, wrappers like sudo removed."""
    import shlex
    result = []
    for part in _COMMAND_JOINERS.split(command or ""):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        while words and (words[0] in _WRAPPERS or re.match(r"^\w+=", words[0])):
            words = words[1:]
        if words:
            result.append(words)
    return result


_SINGLE_DASH_WORD = re.compile(r"^\s+-[a-z][a-z]+\b", re.M)


def _lookup(text: str, token: str) -> List[Tuple[str, str]]:
    """Find a flag the way the user wrote it. '-la' isn't an option of its
    own, so try it whole first, then letter by letter, unless the command
    uses whole words after one dash (find -size, find -name): there an
    unknown '-bigger' is one made-up option, not six letters."""
    name = token.split("=", 1)[0]
    found = flag_help(text, name)
    if found or name.startswith("--") or len(name) <= 2 or _SINGLE_DASH_WORD.search(text):
        return [(name, found)]
    return [(f"-{c}", flag_help(text, f"-{c}")) for c in name[1:]]


def check_flags(command: str) -> List[dict]:
    """For each command on the line: what the manual says about it and about
    each flag used. Commands without a manual on this computer are left out.

    Returns [{"name", "source", "summary", "flags": [(flag, help or "")]}]."""
    notes = []
    for words in _simple_commands(command):
        name = os.path.basename(words[0])
        text, source = read_manual(name)
        if not text:
            continue
        flags, seen = [], set()
        for tok in words[1:]:
            if not tok.startswith("-") or tok in ("-", "--") or tok[1:].isdigit():
                continue
            for flag, help_text in _lookup(text, tok):
                if flag not in seen:
                    seen.add(flag)
                    flags.append((flag, help_text))
        notes.append({"name": name, "source": source,
                      "summary": summary(text), "flags": flags})
    return notes


def explain_from_manual(command: str) -> Optional[str]:
    """Explain a command and the flags used, from the local manual only.
    None if there's no manual for it, or it says nothing useful."""
    notes = check_flags(command)
    if not notes:
        return None
    note = notes[0]
    if not note["summary"] and not any(h for _, h in note["flags"]):
        return None
    parts = [note["summary"]] if note["summary"] else []
    if note["flags"]:
        lines = [f"  {flag}  {help_text or '(not found in the manual)'}"
                 for flag, help_text in note["flags"]]
        parts.append(f"In '{command.strip()}':\n" + "\n".join(lines))
    parts.append(f"Full details: {note['source']}")
    return "\n".join(parts)
