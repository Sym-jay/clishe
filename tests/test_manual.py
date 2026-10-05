"""Tests for manual.py - reading the man pages installed on this computer.
Sample text is used instead of real man pages, so results don't depend on
the machine running the tests."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import manual  # noqa: E402
from manual import flag_help, summary  # noqa: E402

TAR_MAN = """TAR(1)                         GNU TAR Manual                         TAR(1)

NAME
       tar - an archiving utility

OPTIONS
   Operation mode
       -x, --extract, --get
              Extract files from an archive.  Arguments are optional.

       -z, --gzip, --gunzip, --ungzip
              Filter the archive through gzip(1).

       -v, --verbose
              Verbosely list files processed.

       -f, --file=ARCHIVE
              Use archive file or device ARCHIVE.
"""

LS_MAN = """NAME
       ls - list directory contents

DESCRIPTION
       -a, --all
              do not ignore entries starting with .

       -l     use a long listing format

       --block-size=SIZE
              with -l, scale sizes by SIZE when printing them; e.g.,
              '--block-size=M'; see SIZE format below
"""

HELP_TEXT = """Usage: tool [OPTION]...
  -q, --quiet     print nothing
  -n NUM          stop after NUM lines
"""


def test_summary_from_name_section():
    assert summary(TAR_MAN) == "tar - an archiving utility"
    assert summary(HELP_TEXT) == ""


@pytest.mark.parametrize("text,flag,expected", [
    (TAR_MAN, "-x", "Extract files from an archive."),
    (TAR_MAN, "--extract", "Extract files from an archive."),
    (TAR_MAN, "--file", "Use archive file or device ARCHIVE."),
    (LS_MAN, "-l", "use a long listing format"),
    (LS_MAN, "-a", "do not ignore entries starting with ."),
    (LS_MAN, "--block-size", "with -l, scale sizes by SIZE when printing them; e.g., "
                             "'--block-size=M'; see SIZE format below"),
    (HELP_TEXT, "-q", "print nothing"),
    (HELP_TEXT, "-n", "stop after NUM lines"),
    (TAR_MAN, "-k", ""),
])
def test_flag_help(text, flag, expected):
    assert flag_help(text, flag) == expected


def _fake_manuals(monkeypatch, pages):
    monkeypatch.setattr(manual, "read_manual",
                        lambda name: (pages[name], f"man {name}") if name in pages else ("", ""))


def test_combined_short_flags_are_looked_up_one_by_one(monkeypatch):
    _fake_manuals(monkeypatch, {"tar": TAR_MAN})
    text = manual.explain_from_manual("tar -xzvf backup.tgz")
    assert text.splitlines()[0] == "tar - an archiving utility"
    assert "  -x  Extract files from an archive." in text
    assert "  -f  Use archive file or device ARCHIVE." in text
    assert text.endswith("Full details: man tar")


def test_every_command_in_a_pipeline_is_checked(monkeypatch):
    _fake_manuals(monkeypatch, {"tar": TAR_MAN, "ls": LS_MAN})
    notes = manual.check_flags("sudo ls -la | tar -xq")
    assert [n["name"] for n in notes] == ["ls", "tar"]
    assert notes[0]["flags"] == [("-l", "use a long listing format"),
                                 ("-a", "do not ignore entries starting with .")]
    assert notes[1]["flags"][1] == ("-q", "")  # not in the manual


def test_no_manual_means_no_explanation(monkeypatch):
    _fake_manuals(monkeypatch, {})
    assert manual.explain_from_manual("mytool -x") is None


def test_overstrike_and_colours_are_removed():
    assert manual._clean("N\bNA\bAM\bME\bE \x1b[1mbold\x1b[0m") == "NAME bold"


@pytest.mark.parametrize("name", ["reboot", "mkfs.ext4", "rm", "dd", "../evil", "a b"])
def test_risky_or_odd_names_are_never_run_for_help(name, monkeypatch):
    import subprocess
    manual.read_manual.cache_clear()
    monkeypatch.setattr(manual.shutil, "which", lambda n: "/usr/bin/" + n if n != "man" else None)
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or None)
    assert manual.read_manual(name) == ("", "")
    assert calls == []
    manual.read_manual.cache_clear()
