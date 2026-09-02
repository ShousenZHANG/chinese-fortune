"""Coverage + correctness for lunar_convert and the zodiac sub-commands
(info / year / taisui) that the main suite did not exercise."""
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
# lunar_convert — 公历 <-> 农历 round trip
# --------------------------------------------------------------------------- #

def test_solar_to_lunar():
    d = run("lunar_convert.py", "solar2lunar", "--year", "1990", "--month", "5", "--day", "10")
    assert d["lunar_date"]["year_in_ganzhi"] == "庚午"
    assert d["lunar_date"]["day_chinese"] == "十六"


def test_lunar_to_solar_roundtrip():
    # 1990 农历四月十六 -> 公历 1990-05-10 (inverse of the test above).
    d = run("lunar_convert.py", "lunar2solar", "--year", "1990", "--month", "4", "--day", "16")
    assert d["solar_date"]["iso"] == "1990-05-10"


def test_solar2lunar_invalid_date():
    d = run("lunar_convert.py", "solar2lunar", "--year", "1990", "--month", "13", "--day", "40")
    assert d.get("error") == "invalid_date"


# --------------------------------------------------------------------------- #
# zodiac sub-commands
# --------------------------------------------------------------------------- #

def test_zodiac_info():
    d = run("zodiac_compat.py", "info", "--zodiac", "鼠")
    assert d["wuxing"] == "水"
    assert isinstance(d["strengths"], list) and d["strengths"]


def test_zodiac_year_lichun_vs_folk():
    d = run("zodiac_compat.py", "year", "--year", "1990")
    assert d["strict_bazi_zodiac"] == "马"
    assert d["folk_zodiac"] == "马"


def test_zodiac_taisui_2026_horse_year():
    # 2026 = 丙午 马年; 本命=马, 冲=鼠.
    d = run("zodiac_compat.py", "taisui", "--year", "2026")
    assert d["year_zodiac"] == "马"
    assert d["犯太岁"] == "马"
    assert d["冲太岁"] == "鼠"


# --------------------------------------------------------------------------- #
# 错误路径退出码 — 13 引擎中 zodiac_compat 是唯一 error 仍 exit 0 的异类
# --------------------------------------------------------------------------- #

def test_zodiac_info_unknown_exits_nonzero():
    """输出 error 负载时必须 rc=1, 否则按退出码判断的调用方会当成功."""
    from conftest import run_cli
    d = run_cli("zodiac_compat.py", "info", "--zodiac", "XX", expect_rc=1)
    assert "error" in d


def test_zodiac_compat_unknown_exits_nonzero():
    from conftest import run_cli
    d = run_cli("zodiac_compat.py", "compat", "--a", "鼠", "--b", "XX", expect_rc=1)
    assert "error" in d
