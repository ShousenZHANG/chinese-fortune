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


# --------------------------------------------------------------------------- #
# 不揣测时辰 — lunar2solar 无时辰时不得输出时柱
# --------------------------------------------------------------------------- #

def test_lunar2solar_without_hour_emits_no_hour_pillar():
    """00-intake.md: 时辰未知 → 时柱缺如, 标注"时柱待补". 不揣测时辰.

    lunar2solar took no --hour, silently used 12:00, and still published a
    fully-formed 时柱 — a fabricated pillar in exactly the unknown-hour case
    the intake table prescribes this tool for.
    """
    from conftest import run_cli
    d = run_cli("lunar_convert.py", "lunar2solar",
                "--year", 1958, "--month", 9, "--day", 12)
    assert d["solar_date"]["iso"] == "1958-10-24"
    assert d["lunar_date"]["time_in_ganzhi"] is None
    assert d["ganzhi"]["hour"] is None
    assert "待补" in d["lunar_date"]["time_note"]
    # the three determinate pillars are unaffected
    assert d["ganzhi"]["day"] == "甲戌"


def test_lunar2solar_with_hour_emits_the_hour_pillar():
    """Supplying --hour makes the 时柱 legitimate, so it must appear."""
    from conftest import run_cli
    d = run_cli("lunar_convert.py", "lunar2solar",
                "--year", 1958, "--month", 9, "--day", 12, "--hour", 12)
    assert d["ganzhi"]["hour"] == "庚午"
    assert d["lunar_date"]["time_in_ganzhi"] == "庚午"


def test_solar2lunar_without_hour_emits_no_hour_pillar():
    """Same rule: --hour defaulting to 0 is indistinguishable from a user who
    genuinely said 子时."""
    from conftest import run_cli
    d = run_cli("lunar_convert.py", "solar2lunar",
                "--year", 1958, "--month", 10, "--day", 24)
    assert d["ganzhi"]["hour"] is None
    assert "待补" in d["lunar_date"]["time_note"]
