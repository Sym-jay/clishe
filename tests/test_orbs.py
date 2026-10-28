"""Tests for orbs.py - the thinking orbs drawn while Clishe waits."""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import orbs  # noqa: E402

# Visible dots and lines at 1.3 s, from the original JavaScript engine
# (thinking-orbs 0.3.2, 64px design). A change to the port that moves away
# from the original shows up here.
ORIGINAL = {
    "working": (516, 0), "searching": (204, 0), "solving": (138, 0),
    "listening": (134, 0), "connecting": (48, 88), "weaving": (153, 0),
    "composing": (566, 0), "breathing": (484, 0), "shaping": (24, 0),
}


def test_every_state_is_covered():
    assert set(ORIGINAL) == set(orbs.STATES)


@pytest.mark.parametrize("state", sorted(ORIGINAL))
def test_geometry_matches_the_original(state):
    dots, lines = orbs.frame(state, 1.3)
    visible = (sum(1 for d in dots if d[3] >= 0.02), sum(1 for ln in lines if ln[5] >= 0.02))
    assert visible == ORIGINAL[state]


def test_shaping_dots_match_the_original():
    # The first dots of the circle, from the original at 0 s.
    dots, _ = orbs.frame("shaping", 0)
    assert [(round(x, 2), round(y, 2)) for x, y, *_ in dots[:3]] == \
        [(32.0, 9.73), (37.76, 10.49), (43.13, 12.72)]


def test_rounding_is_javascripts():
    # Python's round(2.5) is 2; the original's Math.round gives 3, and the
    # composing ribbon's band count depends on it.
    assert orbs._round(2.5) == 3 and orbs._round(-0.5) == 0


@pytest.mark.parametrize("state", sorted(ORIGINAL))
def test_each_state_draws_braille_and_moves(state):
    frames = ["\n".join(orbs.render(state, t, color=False)) for t in (0, 0.5, 1.0)]
    rows = frames[0].split("\n")
    assert len(rows) == orbs.ROWS and all(len(r) == orbs.COLS for r in rows)
    assert all(ch == " " or 0x2800 <= ord(ch) <= 0x28FF for ch in frames[0].replace("\n", ""))
    assert any(ch != " " for ch in frames[0].replace("\n", "")), "nothing drawn"
    assert len(set(frames)) == 3, "the orb doesn't move"


def test_same_moment_draws_the_same_frame():
    assert orbs.render("searching", 0.7) == orbs.render("searching", 0.7)


def test_shading_uses_four_greys():
    art = "".join(orbs.render("composing", 0.5, color=True))
    assert "\033[38;5;" in art
    assert {int(code) for code in __import__("re").findall(r"38;5;(\d+)m", art)} <= set(orbs._GREYS)


def test_run_draws_then_erases_itself(monkeypatch):
    monkeypatch.setattr(orbs, "DELAY", 0)
    out = io.StringIO()
    orbs.run("composing", "Let me think...", out=out, seconds=0.2)
    text = out.getvalue()
    assert text.startswith("\033[?25l")                 # hides the cursor
    assert "Let me think..." in text
    assert text.endswith("\033[J\033[?25h")             # clears its lines, shows the cursor


def test_a_quick_answer_draws_nothing():
    out = io.StringIO()
    orbs.run("composing", out=out, seconds=0.05)        # stopped inside the 0.3 s delay
    assert out.getvalue() == ""


def test_demo_shows_every_state(monkeypatch):
    monkeypatch.setattr(orbs, "DELAY", 0)
    out = io.StringIO()
    orbs.demo(out=out, each=0.06, color=False)
    for state, (_, what) in orbs.STATES.items():
        assert f"{state}: {what}" in out.getvalue()
