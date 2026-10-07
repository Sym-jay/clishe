"""
`clishe tour`: a walk through the user's own computer in plain English -
which Linux they're running, the hardware, the disk, the desktop, where
their files live and how software gets installed - with a command to try
at each stop, so they can find it all again themselves.

Everything is read locally from /etc and /proc and the environment. Paths
go through `root` so the tests can point it at a fake system.
"""
import getpass
import grp
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional


def _read(root: Path, path: str) -> str:
    try:
        return (root / path.lstrip("/")).read_text(errors="replace")
    except OSError:
        return ""


def _os_release(root: Path) -> dict:
    info = {}
    for line in _read(root, "/etc/os-release").splitlines():
        key, _, value = line.partition("=")
        if key:
            info[key.strip()] = value.strip().strip('"')
    return info


def _size(n_bytes: float) -> str:
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n_bytes < 1024 or unit == "TB":
            return f"{n_bytes:.0f} {unit}" if unit == "bytes" else f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return ""


def _duration(seconds: float) -> str:
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = [f"{days} day{'s' * (days != 1)}"] if days else []
    if hours:
        parts.append(f"{hours} hour{'s' * (hours != 1)}")
    if not days:
        parts.append(f"{minutes} minute{'s' * (minutes != 1)}")
    return ", ".join(parts)


def _is_mac(root: Path) -> bool:
    return sys.platform == "darwin" and root == Path("/")


def _sysctl(name: str) -> str:
    """macOS keeps hardware details in sysctl instead of /proc."""
    try:
        out = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=2)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _stop(title: str, facts: list, note: str, try_: list) -> dict:
    return {"title": title, "facts": [f for f in facts if f[1]], "note": note, "try": try_}


def system(root: Path) -> dict:
    if _is_mac(root):
        version = platform.mac_ver()[0]
        return _stop("Your system", [("System", f"macOS {version}".strip()),
                                     ("Kernel", f"Darwin {platform.release()}")],
                     "macOS is built on Darwin, a Unix system, so nearly every command you "
                     "learn here works the same on Linux. A few options differ (macOS has the "
                     "BSD versions of tools like ls and sed): man <command> always shows the "
                     "version on your computer.", ["sw_vers", "uname -a"])
    info = _os_release(root)
    name = info.get("PRETTY_NAME") or info.get("NAME") or "an unknown Linux"
    kernel = _read(root, "/proc/sys/kernel/osrelease").strip() or platform.release()
    based_on = info.get("ID_LIKE", "")
    note = (f"Linux itself is just the kernel ({kernel}): the part that talks to the hardware. "
            f"{info.get('NAME', 'Your distribution')} is everything built around it: the "
            "desktop, the apps and the way software is installed.")
    if based_on:
        note += f" It's based on {based_on}, so guides written for {based_on.split()[0]} mostly work here too."
    return _stop("Your Linux", [("Distribution", name), ("Kernel", kernel)],
                 note, ["cat /etc/os-release", "uname -r"])


