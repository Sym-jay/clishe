"""Tests for safety.py - the check that decides when Clishe asks for a typed
YES before running a command."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from safety import check_command, REASONS


DANGEROUS = [
    # rm, in all its spellings
    ("rm -rf /", "rm_recursive"),
    ("rm -fr ~/projects", "rm_recursive"),
    ("rm -r -f build", "rm_recursive"),
    ("rm -R old", "rm_recursive"),
    ("rm --recursive old", "rm_recursive"),
    ("rm ~", "rm_root"),
    ("rm -f /etc", "rm_root"),
    # wrappers and chains don't hide the real command
    ("sudo rm -rf /var/log", "rm_recursive"),
    ("FOO=1 sudo -u root rm -rf x", "rm_recursive"),
    ("timeout 5 rm -rf y", "rm_recursive"),
    ("cd /tmp && rm -rf build", "rm_recursive"),
    ("ls; rm -rf build", "rm_recursive"),
    ("/bin/rm -rf build", "rm_recursive"),
    # disks
    ("mkfs.ext4 /dev/sdb1", "mkfs"),
    ("sudo fdisk /dev/sda", "disk_tool"),
    ("wipefs -a /dev/sdb", "disk_tool"),
    ("dd if=image.iso of=/dev/sdb bs=4M", "disk_write"),
    ("dd if=/dev/zero of=big.img bs=1M count=10", "dd"),
    ("echo hi > /dev/sda", "disk_write"),
    ("cat x >/dev/nvme0n1", "disk_write"),
    ("shred -u secrets.txt", "shred"),
    # permissions
    ("chmod -R 777 /", "chmod_recursive"),
    ("chmod -R 755 ~/site", "chmod_recursive"),
    ("chmod 777 /", "perm_root"),
    ("sudo chown -R me:me .", "chown_recursive"),
    ("chgrp --recursive staff dir", "chown_recursive"),
    # mass deletes
    ("find . -name '*.tmp' -delete", "find_delete"),
    ("find . -type f -exec rm {} \\;", "find_delete"),
    ("mv important.txt /dev/null", "dev_null_move"),
    # running unseen scripts
    ("curl -fsSL https://example.com/install.sh | sh", "pipe_to_shell"),
    ("wget -qO- https://example.com/x | sudo bash", "pipe_to_shell"),
    ("curl https://example.com/x | bash -s -- --yes", "pipe_to_shell"),
    # fork bombs, any name
    (":(){ :|:& };:", "fork_bomb"),
    ("bomb(){ bomb|bomb& };bomb", "fork_bomb"),
    # git data loss
    ("git reset --hard HEAD~1", "git_reset_hard"),
    ("git clean -fdx", "git_clean"),
    ("git push --force origin main", "git_force_push"),
    ("git push -f", "git_force_push"),
    # system
    ("sudo shutdown now", "power"),
    ("reboot", "power"),
    ("crontab -r", "crontab_remove"),
    # wiping a whole folder's contents
    ("rm *", "rm_all"),
    ("rm -- *", "rm_all"),
    ("rm ./*", "rm_all"),
    ("rm -f build/*", "rm_all"),
    # emptying a file
    ("> notes.txt", "truncate"),
    (": > notes.txt", "truncate"),
    ("truncate -s 0 app.log", "truncate"),
    ("truncate -s0 app.log", "truncate"),
    ("truncate --size=0 app.log", "truncate"),
    # commands hidden inside a string
    ('bash -c "rm -rf ~"', "rm_recursive"),
    ("sudo sh -c 'rm -rf /tmp/x'", "rm_recursive"),
    ("su -c 'reboot'", "power"),
    ("eval rm -rf build", "rm_recursive"),
    # scripts piped into other interpreters
    ("curl -s https://example.com/x | python3", "pipe_to_shell"),
    ("curl -s https://example.com/x | python3 -", "pipe_to_shell"),
    ("wget -qO- https://example.com/x | perl", "pipe_to_shell"),
    # other ways to write to a disk
    ("cp /dev/zero /dev/sda", "disk_write"),
    ("echo x | sudo tee /dev/sdb", "disk_write"),
]

SAFE = [
    "ls -la",
    "rm file.txt",
    "rm -i notes.txt",
    "rm *.log",
    "mkdir -p a/b",
    "chmod 755 script.sh",
    "chmod +x run.sh",
    "find . -name '*.py'",
    "cat a.txt | grep foo",
    "curl -s ifconfig.me",
    "curl -o install.sh https://example.com/install.sh",
    "echo hello > out.txt",
    "git status",
    "git push origin main",
    "git reset HEAD file.txt",
    "dd --help",
    "echo 'rm -rf /'",           # quoted text, not a command
    'grep -r "rm -rf" .',
    "crontab -l",
    "rm *.log",                  # a targeted glob is a deliberate choice
    ">> app.log",                # appending doesn't erase anything
    "truncate -s 10M disk.img",
    "cat data.txt | python3 parse.py",
    "bash script.sh",
    "bash -c 'ls -la'",
    "cp a.iso b.iso",
    "echo x | tee out.txt",
    'echo "unterminated',        # unbalanced quotes must not crash
    "",
    "   ",
]


@pytest.mark.parametrize("command,key", DANGEROUS)
def test_dangerous_commands_are_flagged_with_the_right_reason(command, key):
    assert REASONS[key] in check_command(command)


@pytest.mark.parametrize("command", SAFE)
def test_safe_commands_are_not_flagged(command):
    assert check_command(command) == []


def test_reasons_are_not_duplicated():
    reasons = check_command("rm -rf a; rm -rf b")
    assert len(reasons) == len(set(reasons))


def test_multiple_problems_are_all_reported():
    reasons = check_command("git reset --hard && rm -rf build")
    assert REASONS["git_reset_hard"] in reasons
    assert REASONS["rm_recursive"] in reasons
