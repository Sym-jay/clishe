"""Tests for undo.py - "undo that". Real files in a temp folder; the undo
commands are run with bash to prove they put things back."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import undo  # noqa: E402


@pytest.fixture
def here(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(undo, "_trash_command", lambda: "")
    return tmp_path


def _run(command, cwd):
    """Run like Clishe would, and return the undo record."""
    note = undo.before(command, str(cwd), home=str(cwd / "home"))
    assert note is not None, command
    subprocess.run(["bash", "-c", command], cwd=cwd, check=True)
    return undo.after(note, str(cwd))


def _undo(record, cwd):
    result = undo.plan(record)
    if result["status"] == "ok":
        subprocess.run(["bash", "-c", " && ".join(result["commands"])], cwd=cwd, check=True)
    return result


def test_mv_rename_and_back(here):
    (here / "a.txt").write_text("hi")
    record = _run("mv a.txt b.txt", here)
    assert undo.plan(record)["commands"] == ["mv b.txt a.txt"]
    _undo(record, here)
    assert (here / "a.txt").read_text() == "hi" and not (here / "b.txt").exists()


def test_mv_into_a_folder_with_a_pattern(here):
    (here / "d").mkdir()
    (here / "x.log").write_text("1")
    (here / "y.log").write_text("2")
    record = _run("mv *.log d", here)
    _undo(record, here)
    assert sorted(p.name for p in here.glob("*.log")) == ["x.log", "y.log"]


def test_mv_back_refused_when_something_new_is_there(here):
    (here / "a.txt").write_text("hi")
    record = _run("mv a.txt b.txt", here)
    (here / "a.txt").write_text("new")
    result = undo.plan(record)
    assert result["status"] == "impossible" and "something new" in result["explanation"]


def test_mv_that_replaced_a_file_says_so(here):
    (here / "a.txt").write_text("a")
    (here / "b.txt").write_text("b")
    result = undo.plan(_run("mv a.txt b.txt", here))
    assert result["status"] == "impossible"
    assert "can't be brought back" in result["explanation"]


def test_mkdir_p_removes_only_what_it_made(here):
    (here / "keep").mkdir()
    record = _run("mkdir -p keep/a/b", here)
    assert undo.plan(record)["commands"] == ["rmdir keep/a/b", "rmdir keep/a"]
    _undo(record, here)
    assert (here / "keep").is_dir() and not (here / "keep" / "a").exists()


def test_mkdir_not_removed_once_it_has_files(here):
    record = _run("mkdir notes", here)
    (here / "notes" / "todo.txt").write_text("x")
    assert undo.plan(record)["status"] == "impossible"


def test_touch_only_removes_an_empty_file(here):
    record = _run("touch new.txt", here)
    assert undo.plan(record)["commands"] == ["rm new.txt"]
    (here / "new.txt").write_text("now it has content")
    assert undo.plan(record)["status"] == "impossible"


def test_cp_removes_the_copy_but_not_after_changes(here):
    (here / "a.txt").write_text("hi")
    record = _run("cp a.txt b.txt", here)
    _undo(record, here)
    assert (here / "a.txt").exists() and not (here / "b.txt").exists()
    record = _run("cp a.txt c.txt", here)
    os.utime(here / "c.txt", (1, 1))
    assert undo.plan(record)["status"] == "impossible"


def test_cp_copy_goes_to_the_trash_when_there_is_one(here, monkeypatch):
    (here / "a.txt").write_text("hi")
    record = _run("cp a.txt b.txt", here)
    monkeypatch.setattr(undo, "_trash_command", lambda: "gio trash")
    assert undo.plan(record)["commands"] == ["gio trash b.txt"]


def test_chmod_puts_the_old_mode_back(here):
    (here / "s.sh").write_text("echo")
    os.chmod(here / "s.sh", 0o644)
    record = _run("chmod 700 s.sh", here)
    assert undo.plan(record)["commands"] == ["chmod 644 s.sh"]
    _undo(record, here)
    assert oct(os.stat(here / "s.sh").st_mode & 0o777) == "0o644"


def test_cd_goes_back(here):
    (here / "sub").mkdir()
    note = undo.before("cd sub", str(here))
    record = undo.after(note, str(here / "sub"))
    assert undo.plan(record)["commands"][0].startswith("cd ")


def test_freedesktop_trash_is_restored(here):
    """gio trash and trash-put keep files in Trash/files with a .trashinfo."""
    (here / "report.txt").write_text("important")
    note = undo.before("gio trash report.txt", str(here), home=str(here))
    trash = here / "data" / "Trash"
    (trash / "files").mkdir(parents=True)
    (trash / "info").mkdir()
    os.rename(here / "report.txt", trash / "files" / "report.txt")
    (trash / "info" / "report.txt.trashinfo").write_text(
        f"[Trash Info]\nPath={here / 'report.txt'}\nDeletionDate=2026-10-07T10:00:00\n")
    record = undo.after(note, str(here))
    _undo(record, here)
    assert (here / "report.txt").read_text() == "important"
    assert not (trash / "info" / "report.txt.trashinfo").exists()


def test_mac_trash_hidden_gives_put_back_steps(here):
    note = undo.before("trash report.txt", str(here), home=str(here))
    note["trash"]["mac"] = None   # what macOS does without Full Disk Access
    record = undo.after(note, str(here))
    result = undo.plan(record)
    assert result["status"] == "impossible" and "Put Back" in result["explanation"]


def test_package_install_suggests_removing_it(here):
    record = undo.after(undo.before("sudo apt install htop", str(here)), str(here))
    assert undo.plan(record)["commands"] == ["sudo apt remove htop"]


def test_rm_says_it_cannot_be_undone(here):
    (here / "a.txt").write_text("x")
    result = undo.plan(_run("rm a.txt", here))
    assert result["status"] == "impossible" and "Trash" in result["explanation"]


@pytest.mark.parametrize("command", ["ls -la", "mv a b | cat", "cp a b && ls", "sudo mv a b",
                                     "echo hi > f.txt", ""])
def test_not_undoable(here, command):
    assert undo.before(command, str(here)) is None


def test_only_the_last_ten_are_kept(tmp_path):
    path = tmp_path / "undo.json"
    undo.save(path, [{"command": str(i), "kind": "cd", "from": "/"} for i in range(15)])
    records = undo.load(path)
    assert len(records) == 10 and records[0]["command"] == "5"
