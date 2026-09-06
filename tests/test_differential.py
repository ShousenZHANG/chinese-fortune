"""Differential correctness tests — cross-check the calendar engine against an
INDEPENDENT second implementation (sxtwl, a C++ port of 寿星天文历).

Closes the "self-snapshot" gap: the rest of the suite asserts bazi_calc equals
lunar_python (the library it wraps). Here two INDEPENDENT codebases must agree.

Methodology note: sxtwl's getYearGZ/getMonthGZ are date-granular (the whole
节气 day counts as "after"), while lunar_python is time-aware (the pillar flips
at the exact 节气 instant — verified more precise). So:
  - 日柱 (date-level in both) is cross-checked over the FULL grid.
  - 年柱/月柱 are cross-checked only on non-节气 days, where granularity is moot.
  - A dedicated test asserts lunar_python's time-aware 立春 switch is correct.
"""
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

sxtwl = pytest.importorskip("sxtwl")
pytest.importorskip("lunar_python")
from lunar_python import Solar  # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"


def sx_gz(day, kind, hour=12):
    g = {"y": day.getYearGZ(), "m": day.getMonthGZ(),
         "d": day.getDayGZ(), "h": day.getHourGZ(hour)}[kind]
    return GAN[g.tg] + ZHI[g.dz]


def lp_lunar(y, m, d, hour=12):
    return Solar.fromYmdHms(y, m, d, hour, 0, 0).getLunar()


def _is_jieqi_day(y, m, d) -> bool:
    table = lp_lunar(y, m, d).getJieQiTable()
    return any(s.getYear() == y and s.getMonth() == m and s.getDay() == d
               for s in table.values())


def _grid():
    g = []
    cur, end = date(1920, 1, 1), date(2080, 1, 1)
    while cur < end:
        g.append((cur.year, cur.month, cur.day))
        cur += timedelta(days=131)  # ~0.36y; 447 points sweeping all 节气
    return g


GRID = _grid()


@pytest.mark.parametrize("y,m,d", GRID)
def test_day_pillar_matches_sxtwl_full_grid(y, m, d):
    """日柱 (60-cycle anchor) must match the independent engine on every date."""
    lp = lp_lunar(y, m, d).getDayInGanZhi()
    sx = sx_gz(sxtwl.fromSolar(y, m, d), "d")
    assert lp == sx, f"{y}-{m}-{d}: 日柱 lunar_python {lp} != sxtwl {sx}"


@pytest.mark.parametrize("y,m,d", GRID)
def test_year_month_pillar_matches_sxtwl_off_jieqi(y, m, d):
    """年柱/月柱 must match on non-节气 days (granularity difference is moot)."""
    if _is_jieqi_day(y, m, d):
        pytest.skip("节气 day: time-aware vs date-level convention differ by design")
    e = lp_lunar(y, m, d).getEightChar()
    day = sxtwl.fromSolar(y, m, d)
    assert e.getYear() == sx_gz(day, "y"), f"{y}-{m}-{d} 年柱"
    assert e.getMonth() == sx_gz(day, "m"), f"{y}-{m}-{d} 月柱"


@pytest.mark.parametrize("hour", [2, 8, 10, 16, 18, 22])
def test_hour_pillar_matches_sxtwl(hour):
    y, m, d = 1988, 9, 17
    e = lp_lunar(y, m, d, hour).getEightChar()
    e.setSect(2)
    assert e.getTime() == sx_gz(sxtwl.fromSolar(y, m, d), "h", hour)


def test_lichun_year_pillar_is_time_aware():
    """The 八字 year pillar must flip at the exact 立春 instant, not midnight.
    2024 立春 = Feb 4 16:27 → before = 癸卯, after = 甲辰."""
    before = lp_lunar(2024, 2, 4, 16).getEightChar().getYear()  # 16:00
    after = lp_lunar(2024, 2, 4, 17).getEightChar().getYear()   # 17:00
    assert before == "癸卯"
    assert after == "甲辰"


def test_bazi_script_matches_independent_engine():
    """End-to-end: bazi_calc.py == sxtwl for a noon non-节气 birth."""
    import json
    assert not _is_jieqi_day(1984, 10, 1)
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "bazi_calc.py"),
         "--year", "1984", "--month", "10", "--day", "1", "--hour", "12",
         "--gender", "male", "--as-of-year", "2026"],
        capture_output=True, text=True, encoding="utf-8",
    )
    d = json.loads(proc.stdout)
    p = d["four_pillars"]
    day = sxtwl.fromSolar(1984, 10, 1)
    assert p["year"]["ganzhi"] == sx_gz(day, "y")
    assert p["month"]["ganzhi"] == sx_gz(day, "m")
    assert p["day"]["ganzhi"] == sx_gz(day, "d")
    assert p["hour"]["ganzhi"] == sx_gz(day, "h", 12)


# 曾有一条 test_lunar_python_day_pillar_matches_sxtwl_on_every_day_1920_2080,
# 逐日比对 58,440 天, 耗时 58 秒。**已删除。**
#
# 它比的是 lunar_python 对 sxtwl —— lp_lunar() 就是被封装的那个库, 全程不经过
# scripts/ 任何一行。也就是说它校验的是我们的**依赖**, 不是我们的代码; 而上面
# 447 点的参数化网格已经在做同一件事, 且失败时能报出具体日期。
#
# 它当初存在的唯一理由, 是让 README 能写「1920-2080 全网格验证」—— 为一句话付
# 58 秒/次, 是在优化说辞而不是优化正确性。README 已改为分两层如实陈述。


def test_bazi_engine_matches_sxtwl_over_a_real_grid():
    """Four pillars on an independent clock-time grid; solar correction has golden tests.

    Exclude solar-term dates for year/month because sxtwl has date granularity.
    Sect 2 keeps the same civil day at 23h; the hour stem uses the next day.
    """
    import bazi_calc
    cur, end = date(1920, 1, 1), date(2080, 1, 1)
    checked = 0
    while cur < end:
        independent = sxtwl.fromSolar(cur.year, cur.month, cur.day)
        for hour in (0, 12, 23):
            args = bazi_calc.build_parser().parse_args([
                '--year', str(cur.year), '--month', str(cur.month), '--day', str(cur.day),
                '--hour', str(hour), '--gender', 'male', '--as-of-year', '2026',
                '--time-standard', 'clock'])
            chart = bazi_calc.calculate_bazi(args)
            assert chart['ok'], (cur, hour, chart)
            assert chart['solar_date'] == {'year': cur.year, 'month': cur.month,
                                           'day': cur.day, 'hour': hour, 'minute': 0}
            pillars = chart['four_pillars']
            assert pillars['day']['ganzhi'] == sx_gz(independent, 'd'), (cur, hour, 'day')
            assert pillars['hour']['ganzhi'] == sx_gz(independent, 'h', hour), (cur, hour, 'hour')
            if not independent.hasJieQi():
                assert pillars['year']['ganzhi'] == sx_gz(independent, 'y'), (cur, hour, 'year')
                assert pillars['month']['ganzhi'] == sx_gz(independent, 'm'), (cur, hour, 'month')
            checked += 1
        cur += timedelta(days=97)
    assert checked >= 1800
