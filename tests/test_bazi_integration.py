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
