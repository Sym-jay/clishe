"""Tests for breakdown.py - drawing a command with each part labelled.
Man pages are stubbed with sample GNU text, so results don't depend on the
machine running the tests."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import breakdown  # noqa: E402
import manual  # noqa: E402

FIND_MAN = """NAME
       find - search for files in a directory hierarchy

OPTIONS
       -size n[cwbkMG]
              File uses less than, more than or exactly n units of space.
"""


@pytest.fixture(autouse=True)
def manuals(monkeypatch):
    pages = {"find": FIND_MAN}
    monkeypatch.setattr(manual, "read_manual",
                        lambda name: (pages[name], f"man {name}") if name in pages else ("", ""))


def _render(command, width=80):
    result = breakdown.draw(command, width)
    if result is None:
        return None
    return [result["command"]] + [tree + label for tree, label in result["lines"]]


def test_find_is_drawn_with_each_part_labelled():
    assert _render("find . -type f -size +100M") == [
        "find  .  -type f  -size +100M",
        "│     │  │        └─ bigger than 100M",
        "│     │  └─ only files, not folders",
        "│     └─ this folder",
        "└─ search for files in a directory hierarchy",
    ]


def test_options_written_together_get_a_line_each():
    lines = _render("tar -xzvf backup.tgz")
    assert lines[0] == "tar  -xzvf  backup.tgz"
    assert lines[1] == "│    ├─ -x  extract an archive"
    assert lines[4].startswith("│    └─ -f  specify the archive filename")
    assert lines[5] == "└─ archives files together, optionally with compression"


def test_placeholders_stay_whole():
    lines = _render("tar -czvf <archive name>.tar.gz <folder>")
    assert lines[0] == "tar  -czvf  <archive name>.tar.gz  <folder>"
    assert "└─ the folder you choose" in lines[1]


def test_sudo_and_subcommands():
    lines = _render("sudo apt install htop")
    assert lines[-1] == "└─ as the administrator (asks for your password)"
    assert any(line.endswith("└─ install a package") for line in lines)


@pytest.mark.parametrize("command", [
    "du -sh * | sort -h",        # pipes
    "echo hi > out.txt",         # redirects
    "cd x && ls",
    "echo $(date)",
    "mystery-tool --flag",       # nothing to say about it
    "",
])
def test_no_breakdown_when_it_would_not_help(command):
    assert breakdown.draw(command) is None


def test_no_breakdown_when_too_wide():
    assert breakdown.draw("find . -type f -size +100M", width=30) is None


@pytest.mark.parametrize("text,expected", [
    ("ls - list directory contents", "list directory contents"),
    ("ls – list directory contents", "list directory contents"),
    ("Install a package, e.g. apt install htop", "install a package"),
    ("Shows how much disk space files/directories are using.",
     "shows how much disk space files/directories are using"),
    ("File uses less than, more than or exactly n units of space, rounding up and more words here",
     "file uses less than, more than or exactly n units of…"),
    ("Archives (bundles) files together, optionally with compression.",
     "archives files together, optionally with compression"),
    ("(The lowercase letter “ell”.) List files in the long format, as described below.",
     "list files in the long format"),
])
def test_short_labels(text, expected):
    assert breakdown._short(text) == expected
