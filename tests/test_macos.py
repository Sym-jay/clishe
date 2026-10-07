"""macOS support: detection, Homebrew hints, the AI's note, the Trash and
the tour. macOS is faked, so these run anywhere."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import knowledge  # noqa: E402
import tour  # noqa: E402
from providers.base import distro_note  # noqa: E402


@pytest.fixture
def on_a_mac(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(config, "OS_RELEASE_FILE", tmp_path / "no-os-release")


def test_detects_macos(on_a_mac):
    assert config.detect_distro() == "macos"
    assert config.detect_distro_family() == ["macos"]


def test_install_hints_use_homebrew(monkeypatch):
    monkeypatch.setattr(knowledge.shutil, "which", lambda name: "/opt/homebrew/bin/brew")
    assert knowledge.missing_program_hint("htop", ["macos"]).endswith("brew install htop")
    assert knowledge.missing_program_hint("dig", ["macos"]).endswith("brew install bind")


def test_install_hint_mentions_homebrew_when_missing(monkeypatch):
    monkeypatch.setattr(knowledge.shutil, "which", lambda name: None)
    assert "https://brew.sh" in knowledge.missing_program_hint("htop", ["macos"])


def test_ai_is_told_about_bsd_tools_and_brew():
    note = distro_note("macos", ["macos"])
    assert "BSD" in note and "brew install" in note and "never sudo with brew" in note


def test_trash_on_a_mac(monkeypatch):
    import clishe_brain
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(clishe_brain.shutil, "which",
                        lambda name: "/usr/bin/trash" if name == "trash" else None)
    assert clishe_brain._trash_tool() == (["trash"], "Open the Trash in the Dock")


def test_tour_names_macos(monkeypatch):
    monkeypatch.setattr(tour, "_is_mac", lambda root: True)
    monkeypatch.setattr(tour.platform, "mac_ver", lambda: ("15.1", ("", "", ""), ""))
    stop = tour.system(Path("/"))
    assert dict(stop["facts"])["System"] == "macOS 15.1"
    assert "Darwin" in stop["note"]


def test_tour_folders_on_a_mac(tmp_path):
    for folder in ("home", "Users", "Applications", "etc"):
        (tmp_path / folder).mkdir()
    facts = dict(tour.folders(tmp_path, "/Users/sam")["facts"])
    assert "/home" not in facts
    assert facts["/Users"].endswith("yours is /Users/sam")


def test_tour_software_on_a_mac(monkeypatch):
    monkeypatch.setattr(tour.shutil, "which", lambda name: None)
    stop = tour.software(["macos"])
    assert "brew.sh" in dict(stop["facts"])["Package manager"]
    assert stop["try"] == ["brew install htop"]
