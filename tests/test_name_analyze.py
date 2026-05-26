"""Tests for name_analyze: stroke-table merge + reliability flag."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import name_analyze as na

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
NAME = SCRIPTS / "name_analyze.py"


def test_fallback_merged_into_asset():
    """Common given-name chars in FALLBACK must survive even if asset omits them."""
    table = na.load_bihua_table()
    assert table.get("涵") == 12  # missing from asset, present in FALLBACK
    assert table.get("张") == 11
    assert len(table) > 2594  # asset (2594) + fallback-only extras


def run_name(*args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(NAME), *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(proc.stdout)


def test_known_name_reliable():
    d = run_name("--name", "张子涵")
    assert d["ok"] is True
    assert d["reliable"] is True
    assert d["missing_in_table"] == []
    assert d["five_grids"]["ren_ge"]["number"] == 14  # 张11 + 子3


def test_rare_char_flagged_unreliable():
    d = run_name("--name", "张龘")
    assert d["ok"] is True
    assert d["reliable"] is False
    assert "warning" in d


def test_strict_mode_rejects_missing():
    proc = subprocess.run(
        [sys.executable, str(NAME), "--name", "张龘", "--strict"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1
    d = json.loads(proc.stdout)
    assert d["ok"] is False
    assert d["error"] == "missing_strokes"
