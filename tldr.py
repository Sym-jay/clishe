"""
Command summaries and examples from tldr-pages
(https://github.com/tldr-pages/tldr), licensed CC BY 4.0 - see NOTICE.md.
tldr.json.gz is built by scripts/build_tldr.py.

Used for:
  - a plain-English summary of thousands of commands (explain, labels);
  - real examples under `explain`;
  - matching what people type against example descriptions ("extract a
    tar file" -> "Extract a (compressed) archive file into the current
    directory verbosely"), offline, before any AI is asked.
"""
import functools
import gzip
import json
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

DATA = Path(__file__).resolve().parent / "tldr.json.gz"
CREDIT = "tldr-pages"

_HIGHLIGHT = re.compile(r"\[([A-Za-z0-9])\]")       # "E[x]tract" -> "Extract"
_PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")
_OPTION_CHOICE = re.compile(r"^\[(-[^|\]]+)\|(--?[^|\]]+)\]$")  # {{[-C|--directory]}}


@functools.lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return json.loads(gzip.decompress(DATA.read_bytes()))
    except (OSError, ValueError, EOFError):
        return {}


def _platforms() -> Tuple[str, str]:
    return ("osx", "common") if sys.platform == "darwin" else ("linux", "common")


def page(name: str) -> Optional[dict]:
    """The page for a command on this kind of system, or None."""
    for platform in _platforms():
        found = _data().get(platform, {}).get(name)
        if found:
            return found
    return None


def clean(text: str) -> str:
    """tldr marks the letter an option stands for ("E[x]tract"); drop that,
    and the backticks around code."""
    text = _HIGHLIGHT.sub(r"\1", text).replace("`", "").strip()
    return text[:1].upper() + text[1:]


def summary(name: str) -> str:
    """The page's first sentence, e.g. "Archiving utility."."""
    found = page(name)
    if not found or not found.get("s"):
        return ""
    first = re.split(r"(?<=[\w)])\. (?=[A-Z])", clean(found["s"]), maxsplit=1)[0]
    return first.rstrip(".") + "."


def _label(value: str) -> str:
    """A Clishe placeholder name for a tldr value: lowercase words only."""
    value = value.strip()
    if "://" in value:
        return "url"
    if re.fullmatch(r"[\d.]+", value):
        return "number"
    value = value.replace("path/to/", "").split(" ")[0].rstrip(".")
    base, dot, _ext = value.partition(".")
    words = re.findall(r"[a-z]+", re.sub(r"[_\-]", " ", base.lower()))
    if not words:
        return "pattern" if "*" in value else "value"
    label = " ".join(words)
    if dot and not label.endswith(("file", "directory", "folder")):
        label += " file"
    return label


def template(command: str) -> str:
    """A tldr command as a Clishe template: {{path/to/file}} -> <file>,
    {{[-C|--directory]}} -> -C (the short form works on Linux and macOS)."""
    def swap(m):
        inner = m.group(1)
        choice = _OPTION_CHOICE.match(inner)
        if choice:
            return choice.group(1)
        return f"<{_label(inner)}>"
    # "/{{path/to/file}}" means an absolute path; the placeholder covers it.
    command = command.replace("/{{path/to/", "{{path/to/")
    return _PLACEHOLDER.sub(swap, command)


def shown(command: str) -> str:
    """A tldr command for reading: {{path/to/file}} -> <path/to/file>."""
    def swap(m):
        choice = _OPTION_CHOICE.match(m.group(1))
        return choice.group(1) if choice else f"<{m.group(1)}>"
    return _PLACEHOLDER.sub(swap, command)


def examples(name: str, limit: int = 3) -> List[Tuple[str, str]]:
    """[(what it does, command)] from the page, ready to show."""
    found = page(name)
    if not found:
        return []
    return [(clean(d), shown(c)) for d, c in found.get("e", [])[:limit]]


@functools.lru_cache(maxsize=1)
def _installed_examples() -> List[Tuple[str, str, frozenset, int, str]]:
    """Every example whose command is installed here, as (description,
    template, meaning tokens of the description plus the command name,
    position on its page, command name)."""
    from clishe_brain import meaning_tokens
    out, seen = [], set()
    for platform in _platforms():
        for name, found in _data().get(platform, {}).items():
            if name in seen or not shutil.which(name):
                continue
            seen.add(name)
            for position, (desc, command) in enumerate(found.get("e", [])):
                words = command.split()
                if words[:1] == ["sudo"]:
                    words = words[1:]
                if not words or words[0] != name:
                    continue  # a different program
                text = clean(desc)
                out.append((text, template(command), meaning_tokens(f"{text} {name}"),
                            position, name))
    return out


# Matching is deliberately strict: a wrong suggestion teaches the wrong
# thing, so it's better to say nothing and let the AI or "teach me" answer.
# Only commands a beginner is likely to want (the ones Clishe already
# teaches, plus everyday tools) are offered...
EVERYDAY = set("""
ls cd cp mv rm mkdir rmdir touch cat less more head tail wc sort uniq cut tr
grep find xargs tar gzip gunzip zip unzip chmod chown chgrp ln df du free ps
top htop kill pkill killall ping curl wget ssh scp rsync date cal uptime whoami
who hostname uname env echo sed awk diff file stat which whereis man history
tee basename dirname realpath watch sleep seq split paste nl lsblk mount umount
ip ss netstat dig nslookup traceroute systemctl journalctl crontab git python3
pip3 nano vim tree jq zcat zless
""".split())
# ...every meaningful word they typed must appear in the example (or be the
# command's name), with at least two real words in common...
MIN_OVERLAP = 2.0
# ...and the request must start with the same action as the example.
_SHOW_WORDS = {"show", "list", "display", "print", "view", "see", "check", "get", "output"}


def _verb(text: str) -> str:
    from clishe_brain import meaning_tokens, normalize_phrase
    words = normalize_phrase(text).split()
    if not words:
        return ""
    if words[0] in _SHOW_WORDS:
        return "show"
    token = meaning_tokens(words[0])
    return next(iter(token)) if len(token) == 1 else ""


@functools.lru_cache(maxsize=1)
def _beginner_commands() -> frozenset:
    from knowledge import _COMMAND_DICT, POPULAR_PROGRAMS
    return frozenset(EVERYDAY | set(_COMMAND_DICT) | POPULAR_PROGRAMS)


def match(phrase: str) -> Optional[Tuple[str, str]]:
    """The installed example that fits `phrase`, as (description, command
    template), or None. Like any near match, the caller must ask before
    running it."""
    from clishe_brain import _weight, meaning_tokens
    from knowledge import _COMMAND_DICT
    wanted = meaning_tokens(phrase)
    action = _verb(phrase)
    if not wanted or not action:
        return None
    best, best_rank = None, None
    for desc, command, have, position, name in _installed_examples():
        if name not in _beginner_commands() or _verb(desc) != action:
            continue
        overlap = _weight(wanted & have)
        if overlap < MIN_OVERLAP or not wanted <= have:
            continue
        # Commands Clishe already teaches first; then the page's common
        # examples (tldr lists those first); then the description most
        # about the request; then the simplest command.
        rank = (name in _COMMAND_DICT, -position, overlap / _weight(have), -len(command))
        if best_rank is None or rank > best_rank:
            best, best_rank = (desc, command), rank
    return best
