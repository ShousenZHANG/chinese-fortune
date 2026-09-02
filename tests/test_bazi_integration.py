"""End-to-end snapshot tests for bazi_calc.py via subprocess.

Requires lunar_python. Skips gracefully if absent. Uses --as-of-year for
deterministic output so snapshots are stable over time.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
BAZI = SCRIPTS / "bazi_calc.py"

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

pytestmark = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")


def run_bazi(*args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(BAZI), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"non-JSON output (rc={proc.returncode})\n"
            f"stderr={proc.stderr[:500]}\nstdout={proc.stdout[:500]}"
        ) from e


def pillars(d) -> tuple:
    p = d["four_pillars"]
    return (p["year"]["ganzhi"], p["month"]["ganzhi"],
            p["day"]["ganzhi"], p["hour"]["ganzhi"])


def test_known_chart_1990():
    d = run_bazi("--year", 1990, "--month", 5, "--day", 10, "--hour", 14,
                 "--gender", "male", "--as-of-year", 2026)
    assert d["ok"] is True
    assert pillars(d) == ("庚午", "辛巳", "乙亥", "癸未")


def test_known_chart_winter():
    d = run_bazi("--year", 2000, "--month", 1, "--day", 15, "--hour", 12,
                 "--gender", "male", "--as-of-year", 2026)
    assert pillars(d) == ("己卯", "丁丑", "壬申", "丙午")
    assert d["day_master"]["stem"] == "壬"


def test_midnight_rollover_changes_day_pillar():
    """Western longitude + just-after-midnight must roll to the PREVIOUS day.

    Same wall-clock date/time, compared at reference meridian vs far west.
    The day pillar (日柱) must differ — this is the bug that was clamped.
    """
    ref = run_bazi("--year", 2000, "--month", 1, "--day", 2, "--hour", 0,
                   "--minute", 5, "--longitude", 120, "--gender", "male",
                   "--as-of-year", 2026)
    west = run_bazi("--year", 2000, "--month", 1, "--day", 2, "--hour", 0,
                    "--minute", 5, "--longitude", 75, "--gender", "male",
                    "--as-of-year", 2026)
    # Far-west correction (-3h) rolls the corrected solar date back one day.
    assert west["solar_date"]["day"] == 1
    assert ref["four_pillars"]["day"]["ganzhi"] != west["four_pillars"]["day"]["ganzhi"]


def test_determinism_with_as_of_year():
    a = run_bazi("--year", 1990, "--month", 5, "--day", 10, "--hour", 14,
                 "--gender", "male", "--as-of-year", 2026)
    b = run_bazi("--year", 1990, "--month", 5, "--day", 10, "--hour", 14,
                 "--gender", "male", "--as-of-year", 2026)
    assert a == b
    assert [ln["year"] for ln in a["liu_nian"]] == [2026, 2027, 2028, 2029, 2030, 2031]


@pytest.mark.parametrize("bad", [
    ["--year", 1990, "--month", 13, "--day", 10, "--hour", 14, "--gender", "male"],
    ["--year", 1990, "--month", 5, "--day", 40, "--hour", 14, "--gender", "male"],
    ["--year", 1990, "--month", 5, "--day", 10, "--hour", 25, "--gender", "male"],
    ["--year", 1850, "--month", 5, "--day", 10, "--hour", 14, "--gender", "male"],
])
def test_invalid_input_rejected(bad):
    d = run_bazi(*bad)
    assert d["ok"] is False
    assert d["error"] == "invalid_input"


# --------------------------------------------------------------------------- #
# Hard edge cases — the project's headline correctness claims
# --------------------------------------------------------------------------- #

def test_lichun_is_year_boundary_not_jan1():
    """年柱 must switch at 立春 (~Feb 4), not Jan 1.

    2000 立春 ≈ Feb 4: Feb 3 still belongs to 己卯 (1999); Feb 5 is 庚辰 (2000).
    """
    before = run_bazi("--year", 2000, "--month", 2, "--day", 3, "--hour", 12,
                      "--gender", "male", "--as-of-year", 2026)
    after = run_bazi("--year", 2000, "--month", 2, "--day", 5, "--hour", 12,
                     "--gender", "male", "--as-of-year", 2026)
    assert before["four_pillars"]["year"]["ganzhi"] == "己卯"
    assert after["four_pillars"]["year"]["ganzhi"] == "庚辰"


def test_ye_zishi_splits_hour_stem_keeps_day():
    """夜子时 (23:30) vs 早子时 (00:30) on the same civil day:
    day pillar identical, but 时干 differs (sect-2 晚子时 handling)."""
    late = run_bazi("--year", 2020, "--month", 6, "--day", 15, "--hour", 23,
                    "--minute", 30, "--gender", "male", "--as-of-year", 2026)
    early = run_bazi("--year", 2020, "--month", 6, "--day", 15, "--hour", 0,
                     "--minute", 30, "--gender", "male", "--as-of-year", 2026)
    assert late["four_pillars"]["day"]["ganzhi"] == early["four_pillars"]["day"]["ganzhi"] == "己丑"
    assert late["four_pillars"]["hour"]["ganzhi"] == "丙子"
    assert early["four_pillars"]["hour"]["ganzhi"] == "甲子"


def test_leap_month_lunar_input():
    """闰月 lunar input must resolve without error to a valid chart."""
    d = run_bazi("--year", 2020, "--month", 4, "--day", 15, "--hour", 12,
                 "--gender", "male", "--lunar", "--as-of-year", 2026)
    assert d["ok"] is True
    assert pillars(d) == ("庚子", "辛巳", "庚戌", "壬午")


# --------------------------------------------------------------------------- #
# 全量快照 — 拆分重构的安全网
# --------------------------------------------------------------------------- #

def test_bazi_full_output_snapshot():
    """中性示例盘的完整 JSON 必须逐字段不变.

    既有测试只断 has_keys, shen_sha/yong_shen/ge_ju/interactions 的“值”无人锁;
    P4 拆分 bazi_calc 前必须有这一条, 否则搬代码搬出语义漂移也无人发现.
    version 字段已剔除, 发版不影响本快照.
    """
    import json
    from pathlib import Path

    from conftest import run_cli

    got = run_cli("bazi_calc.py", "--year", 2000, "--month", 1, "--day", 15,
                  "--hour", 10, "--minute", 30, "--gender", "male",
                  "--as-of-year", 2026)
    got.pop("version", None)
    want = json.loads(
        (Path(__file__).resolve().parent / "data" /
         "bazi_snapshot_20000115.json").read_text(encoding="utf-8")
    )
    assert got == want


# --------------------------------------------------------------------------- #
# 起运 / 大运 岁数 — 周岁 per 01-bazi.md §7.2, with the months remainder shown
# --------------------------------------------------------------------------- #

def test_qi_yun_reports_years_months_and_days():
    """§7.2 writes 起运 as 6岁4个月 / 5岁余6月 / 4岁余 — the sub-year remainder
    carries meaning. The old output truncated it to a bare integer, and put
    lunar_python's 起运年数 into a field named start_age."""
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 1995, "--month", 3, "--day", 8,
                "--hour", 7, "--minute", 30, "--gender", "female",
                "--as-of-year", 2026)
    q = d["qi_yun"]
    assert q["years"] == 9 and q["months"] == 5
    assert "9岁" in q["text"] and "5个月" in q["text"]
    assert q["start_year"] == 2004


def test_da_yun_bands_anchor_to_qi_yun_age():
    """01-bazi.md §7.2: 起运6岁4个月 → 6—16、16—26、26—36. Every worked example
    (:625 起运5岁 → 5—15, :655 起运8岁 → 8—18, :684 起运4岁 → 4—14) anchors the
    band to the 起运岁 in 周岁 and steps by 10.

    lunar_python's DaYun.getStartAge() is 虚岁, one greater — kept alongside
    under an honest name rather than silently used as if it were 周岁.
    """
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 1995, "--month", 3, "--day", 8,
                "--hour", 7, "--minute", 30, "--gender", "female",
                "--as-of-year", 2026)
    base = d["qi_yun"]["years"]
    for i, yun in enumerate(d["da_yun"]):
        assert yun["start_age"] == base + 10 * i, yun
        assert yun["end_age"] == base + 10 * i + 10
        assert yun["start_age_xusui"] == yun["start_age"] + 1
    assert d["da_yun"][0]["start_age"] == 9
    assert d["da_yun"][1]["start_age"] == 19
