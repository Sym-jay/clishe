"""
Lesson packs for `clishe practice`: hands-on exercises that run in a
throwaway folder. Each pack is a JSON file:

    {"title": "...", "description": "...", "done": "...",
     "exercises": [{"task": "...", "check": [...], "hint": "...", "answer": "..."}]}

A check is a list of conditions that must all hold after the learner runs a
command. Conditions are data, never code, so a pack someone shares can't run
anything on your computer by being checked:

    {"typed": "<regex>"}            what they typed matches (Python regex)
    {"dir": "notes"}                a folder exists        (paths are relative
    {"file": "notes/todo.txt"}      a file exists           to the practice
    {"missing": "old.txt"}          nothing is there        folder)
    {"contains": ["f.txt", "milk"]} a file contains some text
    {"cwd": "notes"}                the learner is in that folder ("." = the practice folder)

Bundled packs live in lessons/ next to this file. Your own, or a workshop's,
go in ~/.local/share/clishe/lessons/ and win if the names clash.
"""
import json
import os
import re
from pathlib import Path
from typing import List, Optional

BUNDLED = Path(__file__).resolve().parent / "lessons"
CONDITIONS = {"typed", "dir", "file", "missing", "contains", "cwd"}
_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def user_dir() -> Path:
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data / "clishe" / "lessons"


def _pack_files() -> dict:
    files = {}
    for folder in (BUNDLED, user_dir()):
        if folder.is_dir():
            for path in sorted(folder.glob("*.json")):
                if _NAME.match(path.stem):
                    files[path.stem] = path
    return files


def problems(pack) -> List[str]:
    """What's wrong with a pack, in plain English (empty if it's fine)."""
    if not isinstance(pack, dict):
        return ["the file should hold one JSON object"]
    found = [f'missing "{key}"' for key in ("title", "exercises") if key not in pack]
    exercises = pack.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        return found + ['"exercises" should be a non-empty list']
    for n, ex in enumerate(exercises, 1):
        if not isinstance(ex, dict):
            found.append(f"exercise {n} should be an object")
            continue
        for key in ("task", "check", "hint", "answer"):
            if not ex.get(key):
                found.append(f'exercise {n} is missing "{key}"')
        for cond in ex.get("check") or []:
            if not isinstance(cond, dict) or len(cond) != 1 or next(iter(cond)) not in CONDITIONS:
                found.append(f"exercise {n} has an unknown check: {cond}")
            elif "typed" in cond:
                try:
                    re.compile(cond["typed"])
                except (re.error, TypeError) as e:
                    found.append(f"exercise {n}: bad pattern {cond['typed']!r} ({e})")
            elif "contains" in cond and not (isinstance(cond["contains"], list)
                                             and len(cond["contains"]) == 2):
                found.append(f'exercise {n}: "contains" needs [file, text]')
    return found


def read(name: str) -> Optional[dict]:
    """The pack called `name`, or None if there's none (or it's broken)."""
    path = _pack_files().get(name)
    if not path:
        return None
    try:
        pack = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return None if problems(pack) else pack


def available() -> List[dict]:
    """[{"name", "title", "description", "count"}] for every valid pack,
    the basics first."""
    packs = []
    for name in _pack_files():
        pack = read(name)
        if pack:
            packs.append({"name": name, "title": pack["title"],
                          "description": pack.get("description", ""),
                          "count": len(pack["exercises"])})
    packs.sort(key=lambda p: (p["name"] != "basics", p["name"]))
    return packs


def _inside(sandbox: str, relative: str) -> str:
    """A path inside the practice folder. Checks never look outside it."""
    path = os.path.normpath(os.path.join(sandbox, str(relative)))
    if path != sandbox and not path.startswith(sandbox + os.sep):
        return os.path.join(sandbox, "\0outside")
    return path


def passes(check: list, typed: str, cwd: str, sandbox: str) -> bool:
    """True if every condition holds."""
    sandbox = os.path.realpath(sandbox)
    for cond in check:
        (kind, value), = cond.items()
        if kind == "typed":
            ok = re.search(value, typed.strip()) is not None
        elif kind == "cwd":
            ok = os.path.realpath(cwd) == os.path.realpath(_inside(sandbox, value))
        elif kind == "dir":
            ok = os.path.isdir(_inside(sandbox, value))
        elif kind == "file":
            ok = os.path.isfile(_inside(sandbox, value))
        elif kind == "missing":
            ok = not os.path.lexists(_inside(sandbox, value))
        else:  # contains
            path, text = value
            try:
                with open(_inside(sandbox, path), errors="replace") as f:
                    ok = str(text) in f.read()
            except (OSError, ValueError):
                ok = False
        if not ok:
            return False
    return True
