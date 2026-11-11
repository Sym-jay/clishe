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
    ("git push origin main", " ! [rejected]        main -> main (fetch first)\n"
                             "error: failed to push some refs",
     "git pull --rebase && git push origin main"),
    ("git push", " ! [rejected]        main -> main (non-fast-forward)",
     "git pull --rebase && git push"),
    ("git commit -m 'first'", "Author identity unknown\n\n*** Please tell me who you are.",
     "git config --global user.name <your name> && git config --global user.email <your email>"),
    ("pip install requests", "error: externally-managed-environment",
     "python3 -m venv .venv && . .venv/bin/activate && pip install requests"),
    ("python3 -m pip install flask gunicorn", "error: externally-managed-environment",
     "python3 -m venv .venv && . .venv/bin/activate && pip install flask gunicorn"),
    ("cd Documents/plan.txt", "bash: cd: Documents/plan.txt: Not a directory", "cd Documents"),
    ("cd Documents/plan.txt/old", "bash: cd: Documents/plan.txt/old: Not a directory",
     "cd Documents"),
])
def test_offline_fixes(folder, command, error, fixed):
    (folder / "Documents" / "plan.txt").write_text("")
    assert _fix(folder, command, error)["command"] == fixed


def test_port_in_use_lists_the_ports(folder, monkeypatch):
    import fix
    error = "OSError: [Errno 98] Address already in use"
    monkeypatch.setattr(fix.sys, "platform", "linux")
    assert _fix(folder, "python3 -m http.server 8000", error)["command"] == "ss -tlnp"
    monkeypatch.setattr(fix.sys, "platform", "darwin")
    assert _fix(folder, "python3 -m http.server 8000", error)["command"] == \
        "lsof -nP -iTCP -sTCP:LISTEN"


def test_cd_into_a_file_here_gets_advice(folder):
    result = _fix(folder, "cd notes.txt", "bash: cd: notes.txt: Not a directory")
    assert result["command"] == "" and "already in" in result["explanation"]


def test_new_rules_stay_out_of_the_way(folder):
    # Other git and pip failures aren't these rules' business.
    assert _fix(folder, "git pull", "fatal: not a git repository")["command"] == ""
    assert _fix(folder, "pip list", "error: externally-managed-environment")["command"] == ""
    assert _fix(folder, "ls notes.txt/x", "ls: cannot access 'notes.txt/x': Not a directory"
                )["command"] == ""


def test_offline_fixes_never_delete(folder):
    """Rule outputs go through the same safety check as everything else, but
    an offline rule should never even suggest deleting anything."""
    from safety import check_command
    cases = [("git push", "(fetch first)"), ("git commit", "Please tell me who you are"),
             ("pip install x", "externally-managed-environment"),
             ("node app.js", "Error: listen EADDRINUSE: address already in use :::3000"),
             ("cd Documents/plan.txt", "Not a directory")]
    (folder / "Documents" / "plan.txt").write_text("")
    for command, error in cases:
        fixed = _fix(folder, command, error)["command"]
        assert fixed and not check_command(fixed), (command, fixed)


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
    result = clishe_brain.fix_command("./run.sh", "bash: ./run.sh: Permission denied")
    assert result["provider"] == "offline"
    assert fake.calls == 0


def test_ai_is_asked_when_no_rule_fits(brain, monkeypatch):
    import clishe_brain
    fake = _FakeProvider({"explanation": "The disk is full.", "command": "df -h"})
    monkeypatch.setattr(clishe_brain, "build_provider_chain", lambda config: [fake])
    result = clishe_brain.fix_command("weird", "something odd happened")
    assert result == {"status": "ok", "explanation": "The disk is full.", "command": "df -h",
                      "provider": "local", "unverified": []}


def test_no_rule_and_no_ai(brain, monkeypatch):
    import clishe_brain
    monkeypatch.setattr(clishe_brain, "build_provider_chain", lambda config: [])
    assert clishe_brain.fix_command("weird", "something odd happened") == {"status": "none"}


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
