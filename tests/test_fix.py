"""Tests for "fix that": fix.py's offline rules and the AI fallback."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fix import offline_fix  # noqa: E402


@pytest.fixture
def folder(tmp_path):
    (tmp_path / "Documents").mkdir()
    (tmp_path / "photos").mkdir()
    (tmp_path / "notes.txt").write_text("hi")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("git", "ls", "python3", "grep"):
        (bin_dir / name).write_text("")
    return tmp_path


def _fix(folder, command, error):
    return offline_fix(command, error, cwd=str(folder), path_dirs=[str(folder / "bin")])


@pytest.mark.parametrize("command,error,fixed", [
    ("gti status", "bash: gti: command not found", "git status"),
    ("sl", "bash: sl: command not found", "ls"),
    ("pyhton3 x.py", "bash: pyhton3: command not found", "python3 x.py"),
    ("cd Documnets", "bash: cd: Documnets: No such file or directory", "cd Documents"),
    ("cat notse.txt", "cat: notse.txt: No such file or directory", "cat notes.txt"),
    ("apt install htop", "E: Could not open lock file - open (13: Permission denied)\n"
                         "E: Unable to acquire the dpkg frontend lock, are you root?",
     "sudo apt install htop"),
    ("systemctl restart nginx", "Failed: Access denied", "sudo systemctl restart nginx"),
    ("./backup.sh", "bash: ./backup.sh: Permission denied", "chmod +x backup.sh && ./backup.sh"),
    ("cp photos backup", "cp: -r not specified; omitting directory 'photos'", "cp -r photos backup"),
    ("cat photos", "cat: photos: Is a directory", "ls photos"),
    ("sudo apt install vscode", "E: Unable to locate package vscode",
     "sudo apt update && sudo apt install vscode"),
])
def test_offline_fixes(folder, command, error, fixed):
    assert _fix(folder, command, error)["command"] == fixed


def test_never_guesses_a_different_file_to_delete(folder):
    result = _fix(folder, "rm notse.txt", "rm: cannot remove 'notse.txt': No such file or directory")
    assert result["command"] == ""
    assert "notes.txt" in result["explanation"]


def test_ssh_key_errors_get_advice_not_sudo(folder):
    result = _fix(folder, "git push", "git@github.com: Permission denied (publickey).")
    assert result["command"] == ""
    assert "SSH key" in result["explanation"]


def test_nothing_close(folder):
    result = _fix(folder, "cd nowhere", "bash: cd: nowhere: No such file or directory")
    assert result["command"] == "" and "ls" in result["explanation"]
    assert _fix(folder, "", "anything") is None
    assert _fix(folder, "weird", "something odd happened") is None


# ---------- AI fallback ----------

@pytest.fixture
def brain(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import manual
    monkeypatch.setattr(manual, "read_manual", lambda name: ("", ""))
    import importlib
    import clishe_brain
    importlib.reload(clishe_brain)
    return clishe_brain.ClisheBrain()


class _FakeProvider:
    name = "local"

    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def fix_command(self, command, error):
        self.calls += 1
        return self.answer


def test_offline_fix_wins_without_asking_the_ai(brain, monkeypatch):
    import clishe_brain
    fake = _FakeProvider({"explanation": "x", "command": "y"})
    monkeypatch.setattr(clishe_brain, "build_provider_chain", lambda config: [fake])
    result = brain.fix("./run.sh", "bash: ./run.sh: Permission denied")
    assert result["provider"] == "offline"
    assert fake.calls == 0


def test_ai_is_asked_when_no_rule_fits(brain, monkeypatch):
    import clishe_brain
    fake = _FakeProvider({"explanation": "The port is in use.", "command": "ss -tlnp"})
    monkeypatch.setattr(clishe_brain, "build_provider_chain", lambda config: [fake])
    result = brain.fix("python3 -m http.server 80", "OSError: [Errno 98] Address already in use")
    assert result == {"status": "ok", "explanation": "The port is in use.", "command": "ss -tlnp",
                      "provider": "local", "unverified": []}


def test_no_rule_and_no_ai(brain, monkeypatch):
    import clishe_brain
    monkeypatch.setattr(clishe_brain, "build_provider_chain", lambda config: [])
    assert brain.fix("weird", "something odd happened") == {"status": "none"}


def test_provider_fix_command_uses_the_shared_prompt():
    from providers.local_provider import LocalProvider

    class _Resp:
        def __init__(self, body): self.body = body
        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    captured = {}

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data)
        content = '{"explanation": "No such folder.", "command": null}'
        return _Resp(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    provider = LocalProvider({"host": "http://localhost:8080", "model": "m"})
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert provider.fix_command("cd x", "cd: x: No such file") == \
            {"explanation": "No such folder.", "command": ""}
    system, user = captured["payload"]["messages"]
    assert "Never suggest a command that deletes" in system["content"]
    assert "Command: cd x" in user["content"] and "No such file" in user["content"]
