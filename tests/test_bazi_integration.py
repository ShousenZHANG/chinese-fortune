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


# --------------------------------------------------------------------------- #
# 神煞 断语必须带上参考文档的立场
# --------------------------------------------------------------------------- #

def test_shensha_meanings_carry_their_reference_stance():
    """19-shensha.md §3.15 says of 十恶大败 「子平派多不采用」 and its principle 6
    forbids 炒作神煞恐慌 by name; §3.13 makes 魁罡 conditional on 不喜见财官(破格)
    / 喜见印比(助力). The asset shipped 十恶大败 as a flat 「事业财运均不利」 and
    魁罡 without either condition, so the caveat only existed in a file the
    engine never reads.
    """
    import json
    from pathlib import Path

    assets = json.loads((Path(__file__).resolve().parent.parent / "assets" /
                         "shensha.json").read_text(encoding="utf-8"))
    by_name = {e["name"]: e for grp in ("ji_shen", "xiong_sha")
               for e in assets.get(grp, [])}

    shi_e = by_name["十恶大败"]["meaning"]
    assert "争议" in shi_e and "子平" in shi_e, shi_e
    assert "均不利" not in shi_e, "flat adverse verdict contradicts §3.15"

    kui_gang = by_name["魁罡"]["meaning"]
    assert "破格" in kui_gang and "印比" in kui_gang, kui_gang


# --------------------------------------------------------------------------- #
# 三柱模式 — 时辰未知时仍可排年/月/日柱
# --------------------------------------------------------------------------- #

def test_three_pillar_mode_when_hour_unknown():
    """00-intake.md: 时辰未知 → 仍可排年/月/日柱; 时柱缺如, 标注"时柱待补". 不揣测时辰.

    --hour used to be required, so the script could not follow the skill's own
    documented edge case at all; the only way through was to pass a fabricated
    hour and hope the caller suppressed every contaminated field.
    """
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 1958, "--month", 10, "--day", 24,
                "--gender", "male", "--as-of-year", 2026)

    assert d["hour_known"] is False
    fp = d["four_pillars"]
    assert fp["year"]["ganzhi"] == "戊戌"
    assert fp["month"]["ganzhi"] == "壬戌"
    assert fp["day"]["ganzhi"] == "甲戌"
    assert "待补" in fp["hour"]["status"]
    assert fp["hour"].get("ganzhi") in (None, "")
    # nothing hour-derived may be asserted as fact
    assert d["na_yin"].get("hour") is None
    assert d["true_solar_time"]["applied"] is False
    assert any("时柱" in n for n in d["notes"])


def test_three_pillar_aggregates_exclude_the_hour():
    """五行得分 must count six characters, not eight, when the hour is unknown —
    a guessed hour silently moves 旺衰, 用神, 格局 and 神煞 with it."""
    from conftest import run_cli
    three = run_cli("bazi_calc.py", "--year", 1958, "--month", 10, "--day", 24,
                    "--gender", "male", "--as-of-year", 2026)
    guessed = run_cli("bazi_calc.py", "--year", 1958, "--month", 10, "--day", 24,
                      "--hour", 12, "--gender", "male", "--as-of-year", 2026)
    assert three["wuxing_count"] != guessed["wuxing_count"], (
        "three-pillar totals must differ from an eight-character chart")
    assert three["hour_known"] is False and guessed["hour_known"] is True


def test_supplying_hour_is_unchanged():
    """Relaxing required=True must not alter any existing invocation."""
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 1995, "--month", 3, "--day", 8,
                "--hour", 7, "--minute", 30, "--gender", "female",
                "--as-of-year", 2026)
    assert d["hour_known"] is True
    assert d["four_pillars"]["hour"]["ganzhi"] == "丙辰"


# --------------------------------------------------------------------------- #
# 夏令时 — 钟表时间落在 DST 窗口时, 时柱必须按标准时折算
# --------------------------------------------------------------------------- #

