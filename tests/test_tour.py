"""Tests for tour.py - `clishe tour`, run against a fake Linux system."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tour  # noqa: E402


@pytest.fixture
def fake_ubuntu(tmp_path):
    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    write("etc/os-release", 'NAME="Linux Mint"\nPRETTY_NAME="Linux Mint 22"\n'
                            'ID=linuxmint\nID_LIKE="ubuntu debian"\n')
    write("proc/sys/kernel/osrelease", "6.8.0-45-generic\n")
    write("proc/cpuinfo", "processor\t: 0\nmodel name\t: Intel(R) Core(TM) i5-8250U CPU\n")
    write("proc/meminfo", "MemTotal:        8048576 kB\nMemFree: 1 kB\n")
    write("proc/uptime", "93784.12 1000.00\n")
    for folder in ("home", "etc", "usr/bin", "tmp"):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _facts(stop):
    return dict(stop["facts"])


def test_system_names_the_distro_and_what_it_is_based_on(fake_ubuntu):
    stop = tour.system(fake_ubuntu)
    assert _facts(stop) == {"Distribution": "Linux Mint 22", "Kernel": "6.8.0-45-generic"}
    assert "based on ubuntu debian" in stop["note"]


def test_hardware(fake_ubuntu):
    facts = _facts(tour.hardware(fake_ubuntu))
    assert facts["Processor"] == "Intel(R) Core(TM) i5-8250U CPU"
    assert facts["Memory"] == "7.7 GB"
    assert facts["On for"] == "1 day, 2 hours"


def test_folders_only_lists_what_exists(fake_ubuntu):
    facts = _facts(tour.folders(fake_ubuntu, "/home/sam"))
    assert list(facts) == ["/home", "/etc", "/usr/bin", "/tmp", "/proc"]
    assert facts["/home"].endswith("yours is /home/sam")


def test_desktop_and_shell():
    facts = _facts(tour.desktop({"XDG_CURRENT_DESKTOP": "X-Cinnamon", "XDG_SESSION_TYPE": "x11",
                                 "SHELL": "/bin/bash"}))
    assert facts == {"Desktop": "X-Cinnamon", "Display": "X11 (the older way of drawing windows)",
                     "Shell": "bash"}


def test_software_uses_the_family_package_manager():
    stop = tour.software(["linuxmint", "ubuntu", "debian"])
    assert _facts(stop)["Package manager"] == "apt"
    assert stop["try"] == ["sudo apt install htop"]


@pytest.mark.parametrize("groups,admin", [(["sam", "sudo"], "yes"), (["sam", "wheel"], "yes"),
                                          (["sam"], "no")])
def test_you(groups, admin):
    assert _facts(tour.you({"USER": "sam"}, groups=groups))["Admin (sudo)"] == admin


@pytest.mark.parametrize("seconds,text", [(59, "0 minutes"), (3660, "1 hour, 1 minute"),
                                          (2 * 86400 + 7200, "2 days, 2 hours")])
def test_duration(seconds, text):
    assert tour._duration(seconds) == text


def test_whole_tour_on_a_bare_system(tmp_path):
    stops = tour.tour(root=tmp_path, env={"HOME": str(tmp_path)})
    assert [s["title"] for s in stops][0] == "Your Linux"
    assert _facts(stops[0])["Distribution"] == "an unknown Linux"
