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


def test_day_pillar_matches_sxtwl_on_every_day_1920_2080():
    """真·全网格: 1920-01-01 到 2080-01-01 逐日比对, 58,440 天无遗漏。

    上面那个参数化网格步长 131 天, 447 个采样点 = 该区间的 0.76%, 而 README
    (中文版) 声称「1920–2080 全网格验证」—— 英文版同一行不带「全」字。函数名
    test_day_pillar_matches_sxtwl_full_grid 与 docstring "on every date" 把同一个
    夸大刻进了代码。

    实测逐日跑一遍约 48 秒, 完全可行, 所以这里把声明兑现而不是把声明改小。
    采样网格保留 —— 它给出逐日期的失败用例名, 定位快。
    """
    from datetime import date, timedelta
    cur, end = date(1920, 1, 1), date(2080, 1, 1)
    checked, mismatches = 0, []
    while cur < end:
        lp = lp_lunar(cur.year, cur.month, cur.day).getDayInGanZhi()
        sx = sx_gz(sxtwl.fromSolar(cur.year, cur.month, cur.day), "d")
        if lp != sx:
            mismatches.append(f"{cur.isoformat()}: lunar_python {lp} != sxtwl {sx}")
        checked += 1
        cur += timedelta(days=1)
    # 分歧优先报告。早先这里在攒够 10 条时 break, 于是 checked 也停在半路 ——
    # 一旦真出现系统性分歧, 断言顺序会让它以 `assert 9 == 58440` 收场, 把唯一
    # 有用的信息 (哪一天、差多少) 全吞掉。现在跑满全程, 只截断展示。
    assert not mismatches, (
        f"{len(mismatches)}/{checked} 天日柱不符, 前 10 条: "
        + " | ".join(mismatches[:10]))
    assert checked == 58440, checked
