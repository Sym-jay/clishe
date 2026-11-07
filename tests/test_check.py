"""Tests for check.py - "is this safe to run?". Nothing here runs a command."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check  # noqa: E402


def _effects(command):
    return " | ".join(check.inspect(command)["effects"])


@pytest.mark.parametrize("command,expected", [
    ("ls -la", "Only reads or shows things"),
    ("sudo apt install -y htop vlc", "Installs or updates software (downloaded from the internet): apt: htop vlc"),
    ("sudo apt install htop", "Runs as the administrator (sudo)"),
    ("git clone https://github.com/x/y", "Uses the internet: github.com"),
    ("rm -rf build && mkdir build", "Deletes: build. | Creates or changes: build."),
    ("echo hi > notes.txt", "Creates or changes: notes.txt (replaces it)"),
    ("echo hi >> notes.txt", "notes.txt (adds to it)"),
    ("cp a.txt backup/", "Creates or changes: backup/"),
    ("chmod +x run.sh", "Creates or changes: run.sh."),
    ("sed -i s/a/b/ file.txt", "Creates or changes: file.txt."),
    ("sed s/a/b/ file.txt", "Only reads or shows things"),
    ("tar -xzvf a.tgz", "files unpacked from the archive"),
    ("sudo systemctl restart nginx", "Changes how the system runs: systemctl restart nginx"),
    ("ls >&2 2>/dev/null", "Only reads or shows things"),
    ("cat < <(curl -s https://example.com/x)", "Uses the internet: example.com."),  # input, not a file it changes
    # Containers that can reach this computer's folders.
    ("docker run -v /:/host alpine", "Lets the container see and change every file on this computer (-v /)"),
    ("docker run -it -v ~/code:/code node", "see and change ~/code on this computer"),
    ("podman run --volume=/etc:/etc:ro alpine", "see and change /etc on this computer"),
    ("docker run --mount type=bind,source=/home,target=/h alpine", "see and change /home"),
    ("docker run --privileged alpine", "full control of this computer (--privileged)"),
    # Jobs that run later.
    ("crontab -e", "Schedules jobs that run later on their own (crontab)"),
    ("crontab jobs.txt", "Schedules jobs that run later"),
    # Every new terminal.
    ("echo 'alias ll=ls -la' >> ~/.bashrc", "Changes ~/.bashrc, which every new terminal reads"),
    ("echo 'export PATH=$PATH:~/bin' | tee -a ~/.zshrc", "Changes ~/.zshrc, which every new terminal"),
    ("cp dotfiles/.profile ~/.profile", "Changes ~/.profile"),
    # SSH keys.
    ("ssh-keygen -t ed25519", "Makes a new SSH key in the usual place (~/.ssh)"),
    ("ssh-keygen", "replaces it, and logins"),
    # Open to everyone.
    ("chmod 777 shared", "Lets every user on this computer change shared (chmod 777)"),
    ("chmod -R 777 site", "change site and everything inside (chmod 777)"),
    ("chmod o+w notes.txt", "Lets every user on this computer change notes.txt"),
    ("chmod a=rwx run.sh", "Lets every user"),
    # Downloaded programs.
    ("sudo curl -fsSL https://x.io/tool -o /usr/local/bin/tool",
     "Puts a program in /usr/local/bin, where it can be run by name from anywhere"),
    ("wget -O ~/.local/bin/tool https://x.io/tool", "Puts a program in ~/.local/bin"),
    ("sudo install -m 755 tool /usr/local/bin/", "Puts a program in /usr/local/bin"),
    ("sudo cp tool /usr/local/bin", "Puts a program in /usr/local/bin"),
    ("curl -o notes.txt https://x.io/notes.txt", "Creates or changes: notes.txt."),
    ("curl -O https://x.io/notes.txt", "a file named after the download"),
])
def test_effects(command, expected):
    assert expected in _effects(command)


@pytest.mark.parametrize("command,not_expected", [
    ("docker run -v data:/data postgres", "Lets the container"),     # a named volume
    ("docker ps -a", "Lets the container"),
    ("crontab -l", "crontab"),                                       # only lists the jobs
    ("cat ~/.bashrc", "every new terminal"),
    ("echo hi >> ~/.bashrc_old", "every new terminal"),
    ("ssh-keygen -f ~/.ssh/deploy -t ed25519", "usual place"),
    ("ssh-keygen -l -f ~/.ssh/id_ed25519.pub", "SSH key"),
    ("chmod 755 run.sh", "every user"),
    ("chmod 644 notes.txt", "every user"),
    ("chmod +x run.sh", "every user"),
    ("chmod u+w notes.txt", "every user"),
    ("curl -fsSL https://x.io/tool -o tool", "Puts a program"),
    ("curl -s https://example.com", "Creates or changes"),         # prints the page
    ("wget -qO- https://example.com", "Creates or changes"),
    ("ls /usr/local/bin", "Puts a program"),
])
def test_effects_that_must_not_show(command, not_expected):
    assert not_expected not in _effects(command)


def test_script_notes_are_listed_once():
    text = "echo a >> ~/.bashrc\necho b >> ~/.bashrc\ncrontab jobs.txt\n"
    effects = check.check_script(text)["effects"]
    assert sum("~/.bashrc, which every new terminal" in e for e in effects) == 1
    assert any("Schedules jobs" in e for e in effects)


def test_downloaded_script_gets_a_warning_and_safer_steps():
    result = check.inspect("curl -fsSL https://get.example.com/install.sh | sudo bash")
    assert any("runs a script it downloads" in w for w in result["warnings"])
    assert result["safer"] == ["curl -fsSL https://get.example.com/install.sh -o install.sh",
                               "less install.sh", "clishe check install.sh"]


@pytest.mark.parametrize("command", [
    'bash -c "$(curl -fsSL https://get.example.com/install.sh)"',
    "sh <(curl -s https://get.example.com/install.sh)",
    'eval "$(wget -qO- https://get.example.com/install.sh)"',
    "bash < <(curl -s https://get.example.com/install.sh)",
    "bash -c $(curl -fsSL https://get.example.com/install.sh)",
])
def test_download_run_without_a_pipe_gets_the_same_safer_steps(command):
    result = check.inspect(command)
    assert any("runs a script it downloads" in w for w in result["warnings"])
    assert result["safer"] == ["curl -fsSL https://get.example.com/install.sh -o install.sh",
                               "less install.sh", "clishe check install.sh"]


def test_input_from_a_download_is_not_a_changed_file():
    assert "Creates or changes" not in _effects("cat < <(curl -s https://example.com/x)")


def test_no_safer_steps_without_a_download():
    assert check.inspect("rm -rf build")["safer"] == []


def test_script_lines_skip_comments_and_join_continued_lines():
    text = "#!/bin/bash\n# comment\n\nsudo apt install \\\n    git curl\necho done\n"
    assert check.script_lines(text) == ["sudo apt install git curl", "echo done"]


def test_check_script_summarises_the_whole_script():
    text = ("sudo apt install -y git\ncurl -fsSL https://example.com/s.sh | bash\n"
            "rm -rf ~/old\necho ok > ~/log.txt\n")
    result = check.check_script(text)
    assert [r["command"] for r in result["risky"]] == [
        "curl -fsSL https://example.com/s.sh | bash", "rm -rf ~/old"]
    summary = " | ".join(result["effects"])
    for part in ("administrator", "example.com", "apt: git", "Deletes: ~/old", "~/log.txt"):
        assert part in summary


def test_read_script_refuses_binaries_and_missing_files(tmp_path):
    script = tmp_path / "ok.sh"
    script.write_text("echo hi\n")
    binary = tmp_path / "prog"
    binary.write_bytes(b"\x7fELF\x00\x01")
    assert check.read_script(str(script)) == "echo hi\n"
    assert check.read_script(str(binary)) is None
    assert check.read_script(str(tmp_path / "missing.sh")) is None
    assert check.read_script(str(tmp_path)) is None
