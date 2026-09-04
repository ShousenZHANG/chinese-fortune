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
    """1990 是两种换岁法恰好一致的年份, 所以这条断言原本对该 bug 完全免疫:
    strict_bazi_zodiac 探硬编码的 2月5日 + getYearShengXiao() (农历年口径),
    在 1950-2050 的 49/101 年返回上一年生肖, 而 1990 不在其中。改用 2026 —— 丙午
    马年, 立春 2月4日, 春节 2月17日, 旧实现给「蛇」。
    """
    d = run("zodiac_compat.py", "year", "--year", "2026")
    assert d["zodiac"] == "马"
    assert d["strict_bazi_zodiac"] == "马"
    assert d["folk_zodiac"] == "马"
    assert d["li_chun"] == "2026-02-04"
    assert d["lunar_new_year"] == "2026-02-17"


@pytest.mark.parametrize("year", list(range(1950, 2051)))
def test_zodiac_year_matches_lichun_year_pillar(year):
    """整年生肖必须等于该年立春后的年柱地支所对应的生肖, 逐年锁死 1950-2050。
    旧实现在其中 49 年不符。
    """
    from lunar_python import Solar
    truth = Solar.fromYmdHms(year, 6, 1, 12, 0, 0).getLunar().getYearShengXiaoByLiChun()
    d = run("zodiac_compat.py", "year", "--year", str(year))
    assert d["zodiac"] == truth, (year, d["zodiac"], truth)
    assert d["strict_bazi_zodiac"] == truth
    # 两法对整年标签必然一致 —— 分界都在 1-2 月, 年中取值落在同一区间。
    assert d["folk_zodiac"] == truth


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
