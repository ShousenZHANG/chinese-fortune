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
