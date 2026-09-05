"""Tests for name_analyze: stroke-table merge + reliability flag."""
import json
import subprocess
import sys
from pathlib import Path

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


def test_all_five_grids_are_pinned_not_just_ren_ge():
    """全仓从前唯一的五格数值断言是 ren_ge == 14; 天格/地格/外格/总格 四个格零断言。
    变异测试实证: 把 wai = (total - ren) + 1 改成 + 2, 全量套件仍全绿 —— 而外格数字
    错会查错 81 数理那一行, 吉凶断语整条错, 并且照样写进交付给用户的 summary。

    张子涵 (张11 子3 涵12, 康熙笔画):
      天格 = 姓 + 1        = 12
      人格 = 姓 + 名首     = 14
      地格 = 名之和        = 15
      总格 = 全名之和      = 26
      外格 = 总格 - 人格 + 1 = 13
    """
    d = run_name("--name", "张子涵")
    g = d["five_grids"]
    assert g["tian_ge"]["number"] == 12
    assert g["ren_ge"]["number"] == 14
    assert g["di_ge"]["number"] == 15
    assert g["zong_ge"]["number"] == 26
    assert g["wai_ge"]["number"] == 13
    # 五格恒等式: 外格 = 总格 - 人格 + 1
    assert g["wai_ge"]["number"] == g["zong_ge"]["number"] - g["ren_ge"]["number"] + 1
    # 数字必须真的驱动断语, 而不是各算各的
    assert g["wai_ge"]["luck"] == "大吉"
    assert "外格 13" in d["summary"]
