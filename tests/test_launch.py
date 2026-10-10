"""Tests for launch.py - the `clishe` command of the pip/pipx install.
os.execv is faked, so nothing is actually started."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import launch  # noqa: E402


def test_runs_the_bundled_script_with_bash(monkeypatch):
    calls = []
    monkeypatch.setattr(launch.shutil, "which", lambda name: "/bin/bash")
    monkeypatch.setattr(launch.os, "execv", lambda path, argv: calls.append((path, argv)))
    monkeypatch.setattr(sys, "argv", ["clishe", "explain", "ls -la"])
    launch.main()
    path, argv = calls[0]
    script = Path(launch.__file__).resolve().parent / "clishe.sh"
    assert path == "/bin/bash"
    assert argv == ["/bin/bash", str(script), "explain", "ls -la"]
    assert script.exists()


def test_says_so_when_bash_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(launch.shutil, "which", lambda name: None)
    monkeypatch.setattr(launch.os, "execv", lambda *a: (_ for _ in ()).throw(AssertionError))
    assert launch.main() == 1
    assert "needs bash" in capsys.readouterr().err
