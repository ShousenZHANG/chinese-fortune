"""The release harness must fail loudly, never vacuously.

evals/run_checks.py is the release gate, but nothing tested the gate itself.
These cover the failure paths: a gate that silently degrades to "nothing to
check" is worse than no gate, because it reports PASS.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))

import run_checks  # noqa: E402  # isort: skip


# --------------------------------------------------------------------------- #
# check_release_cleanliness — the committed-.pyc gate must not degrade to a
# loop over an empty list when git is unavailable
# --------------------------------------------------------------------------- #

def test_cleanliness_fails_when_git_ls_files_fails(monkeypatch):
    """A non-zero `git ls-files` must fail the check, not empty the list."""
    def fake_run(*a, **kw):
        return subprocess.CompletedProcess(
            args=a[0] if a else [], returncode=128,
            stdout="", stderr="fatal: not a git repository")

    monkeypatch.setattr(run_checks.subprocess, "run", fake_run)
    with pytest.raises(AssertionError, match="git ls-files"):
        run_checks.check_release_cleanliness()


def test_cleanliness_fails_when_git_missing(monkeypatch):
    """An OSError (git not on PATH) must also fail loudly."""
    def boom(*a, **kw):
        raise OSError("git not found")

    monkeypatch.setattr(run_checks.subprocess, "run", boom)
    with pytest.raises(AssertionError, match="git ls-files"):
        run_checks.check_release_cleanliness()


# --------------------------------------------------------------------------- #
# check_interpretive_discipline — both files must be locked symmetrically
# --------------------------------------------------------------------------- #

FIVE_CLASSICS = ["子平真诠", "滴天髓", "穷通宝鉴", "三命通会", "渊海子平"]


def test_agent_discipline_needles_cover_all_five_classics():
    """agents/openai.yaml was guarded by a single substring, so four of the
    five classics and both discipline clauses could be stripped with the gate
    still green. The needle list must be symmetric with SKILL.md's."""
    needles = run_checks.AGENT_DISCIPLINE_NEEDLES
    for classic in FIVE_CLASSICS:
        assert classic in needles, f"agent lock missing classic: {classic}"
    assert any("古籍无据" in n for n in needles), "agent lock missing 不妄断 clause"


def test_agent_discipline_actually_fails_on_a_missing_classic(monkeypatch):
    """Not just the constant — the check must act on it."""
    real = Path.read_text

    def stripped(self, *a, **kw):
        text = real(self, *a, **kw)
        if self.name == "openai.yaml":
            return text.replace("滴天髓", "")
        return text

    monkeypatch.setattr(Path, "read_text", stripped)
    with pytest.raises(AssertionError, match="滴天髓"):
        run_checks.check_interpretive_discipline()


# --------------------------------------------------------------------------- #
# check_unit_tests — the failure path itself must not crash
# --------------------------------------------------------------------------- #

def test_unit_test_failure_reports_output_instead_of_crashing(monkeypatch):
    """pytest failing used to raise TypeError inside the harness: stdout was
    None after a decode error, so the gate reported its own stack trace rather
    than the test failure."""
    def fake_run(*a, **kw):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout=None)

    monkeypatch.setattr(run_checks.subprocess, "run", fake_run)
    with pytest.raises(AssertionError, match="pytest failed"):
        run_checks.check_unit_tests()


# --------------------------------------------------------------------------- #
# eval assertions must be able to tell a correct asset from a truncated one
# --------------------------------------------------------------------------- #

def test_jiemeng_eval_asserts_structure_not_one_character():
    """eval #7's only needle was 蛇 — a single CJK character in a 38 KB file,
    which cannot distinguish a correct dream dictionary from a broken one."""
    spec = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    ev = next(e for e in spec["evals"] if e["id"] == 7)
    needles = [n for a in ev["assertions"] for n in a.get("needles", [])]
    assert len(needles) >= 3, f"eval #7 still thin: {needles}"
    assert "traditional" in needles and "modern_psychology" in needles, (
        "must assert the dual-reading structure the eval's expected_output promises"
    )


def test_qimen_school_note_is_locked():
    """The 三元 honesty note added in v1.3.0 carried no invariant lock, unlike
    every other honesty text in the project."""
    spec = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    needles = [
        n for e in spec["evals"] for a in e.get("assertions", [])
        if a.get("file", "").endswith("06-qimen.md") for n in a.get("needles", [])
    ]
    assert "拆补置闰" in needles, "qimen 流派注 unlocked"