def hardware(root: Path) -> dict:
    cpu = ""
    for line in _read(root, "/proc/cpuinfo").splitlines():
        if line.lower().startswith(("model name", "hardware", "cpu model")):
            cpu = line.split(":", 1)[1].strip()
            break
    cores = os.cpu_count() or 0
    memory = ""
    for line in _read(root, "/proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            memory = _size(int(line.split()[1]) * 1024)
            break
    if not memory and root == Path("/"):
        try:
            memory = _size(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
        except (ValueError, OSError, AttributeError):
            pass
    uptime = _read(root, "/proc/uptime").split()
    if _is_mac(root):
        cpu = cpu or _sysctl("machdep.cpu.brand_string")
        boot = re.search(r"sec = (\d+)", _sysctl("kern.boottime"))
        if boot:
            uptime = [str(time.time() - int(boot.group(1)))]
    return _stop("Your computer",
                 [("Processor", cpu), ("Cores", str(cores) if cores else ""),
                  ("Memory", memory),
                  ("On for", _duration(float(uptime[0])) if uptime else "")],
                 "Memory (RAM) is what running programs use. The system borrows unused memory "
                 "to speed things up, so 'free' memory always looks low: look at 'available' instead.",
                 ["top -l 1 | head -n 10", "sysctl -n hw.ncpu", "uptime"] if _is_mac(root)
                 else ["free -h", "nproc", "uptime"])


def disk(home: str) -> dict:
    facts = []
    for label, path in (("This computer (/)", "/"), ("Your home folder", home)):
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        line = f"{_size(usage.free)} free of {_size(usage.total)} ({usage.used * 100 // usage.total}% used)"
        if not facts or facts[-1][1] != line:
            facts.append((label, line))
    return _stop("Your disk", facts,
                 "Everything lives in one tree of folders starting at / (called 'root'). "
                 "Other disks and USB sticks appear as folders inside it, under /media on "
                 "Linux and /Volumes on a Mac.",
                 ["df -h", "du -sh ~/*"])


def desktop(env: dict) -> dict:
    name = env.get("XDG_CURRENT_DESKTOP", "").replace(":", " / ")
    if not name and sys.platform == "darwin":
        name = "macOS (Finder and the Dock)"
    session = env.get("XDG_SESSION_TYPE", "")
    shell = os.path.basename(env.get("SHELL", ""))
    kinds = {"wayland": "Wayland (the newer way of drawing windows)",
             "x11": "X11 (the older way of drawing windows)",
             "tty": "a text console, no desktop"}
    return _stop("Your desktop and shell",
                 [("Desktop", name), ("Display", kinds.get(session, session)),
                  ("Shell", shell)],
                 f"The shell is the program reading what you type in this terminal"
                 f"{f' ({shell})' if shell else ''}. The desktop is a separate program, so "
                 "you can change either one without reinstalling the whole system.",
                 ["echo $SHELL"] if sys.platform == "darwin"
                 else ["echo $SHELL", "echo $XDG_CURRENT_DESKTOP"])


# The folders every Linux system has, in plain English.
FOLDERS = [
    ("/home", "everyone's personal folders; yours is {home}"),
    ("/Users", "everyone's personal folders on a Mac; yours is {home}"),
    ("/Applications", "the apps you see in Launchpad and Finder"),
    ("/Volumes", "USB sticks and other disks, when you plug them in"),
    ("/etc", "settings for the whole system (text files you can read)"),
    ("/usr/bin", "most of the programs you run, like ls and grep"),
    ("/var/log", "logs: what the system has been doing"),
    ("/tmp", "scratch space, emptied when the computer restarts"),
    ("/dev", "your hardware, shown as files (disks, USB, terminals)"),
    ("/media", "USB sticks and other disks, when you plug them in"),
    ("/proc", "live information about running programs"),
]


def folders(root: Path, home: str) -> dict:
    facts = [(path, text.format(home=home)) for path, text in FOLDERS
             if (root / path.lstrip("/")).exists()]
    # A Mac also has an empty /home; say where the homes really are.
    if any(path == "/Users" for path, _ in facts):
        facts = [f for f in facts if f[0] != "/home"]
    return _stop("Where things live", facts,
                 "Your own files belong in your home folder (~ is short for it). "
                 "You can look around the rest, but changing it needs sudo.",
                 ["ls /", "cd ~", "ls /etc"])


def software(family: List[str]) -> dict:
    from knowledge import _installer
    manager, template = _installer(family)
    facts = [("Package manager", manager or "")]
    for tool, what in (("flatpak", "Flatpak (app store apps, from Flathub)"),
                       ("snap", "Snap (Ubuntu's app store format)")):
        if shutil.which(tool):
            facts.append(("Also", what))
    note = ("Linux installs software from trusted repositories instead of downloading "
            "installers from websites. The package manager fetches it, checks it, and "
            "keeps it updated.")
    if manager == "brew":
        if not shutil.which("brew"):
            facts = [("Package manager", "Homebrew isn't installed yet (https://brew.sh)")]
        note = ("On a Mac, apps come from the App Store or the web, and command-line tools "
                "come from Homebrew, which works like a Linux package manager.")
    try_ = [template.format("htop")] if template else []
    return _stop("Installing software", facts, note, try_)


def you(env: dict, groups: Optional[List[str]] = None) -> dict:
    user = env.get("USER") or getpass.getuser()
    groups = list(groups or [])
    for gid in ([] if groups else os.getgroups()):
        try:
            groups.append(grp.getgrgid(gid).gr_name)
        except KeyError:
            pass
    admin = bool({"sudo", "wheel", "admin"} & set(groups))
    note = ("You can use sudo to do things that change the whole system, like installing "
            "software. It asks for your password, and that's a good moment to stop and "
            "read the command." if admin else
            "You're not in the sudo or wheel group, so system-wide changes need someone "
            "with admin rights.")
    return _stop("You", [("User name", user), ("Admin (sudo)", "yes" if admin else "no")],
                 note, ["whoami", "groups"])


def tour(root: Optional[Path] = None, env: Optional[dict] = None) -> List[dict]:
    root = Path(root or "/")
    env = dict(os.environ if env is None else env)
    home = env.get("HOME", str(Path.home()))
    from config import detect_distro_family
    family = detect_distro_family() if root == Path("/") else (
        [_os_release(root).get("ID", "")] + _os_release(root).get("ID_LIKE", "").split())
    return [system(root), hardware(root), disk(home), desktop(env),
            folders(root, home), software(family), you(env)]
