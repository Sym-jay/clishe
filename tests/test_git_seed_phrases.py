"""Exercise new offline Git suggestions in an isolated repository."""

import json
import shlex
import subprocess
from pathlib import Path


SEED = json.loads((Path(__file__).parents[1] / "seed_kb.json").read_text())


def test_offline_git_suggestions_preserve_work(tmp_path):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout

    def suggestion(phrase, **values):
        command = SEED[phrase]
        for name, value in values.items():
            command = command.replace(f"<{name}>", shlex.quote(value))
        assert "<" not in command
        return subprocess.run(
            command, shell=True, cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout

    git("init", "-b", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "notes.txt").write_text("first\n")
    suggestion("save my work", message="Initial fixture")
    assert suggestion("which branch am i on").strip() == "main"
    suggestion("create a git branch", branch="feature")
    assert suggestion("which branch am i on").strip() == "feature"
    (tmp_path / "notes.txt").write_text("second\n")
    assert "+second" in suggestion("what did i change")
    suggestion("stage a file", file="notes.txt")
    assert "+second" in suggestion("show staged changes")
    suggestion("save my work", message="Second fixture")
    assert "Second fixture" in suggestion("show recent commits")
    assert "Second fixture" in suggestion("show the last commit")
    suggestion("undo my last commit")
    assert (tmp_path / "notes.txt").read_text() == "second\n"
    assert "+second" in suggestion("show staged changes")
    assert "Initial fixture" in git("log", "-1", "--format=%s")
