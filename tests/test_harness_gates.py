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


# --------------------------------------------------------------------------- #
# 渐进式披露的可达性 — 搬走的内容必须仍能被路由到
# --------------------------------------------------------------------------- #

PERSONAL_DATA_REFS = ["01-bazi.md", "02-ziwei.md", "12-huangli.md",
                      "13-qiming.md", "14-hehun.md"]


def test_intake_reachable_from_every_personal_data_route():
    """00-intake.md holds the collection protocol, the 边界情形 table and the
    step-9 在世状态 ethics check. Moving it out of SKILL.md only works if every
    method that needs birth data still routes to it."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert (ROOT / "references" / "00-intake.md").exists()
    for line in skill.splitlines():
        if any(ref in line for ref in PERSONAL_DATA_REFS) and line.startswith("|"):
            assert "00-intake.md" in line, f"route misses intake: {line[:70]}"


def test_moved_reference_files_all_exist_and_are_linked():
    """Every references/*.md must be reachable from SKILL.md or from another
    reference — an unreachable file is dead weight that progressive disclosure
    can never surface."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    refs = sorted((ROOT / "references").glob("*.md"))
    corpus = skill + "".join(
        f.read_text(encoding="utf-8") for f in refs)
    for f in refs:
        assert corpus.count(f.name) >= 2, f"{f.name} is unreachable (only self-reference)"


def test_every_asset_is_reachable_from_a_script():
    """assets/*.json are consumed by scripts, never opened by Claude, so an
    asset no script reads is unreachable data.

    Moving the SKILL.md asset table out silently orphaned jiemeng.json until
    jiemeng_lookup.py was added — this test is what should have caught it.
    """
    scripts = "".join(
        f.read_text(encoding="utf-8") for f in (ROOT / "scripts").glob("*.py"))
    orphans = [f.name for f in sorted((ROOT / "assets").glob("*.json"))
               if f.name not in scripts]
    assert not orphans, f"assets no script reads: {orphans}"


def test_no_script_exceeds_the_size_limit():
    """The project's own limit is 200-400 lines typical, 800 max. bazi_calc was
    2.1x that and ziwei_calc 1.3x before the v1.5.1 split; keep them there."""
    oversize = {
        f.name: sum(1 for _ in f.open(encoding="utf-8"))
        for f in sorted((ROOT / "scripts").glob("*.py"))
        if sum(1 for _ in f.open(encoding="utf-8")) > 800
    }
    assert not oversize, f"scripts over the 800-line maximum: {oversize}"


def test_interpretive_discipline_names_an_anchor_for_every_scripted_method():
    """解读纪律 says it governs 所有方法 but named canons for only 八字/周易/紫微.
    An evaluation agent doing a tarot reading reported the rule as inoperative
    there — tarot has no 古籍, and pretending otherwise would itself breach
    凡古籍无据者不妄断. Every method with an engine must be named, and the two
    that genuinely have no Chinese canon must say so rather than be omitted.
    """
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    block = skill.split("## 解读纪律")[1].split("\n## ")[0]
    for method in ["周易", "紫微", "六爻", "梅花", "奇门", "六壬", "黄历"]:
        assert method in block, f"解读纪律 names no anchor for {method}"
    # the two without a Chinese canon must be named AND labelled as such
    assert "塔罗" in block and "姓名" in block
    assert "无古籍" in block or "非中土古籍" in block or "无中土古籍" in block


def test_contains_assertion_accepts_non_string_values(monkeypatch):
    """`contains` did `substr not in str(got)`, which raises TypeError the
    moment an eval pins a numeric field (hex_number, a score, a count). The
    gate crashed instead of comparing, so numeric goldens were unusable."""
    run_checks._run_assertion(
        {"kind": "file_contains", "file": "CHANGELOG.md", "needles": ["1.7.0"]},
        "self-test")
    got = {"n": 33, "s": "天山遁"}
    assert run_checks._contains_ok(got, "n", 33)
    assert run_checks._contains_ok(got, "n", "33")
    assert run_checks._contains_ok(got, "s", "天山")
    assert not run_checks._contains_ok(got, "n", 34)


def test_every_cli_engine_has_a_release_eval():
    """The harness is the release gate, but six of fifteen CLIs never ran in
    it — 六爻, 大六壬, 小六壬, 解梦, 历法换算 and 探索. liuyao is the pointed
    example: its hexagram naming was wrong on 48 of 64 hexagrams until v1.4.0
    and no eval would have caught it."""
    import os
    spec = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
    covered = {
        os.path.basename(a["cmd"][0])
        for e in spec["evals"] for a in e.get("assertions", [])
        if a.get("kind") == "script" and a.get("cmd")
    }
    helpers = {
        "utils.py", "build_skill.py", "entropy.py",
        "bazi_tables.py", "bazi_shensha.py", "bazi_strength.py", "bazi_geju.py",
        "ziwei_tables.py", "ziwei_stars.py", "ziwei_palaces.py", "ziwei_patterns.py",
    }
    clis = {p.name for p in (ROOT / "scripts").glob("*.py")} - helpers
    missing = sorted(clis - covered)
    assert not missing, f"CLIs with no release eval: {missing}"


def test_harness_reports_a_timeout_as_a_failed_check_not_a_traceback():
    """main() only caught AssertionError. subprocess.TimeoutExpired is not one,
    so a slow pytest ended the harness with a bare traceback *before any check
    reported*: no per-check verdict, no "x/7" line, and the checks after it
    never ran. The gate's own contract ("7/7") did not hold on that path.

    The margin was real, not theoretical: the timeout was 180s while the suite
    had grown from 1013 to 2150 tests and now includes a 58,440-day sxtwl sweep.
    """
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "evals"))
    import run_checks

    assert run_checks.UNIT_TEST_TIMEOUT_S >= 600, run_checks.UNIT_TEST_TIMEOUT_S

    def boom():
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    after_ran = []

    def later():
        after_ran.append(True)

    boom.__name__, later.__name__ = "check_boom", "check_later"
    results = []
    for check in (boom, later):
        try:
            check()
            results.append((check.__name__, True, ""))
        except AssertionError as exc:
            results.append((check.__name__, False, str(exc)))
        except subprocess.TimeoutExpired as exc:
            results.append((check.__name__, False, f"timed out after {exc.timeout}s"))

    assert results[0] == ("check_boom", False, "timed out after 1s")
    assert after_ran == [True], "checks after a timeout must still run"

    # 上面复刻的是 main() 的循环; 确认 main() 真的带了这个 except 分支。
    src = (root / "evals" / "run_checks.py").read_text(encoding="utf-8")
    assert "except subprocess.TimeoutExpired" in src
