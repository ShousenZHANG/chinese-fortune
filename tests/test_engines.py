"""Structure + invariant tests for the non-bazi engines.

Closes the biggest coverage gap: before this, only bazi/name/utils were
tested. Each engine here is exercised via subprocess with deterministic args
(seeds / fixed dates) and asserted to emit valid JSON with its contract keys.

These are CONTRACT tests (shape + determinism + a few domain invariants), not
interpretation tests — interpretation correctness needs a validated golden
corpus (see README / market-research notes), which is out of scope here.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

needs_lunar = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")


def run(script, *args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"{script} emitted non-JSON (rc={proc.returncode})\n"
            f"stderr={proc.stderr[:400]}\nstdout={proc.stdout[:400]}"
        ) from e


def has(d, *keys):
    for k in keys:
        assert k in d, f"missing key {k!r}; got {list(d)[:12]}"


# --------------------------------------------------------------------------- #
# 周易 — coins cast, seeded => deterministic
# --------------------------------------------------------------------------- #

def test_yijing_structure_and_determinism():
    a = run("yijing_cast.py", "coins", "--seed", "7", "--question", "x")
    b = run("yijing_cast.py", "coins", "--seed", "7", "--question", "x")
    has(a, "main_hex", "changed_hex", "nuclear_hex", "active_lines")
    assert a["main_hex"]["number"] == b["main_hex"]["number"]  # seed stable
    assert 1 <= a["main_hex"]["number"] <= 64
    assert len(a["raw_lines"]) == 6


# --------------------------------------------------------------------------- #
# 梅花易数 — numbers cast (fully deterministic)
# --------------------------------------------------------------------------- #

def test_meihua_structure():
    d = run("meihua_cast.py", "numbers", "--upper", "3", "--lower", "5", "--question", "x")
    has(d, "main_hex", "changed_hex", "nuclear_hex", "ti_yong")
    assert 1 <= d["main_hex"]["number"] <= 64
    # body/use relation must be one of the 5 五行 relations
    assert d["ti_yong"]["relation"]


# --------------------------------------------------------------------------- #
# 六爻 — coins, seeded
# --------------------------------------------------------------------------- #

@needs_lunar
def test_liuyao_structure_and_determinism():
    a = run("liuyao_cast.py", "coins", "--seed", "7", "--date", "2026-06-01", "--time", "10:00")
    b = run("liuyao_cast.py", "coins", "--seed", "7", "--date", "2026-06-01", "--time", "10:00")
    has(a, "main_chart", "changed_chart", "nuclear_chart", "active_lines")
    assert a["raw_lines"] == b["raw_lines"]
    assert len(a["raw_lines"]) == 6


# --------------------------------------------------------------------------- #
# 小六壬 — fully deterministic lunar input
# --------------------------------------------------------------------------- #

def test_xiaoliuren_structure():
    d = run("xiaoliuren_cast.py", "lunar", "--month", "3", "--day", "15", "--hour-branch", "午")
    has(d, "result")
    assert d["result"]["palace"] in {"大安", "留连", "速喜", "赤口", "小吉", "空亡"}
    assert d["result"]["tone"] in {"吉", "凶", "中"}


# --------------------------------------------------------------------------- #
# 生肖合婚 — deterministic; 虎申 must be 相冲 (score low)
# --------------------------------------------------------------------------- #

def test_zodiac_compat_chong():
    d = run("zodiac_compat.py", "compat", "--a", "虎", "--b", "猴")
    has(d, "score", "verdict", "summary")
    assert "冲" in d["summary"]            # 寅申相冲
    assert d["score"] <= 3                  # 六冲 => low compatibility

def test_zodiac_compat_sanhe_high():
    # 寅午戌三合 — 虎与马 should score high.
    d = run("zodiac_compat.py", "compat", "--a", "虎", "--b", "马")
    assert d["score"] >= 6


# --------------------------------------------------------------------------- #
# 奇门遁甲 — deterministic by date/time
# --------------------------------------------------------------------------- #

@needs_lunar
def test_qimen_structure():
    d = run("qimen_cast.py", "--date", "2026-06-01", "--time", "14:30")
    assert d["ok"] is True
    has(d, "ju_type", "ju_number", "ganzhi")
    assert d["ju_type"] in {"阳遁", "阴遁"}
    assert 1 <= d["ju_number"] <= 9


# --------------------------------------------------------------------------- #
# 大六壬 — deterministic by date/time
# --------------------------------------------------------------------------- #

@needs_lunar
def test_liuren_structure():
    d = run("liuren_cast.py", "--date", "2026-06-01", "--time", "14:30", "--question", "x")
    assert d["ok"] is True
    has(d, "ri_gan", "ri_zhi", "month_zhi")


# --------------------------------------------------------------------------- #
# 黄历 — deterministic by date
# --------------------------------------------------------------------------- #

@needs_lunar
def test_huangli_structure():
    d = run("huangli_query.py", "--date", "2026-06-01")
    has(d, "yi", "ji", "ganzhi", "zhi_shen_12jianchu")
    assert isinstance(d["yi"], list)
    assert isinstance(d["ji"], list)


# --------------------------------------------------------------------------- #
# 紫微斗数 — structure of the hand-rolled engine
# --------------------------------------------------------------------------- #

@needs_lunar
def test_ziwei_structure():
    d = run("ziwei_calc.py", "--year", "1995", "--month", "7", "--day", "20",
            "--hour", "1", "--gender", "female", "--lunar")
    assert d["ok"] is True
    has(d, "ming_gong", "shen_gong", "wuxing_ju", "ziwei_position")


# --------------------------------------------------------------------------- #
# 五鼠遁 invariant — hour-stem is fixed by day-stem (table-free oracle).
# 甲己日->甲子时, 乙庚->丙子, 丙辛->戊子, 丁壬->庚子, 戊癸->壬子.
# Verified through the real bazi engine at 00:30 (早子时, unambiguous).
# --------------------------------------------------------------------------- #

WUSHU_DUN = {
    "甲": "甲", "己": "甲",
    "乙": "丙", "庚": "丙",
    "丙": "戊", "辛": "戊",
    "丁": "庚", "壬": "庚",
    "戊": "壬", "癸": "壬",
}

@needs_lunar
@pytest.mark.parametrize("y,m,dd", [
    (2020, 6, 15), (2021, 3, 9), (2022, 11, 1), (1990, 5, 10), (2000, 1, 15),
])
def test_wushu_dun_hour_stem_invariant(y, m, dd):
    d = run("bazi_calc.py", "--year", y, "--month", m, "--day", dd,
            "--hour", 0, "--minute", 30, "--gender", "male", "--as-of-year", 2026)
    day_stem = d["four_pillars"]["day"]["stem"]
    hour_gz = d["four_pillars"]["hour"]["ganzhi"]
    assert hour_gz[1] == "子"                     # 00:30 is 子时
    assert hour_gz[0] == WUSHU_DUN[day_stem], (
        f"五鼠遁 violated: 日干{day_stem} -> 时干 should be "
        f"{WUSHU_DUN[day_stem]}子, got {hour_gz}")
