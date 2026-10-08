"""Tests for apps.py - "how do I install Spotify?". No package manager or
Flatpak is ever run: the system is faked."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import apps  # noqa: E402

KEYS = {"name", "aliases", "flathub", "brew", "apt", "dnf", "pacman"}


def test_app_list_is_tidy():
    seen = {}
    for app in apps.load():
        assert set(app) <= KEYS, f"{app['name']}: unknown keys {set(app) - KEYS}"
        assert app["aliases"], f"{app['name']} needs at least one alias"
        if "flathub" in app:
            assert re.match(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$", app["flathub"]), app["flathub"]
        for alias in app["aliases"]:
            assert alias == alias.lower(), f"aliases are lowercase: {alias!r}"
            assert alias not in seen, f"{alias!r} is used by {seen.get(alias)} and {app['name']}"
            seen[alias] = app["name"]


@pytest.mark.parametrize("text,name", [
    ("how do I install spotify?", "spotify"),
    ("How to install VS Code", "vs code"),
    ("install the vlc app", "vlc"),
    ("download zoom", "zoom"),
    ("get obs on linux", "obs"),
    ("can i install steam", None),     # not one of the forms
    ("what is spotify", None),
    ("install", None),
])
def test_wanted(text, name):
    assert apps.wanted(text) == name


@pytest.mark.parametrize("name,app", [("vs code", "Visual Studio Code"), ("code", "Visual Studio Code"),
                                      ("Chrome", "Google Chrome"), ("nothing-like-this", None)])
def test_find(name, app):
    found = apps.find(name)
    assert (found["name"] if found else None) == app


@pytest.fixture
def which(monkeypatch):
    present = set()
    monkeypatch.setattr(apps.shutil, "which", lambda name: f"/usr/bin/{name}" if name in present else None)
    return present


def test_distro_package_comes_first_with_flathub_as_another_way(which):
    result = apps.plan(apps.find("gimp"), ["fedora"], mac=False, flathub=True)
    assert result["command"] == "sudo dnf install gimp"
    assert result["others"] == ["flatpak install flathub org.gimp.GIMP"]


def test_flathub_when_the_distro_has_no_package(which):
    result = apps.plan(apps.find("spotify"), ["ubuntu", "debian"], mac=False, flathub=True)
    assert result["command"] == "flatpak install flathub com.spotify.Client"
    assert result["setup"] == []


def test_flatpak_setup_when_it_is_missing(which):
    result = apps.plan(apps.find("spotify"), ["linuxmint", "ubuntu"], mac=False, flathub=False)
    assert result["setup"] == [
        "sudo apt install flatpak",
        "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"]


def test_flatpak_installed_but_no_flathub(which):
    which.add("flatpak")
    result = apps.plan(apps.find("zoom"), ["fedora"], mac=False, flathub=False)
    assert result["setup"] == [
        "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"]


def test_arch_gets_its_own_package(which):
    assert apps.plan(apps.find("spotify"), ["arch"], mac=False, flathub=False)["command"] == \
        "sudo pacman -S spotify-launcher"


def test_mac_uses_homebrew_casks(which):
    which.add("brew")
    result = apps.plan(apps.find("vs code"), ["macos"], mac=True)
    assert result["command"] == "brew install --cask visual-studio-code"
    assert "brew.sh" not in result["how"]


def test_mac_without_homebrew_says_how_to_get_it(which):
    assert "https://brew.sh" in apps.plan(apps.find("spotify"), ["macos"], mac=True)["how"]


def test_command_line_tools(which):
    assert apps.tool_plan("htop", ["ubuntu", "debian"])["command"] == "sudo apt install htop"
    assert apps.tool_plan("dig", ["fedora"])["command"] == "sudo dnf install bind-utils"
    which.add("htop")
    assert apps.tool_plan("htop", ["ubuntu"]) == {"app": "htop", "installed": True}
    assert apps.tool_plan("not-a-known-tool", ["ubuntu"]) is None