def test_dst_birth_shifts_the_hour_pillar():
    """China ran 夏令时 1986-1991. A clock reading of 07:30 on 1988-07-01 is
    06:30 standard time, and 07:00 is the 卯/辰 boundary — so the 时柱 differs.

    Without --timezone the tool assumes a flat UTC+8 and returns the 辰 pillar,
    which is what a user entering their clock time would silently get.
    """
    from conftest import run_cli

    naive = run_cli("bazi_calc.py", "--year", 1988, "--month", 7, "--day", 1,
                    "--hour", 7, "--minute", 30, "--gender", "male",
                    "--as-of-year", 2026)
    aware = run_cli("bazi_calc.py", "--year", 1988, "--month", 7, "--day", 1,
                    "--hour", 7, "--minute", 30, "--gender", "male",
                    "--as-of-year", 2026, "--timezone", "Asia/Shanghai")

    assert naive["four_pillars"]["hour"]["ganzhi"] == "甲辰"
    assert aware["four_pillars"]["hour"]["ganzhi"] == "癸卯"
    assert aware["timezone"]["dst_hours"] == 1.0
    assert aware["timezone"]["offset_hours"] == 9.0
    assert any("夏令时" in n for n in aware["notes"])


def test_non_dst_birth_is_unchanged_by_timezone():
    """Outside a DST window the flag must change nothing."""
    from conftest import run_cli

    naive = run_cli("bazi_calc.py", "--year", 1992, "--month", 7, "--day", 1,
                    "--hour", 7, "--minute", 30, "--gender", "male",
                    "--as-of-year", 2026)
    aware = run_cli("bazi_calc.py", "--year", 1992, "--month", 7, "--day", 1,
                    "--hour", 7, "--minute", 30, "--gender", "male",
                    "--as-of-year", 2026, "--timezone", "Asia/Shanghai")

    assert naive["four_pillars"] == aware["four_pillars"]
    assert aware["timezone"]["dst_hours"] == 0.0
    assert not any("夏令时" in n for n in aware["notes"])


def test_unknown_timezone_is_a_clean_error():
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 1990, "--month", 1, "--day", 1,
                "--hour", 12, "--gender", "male",
                "--timezone", "Not/AZone", expect_rc=1)
    assert d["error"] == "invalid_timezone"


# --------------------------------------------------------------------------- #
# --sect: 早子/晚子 school selectable, default unchanged
# --------------------------------------------------------------------------- #

def test_sect_default_is_2_and_labelled():
    """00-intake.md:34 promises '默认子正换日并说明'. The code hardcoded sect 2 and
    never said so in the output."""
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 2020, "--month", 6, "--day", 15,
                "--hour", 23, "--minute", 30, "--gender", "male",
                "--as-of-year", 2026)
    assert d["sect"]["value"] == 2
    assert "子正换日" in d["sect"]["label"]
    assert d["four_pillars"]["day"]["ganzhi"] == "己丑"   # day pillar stays
    assert d["four_pillars"]["hour"]["ganzhi"] == "丙子"  # hour stem from next day


def test_sect_1_rolls_the_day_pillar_at_23():
    """子初换日: 23:00 already belongs to the next day, so the 日柱 advances."""
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 2020, "--month", 6, "--day", 15,
                "--hour", 23, "--minute", 30, "--gender", "male",
                "--as-of-year", 2026, "--sect", 1)
    assert d["sect"]["value"] == 1
    assert "子初换日" in d["sect"]["label"]
    assert d["four_pillars"]["day"]["ganzhi"] == "庚寅"
    assert d["four_pillars"]["hour"]["ganzhi"] == "丙子"


def test_sect_has_no_effect_outside_late_zi():
    from conftest import run_cli
    a = run_cli("bazi_calc.py", "--year", 2020, "--month", 6, "--day", 15,
                "--hour", 10, "--gender", "male", "--as-of-year", 2026, "--sect", 1)
    b = run_cli("bazi_calc.py", "--year", 2020, "--month", 6, "--day", 15,
                "--hour", 10, "--gender", "male", "--as-of-year", 2026, "--sect", 2)
    assert a["four_pillars"] == b["four_pillars"]
