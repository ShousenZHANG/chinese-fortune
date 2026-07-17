"""Coverage for previously-untested deterministic subcommands.

yijing numbers/text, meihua name, xiaoliuren solar — all fully deterministic
(no RNG, no now()), so value-golden assertions are stable. The yijing
numbers case is hand-verifiable: upper 3 = 离☲, lower 5 = 巽☴ → 火风鼎 (#50);
change line 1 flips 巽 → 坎 → 火水未济 (#64).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

pytest.importorskip("lunar_python")


def run(script, *args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- #
# 周易 numbers / text casts
# --------------------------------------------------------------------------- #

def test_yijing_numbers_hand_verified_ding():
    """先天卦数 3=离(上) 5=巽(下) → 火风鼎 #50; 动初爻 → 火水未济 #64."""
    d = run("yijing_cast.py", "numbers", "--upper", "3", "--lower", "5", "--change", "1")
    assert (d["main_hex"]["number"], d["main_hex"]["name"]) == (50, "火风鼎")
    assert d["active_lines"] == [1]
    assert d["changed_hex"]["name"] == "火水未济"


def test_yijing_text_deterministic():
    a = run("yijing_cast.py", "text", "--text", "求财")
    b = run("yijing_cast.py", "text", "--text", "求财")
    assert a["main_hex"]["number"] == b["main_hex"]["number"] == 1
    assert a["main_hex"]["name"] == "乾为天"


# --------------------------------------------------------------------------- #
# 梅花 name cast
# --------------------------------------------------------------------------- #

def test_meihua_name_deterministic():
    d = run("meihua_cast.py", "name", "--text", "张三")
    assert d["main_hex"]["name"] == "乾为天"
    assert d["changing_line"] == 2
    assert d["changed_hex"]["name"] == "天火同人"


# --------------------------------------------------------------------------- #
# 小六壬 solar subcommand (auto lunar conversion path)
# --------------------------------------------------------------------------- #

def test_xiaoliuren_solar_golden():
    d = run("xiaoliuren_cast.py", "solar", "--date", "2026-06-24", "--time", "13:00")
    assert d["result"]["palace"] == "速喜"
    assert d["result"]["tone"] == "吉"


def test_xiaoliuren_solar_midnight_boundary():
    """23:30 falls in 子时; must not crash and must return a valid palace."""
    d = run("xiaoliuren_cast.py", "solar", "--date", "2026-06-24", "--time", "23:30")
    assert d["result"]["palace"] in {"大安", "留连", "速喜", "赤口", "小吉", "空亡"}


# --------------------------------------------------------------------------- #
# 黄历 传统时辰 boundary regression
# --------------------------------------------------------------------------- #

def test_huangli_shichen_traditional_boundaries():
    """REGRESSION: 时辰 blocks must use classical odd-start boundaries
    (子 23-01, 丑 01-03 …) and each block's 干支 branch must equal its
    时辰 label (the old even blocks straddled two 时辰)."""
    d = run("huangli_query.py", "--date", "2026-06-24")
    detail = d["shichen_detail"]
    assert len(detail) == 12
    assert detail[0]["shichen"] == "子"
    assert detail[0]["hour_range"] == "23:00-01:00"
    assert detail[4]["shichen"] == "辰"
    assert detail[4]["hour_range"] == "07:00-09:00"
    for s in detail:
        assert s["ganzhi"][1] == s["shichen"], (
            f"{s['hour_range']} 干支 {s['ganzhi']} != 时辰 {s['shichen']}")
