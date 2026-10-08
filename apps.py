"""
"How do I install Spotify?": the right way to get a desktop app on this
computer, from an offline list (apps.json).

Order of preference:
  1. this distro's own package, when it's certain to be in the official
     repositories (apt/dnf/pacman) - updated with the rest of the system;
  2. Flathub (flatpak), which works on any distro - with the one-time
     Flatpak setup for this distro if it isn't set up yet;
  3. on a Mac, the Homebrew cask.
Command-line tools (htop, tree...) use knowledge.missing_program_hint.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

APPS_FILE = Path(__file__).resolve().parent / "apps.json"
FLATHUB_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"

_NATIVE = {"apt": "sudo apt install {}", "dnf": "sudo dnf install {}",
           "pacman": "sudo pacman -S {}"}
_FLATPAK_PACKAGE = {"apt": "sudo apt install flatpak", "dnf": "sudo dnf install flatpak",
                    "pacman": "sudo pacman -S flatpak", "zypper": "sudo zypper install flatpak",
                    "apk": "sudo apk add flatpak"}
# "how do I install spotify?", "install vs code", "get vlc", "download the zoom app"
_ASK = re.compile(r"^(?:how (?:do i|do you|to|can i) )?(?:install|get|download)\s+"
                  r"(?:the\s+)?(.+?)(?:\s+app(?:lication)?)?(?:\s+on (?:linux|my (?:computer|laptop|mac)))?\??$",
                  re.IGNORECASE)


def load() -> List[dict]:
    try:
        return json.loads(APPS_FILE.read_text()).get("apps", [])
    except (OSError, ValueError):
        return []


def wanted(text: str) -> Optional[str]:
    """The app someone is asking to install, or None if it isn't that kind
    of question."""
    m = _ASK.match((text or "").strip())
    return m.group(1).strip().lower() if m else None


def find(name: str) -> Optional[dict]:
    name = (name or "").strip().lower()
    for app in load():
        if name == app["name"].lower() or name in app.get("aliases", []):
            return app
    return None


def _flathub_ready() -> bool:
    """Flatpak is installed and knows about Flathub."""
    if not shutil.which("flatpak"):
        return False
    try:
        out = subprocess.run(["flatpak", "remotes", "--columns=name"], capture_output=True,
                             text=True, timeout=5)
        return "flathub" in out.stdout.split()
    except (OSError, subprocess.SubprocessError):
        return False


def tool_plan(name: str, family: List[str]) -> Optional[dict]:
    """The same answer for a well-known command-line tool (htop, tree...)."""
    from knowledge import POPULAR_PROGRAMS, _PACKAGE_NAMES, _installer
    if name not in POPULAR_PROGRAMS:
        return None
    if shutil.which(name):
        return {"app": name, "installed": True}
    manager, template = _installer(family)
    if not template:
        return None
    names = _PACKAGE_NAMES.get(name, {})
    package = names.get(manager) or names.get("*") or name
    return {"app": name, "command": template.format(package), "setup": [], "others": [],
            "how": f"{name} is a command-line program from your package manager ({manager})."}


def plan(app: dict, family: List[str], mac: Optional[bool] = None,
         flathub: Optional[bool] = None) -> dict:
    """{"app", "command", "how", "setup": [...], "others": [...]}: the best way
    to install `app` here. `setup` are one-time commands to run first."""
    mac = sys.platform == "darwin" if mac is None else mac
    from knowledge import _installer
    manager = _installer(family)[0]
    name = app["name"]

    if mac:
        if app.get("brew"):
            how = f"{name} comes from Homebrew, which keeps it updated."
            if not shutil.which("brew"):
                how += " Homebrew isn't installed yet: get it from https://brew.sh first."
            return {"app": name, "command": f"brew install --cask {app['brew']}",
                    "how": how, "setup": [], "others": []}
        return {"app": name, "command": "", "setup": [], "others": [],
                "how": f"Download {name} from its website, or look for it in the App Store."}

    flathub_cmd = f"flatpak install flathub {app['flathub']}" if app.get("flathub") else ""
    native_cmd = _NATIVE[manager].format(app[manager]) if manager in _NATIVE and app.get(manager) else ""
    flathub = _flathub_ready() if flathub is None else flathub

    if native_cmd:
        return {"app": name, "command": native_cmd, "setup": [],
                "how": f"{name} is in your system's own software list ({manager}), so it "
                       "updates along with everything else.",
                "others": [flathub_cmd] if flathub_cmd else []}
    if flathub_cmd:
        setup = []
        if not flathub:
            if not shutil.which("flatpak") and manager in _FLATPAK_PACKAGE:
                setup.append(_FLATPAK_PACKAGE.get(manager))
            setup.append(f"flatpak remote-add --if-not-exists flathub {FLATHUB_REPO}")
        return {"app": name, "command": flathub_cmd, "setup": setup, "others": [],
                "how": f"{name} isn't in your system's own software list, but Flathub has it. "
                       "Flathub apps work on any Linux and update with 'flatpak update'."}
    return {"app": name, "command": "", "setup": [], "others": [],
            "how": f"I don't know a package for {name} here. Look on its website for a Linux download."}
