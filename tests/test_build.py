"""Tests for the skill packaging (scripts/build_skill.py).

Locks the distribution contract: the zip must nest under chinese-fortune/,
carry SKILL.md + runtime files, and leak NO dev/test cruft.
"""
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build_skill.py"


@pytest.fixture(scope="module")
def package(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("dist") / "pkg.zip"
    proc = subprocess.run(
        [sys.executable, str(BUILD), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, f"build failed: {proc.stderr}\n{proc.stdout}"
    assert out.exists()
    return out


def test_skill_md_at_package_root(package):
    names = zipfile.ZipFile(package).namelist()
    assert "chinese-fortune/SKILL.md" in names


def test_runtime_files_present(package):
    names = set(zipfile.ZipFile(package).namelist())
    for must in [
        "chinese-fortune/scripts/bazi_calc.py",
        "chinese-fortune/scripts/utils.py",
        "chinese-fortune/scripts/requirements.txt",
        "chinese-fortune/assets/64hex.json",
        "chinese-fortune/references/00-foundations.md",
        "chinese-fortune/agents/openai.yaml",
        "chinese-fortune/README.md",
        "chinese-fortune/README.en.md",
        "chinese-fortune/LICENSE",
    ]:
        assert must in names, f"missing from package: {must}"


def test_no_dev_cruft_leaked(package):
    names = zipfile.ZipFile(package).namelist()
    leaks = [n for n in names if any(x in n for x in (
        "/tests/", "test_", "/evals/", "__pycache__", ".pyc",
        ".bak", "/.git/", "_competitors", "build_skill",
    ))]
    assert leaks == [], f"dev cruft leaked into package: {leaks}"


def test_extracted_package_runs(package, tmp_path):
    """A freshly extracted package must be self-contained and runnable."""
    zipfile.ZipFile(package).extractall(tmp_path)
    skill = tmp_path / "chinese-fortune"
    proc = subprocess.run(
        [sys.executable, str(skill / "scripts" / "bazi_calc.py"),
         "--year", "1990", "--month", "5", "--day", "10", "--hour", "14",
         "--gender", "male", "--as-of-year", "2026"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0
    assert "乙亥" in proc.stdout  # day pillar of the canonical test chart


# --------------------------------------------------------------------------- #
# 版本来源 — 静默回退 "0.0.0" 会产出错名的发布包
# --------------------------------------------------------------------------- #

def test_read_version_matches_the_shipped_constant():
    sys.path.insert(0, str(ROOT / "scripts"))
    import bazi_calc
    import build_skill

    assert build_skill.read_version() == bazi_calc.VERSION


def test_read_version_fails_loudly_when_absent(monkeypatch):
    """A missing VERSION used to yield "0.0.0" silently, so a refactor that
    moved the constant would have shipped a misnamed zip with nothing red."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_skill

    monkeypatch.setattr(Path, "read_text", lambda self, *a, **kw: "# no version here")
    with pytest.raises(SystemExit):
        build_skill.read_version()


def test_default_output_name_carries_the_version(tmp_path, monkeypatch):
    """test_build always passed --out, so the version-derived default filename
    was never exercised."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_skill

    monkeypatch.chdir(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(BUILD)], cwd=tmp_path,
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    produced = list((ROOT / "dist").glob(f"chinese-fortune-v{build_skill.read_version()}.zip"))
    assert produced, f"no versioned zip produced; stdout={proc.stdout[-400:]}"


def test_all_engines_report_the_single_version():
    """Four divergent version sources existed: bazi/ziwei constants, liuren's
    own __version__ pinned at 1.0.0, and a hardcoded "1.0.0" in qimen's
    payload. Every engine that emits a version must echo utils.__version__."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import utils
    from conftest import run_cli

    probes = [
        ("bazi_calc.py", ["--year", 2000, "--month", 1, "--day", 15,
                          "--hour", 10, "--gender", "male"]),
        ("ziwei_calc.py", ["--year", 2000, "--month", 1, "--day", 15,
                           "--hour", 10, "--gender", "male"]),
        ("qimen_cast.py", ["--date", "2026-06-24", "--time", "13:05"]),
        ("liuren_cast.py", ["--date", "2026-06-24", "--time", "13:05"]),
    ]
    for script, args in probes:
        out = run_cli(script, *args)
        assert out["version"] == utils.__version__, script


def test_build_reads_version_from_utils():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_skill
    import utils

    assert build_skill.read_version() == utils.__version__
