"""Tests for tldr.py - summaries, examples and phrase matching from the
bundled tldr-pages data (tldr.json.gz)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tldr  # noqa: E402


@pytest.fixture
def linux(monkeypatch):
    """Linux pages, with every command treated as installed, so results
    don't depend on the machine running the tests."""
    monkeypatch.setattr(tldr, "_platforms", lambda: ("linux", "common"))
    monkeypatch.setattr(tldr.shutil, "which", lambda name: f"/usr/bin/{name}")
    tldr._installed_examples.cache_clear()
    yield
    tldr._installed_examples.cache_clear()


def test_data_is_bundled_with_credit():
    data = tldr._data()
    assert data["license"].startswith("CC BY 4.0")
    assert data["source"] == "https://github.com/tldr-pages/tldr"
    assert len(data["common"]) > 4000 and len(data["linux"]) > 1500


def test_summary_and_examples(linux):
    assert tldr.summary("tar") == "Archiving utility."
    assert tldr.summary("rsync").endswith("by default using SSH.")
    assert tldr.summary("not-a-command") == ""
    what, command = tldr.examples("tar", 1)[0]
    assert what == "Create an archive and write it to a file"   # "[c]reate" cleaned
    assert command.startswith("tar cf <path/to/target.tar>")


@pytest.mark.parametrize("tldr_command,clishe", [
    ("tar xf {{path/to/source.tar}} {{[-C|--directory]}} {{path/to/directory}}",
     "tar xf <source file> -C <directory>"),
    ("cp {{path/to/file1 path/to/file2 ...}} {{path/to/target_directory}}", "cp <file> <target directory>"),
    ("curl {{https://example.com}} --output {{path/to/file}}", "curl <url> --output <file>"),
    ("head -n {{5}} {{path/to/file}}", "head -n <number> <file>"),
    ("ln -s /{{path/to/file_or_directory}} {{path/to/symlink}}", "ln -s <file or directory> <symlink>"),
    ('grep "{{*.html}}" {{path/to/file}}', 'grep "<pattern>" <file>'),
])
def test_template_uses_clishe_placeholders(tldr_command, clishe):
    assert tldr.template(tldr_command) == clishe


@pytest.mark.parametrize("said,command", [
    ("extract a tar file", "tar xvf <source file>"),
    ("count words in a file", "wc -w <file>"),
    ("download a file from a url", "wget <url>"),
    ("show the first 10 lines of a file", "head <file>"),
    ("change the owner of a file", "sudo chown <user> <file or directory>"),
    ("create a symbolic link", "ln -s <file or directory> <symlink>"),
    ("clone a git repository", "git clone <url>"),
])
def test_matches(linux, said, command):
    found = tldr.match(said)
    assert found and found[1] == command


@pytest.mark.parametrize("said", [
    "make a file executable",       # once matched a C compiler
    "show open ports",              # once matched a port scanner
    "kill a process by name",       # once matched a memory-leak tool
    "what is my ip",
    "make me a sandwich",
    "delete my photos",
    "",
])
def test_no_match_rather_than_a_wrong_one(linux, said):
    assert tldr.match(said) is None


def test_only_installed_commands_are_offered(monkeypatch):
    monkeypatch.setattr(tldr, "_platforms", lambda: ("linux", "common"))
    monkeypatch.setattr(tldr.shutil, "which", lambda name: None)
    tldr._installed_examples.cache_clear()
    try:
        assert tldr.match("count words in a file") is None
    finally:
        tldr._installed_examples.cache_clear()
