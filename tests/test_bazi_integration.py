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


# --------------------------------------------------------------------------- #
# --city: 出生地 feeds the computation instead of being collected and dropped
# --------------------------------------------------------------------------- #

def test_city_sets_longitude_and_timezone():
    """The Chengdu eval case: longitude correction flipped 时柱 丙辰 -> 乙卯, and
    the only way to get it was for the LLM to know Chengdu's longitude itself."""
    from conftest import run_cli
    by_city = run_cli("bazi_calc.py", "--year", 1995, "--month", 3, "--day", 8,
                      "--hour", 7, "--minute", 30, "--gender", "female",
                      "--as-of-year", 2026, "--city", "成都")
    by_lon = run_cli("bazi_calc.py", "--year", 1995, "--month", 3, "--day", 8,
                     "--hour", 7, "--minute", 30, "--gender", "female",
                     "--as-of-year", 2026, "--longitude", "104.07",
                     "--timezone", "Asia/Shanghai")
    assert by_city["four_pillars"]["hour"]["ganzhi"] == "乙卯"
    assert by_city["four_pillars"] == by_lon["four_pillars"]
    assert by_city["birthplace"]["name"] == "成都"


def test_explicit_longitude_overrides_city():
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 1995, "--month", 3, "--day", 8,
                "--hour", 7, "--minute", 30, "--gender", "female",
                "--as-of-year", 2026, "--city", "成都", "--longitude", "120")
    assert d["birthplace"]["longitude_source"] == "explicit"
    assert d["true_solar_time"]["longitude"] == 120.0


def test_unknown_city_is_a_clean_error():
    from conftest import run_cli
    d = run_cli("bazi_calc.py", "--year", 1995, "--month", 3, "--day", 8,
                "--hour", 7, "--gender", "female", "--city", "亚特兰蒂斯",
                expect_rc=1)
    assert d["error"] == "unknown_city"


# --------------------------------------------------------------------------- #
# 调候用神 — 与《穷通宝鉴》原文核对过的格 (v1.7.1 起逐条进行)
# --------------------------------------------------------------------------- #

def _tiaohou(key):
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "assets" / "tiaohou.json"
    return json.loads(p.read_text(encoding="utf-8"))["tiaohou"][key]


def test_tiaohou_jia_hai_uses_geng_ding():
    """《穷通宝鉴·论甲木·三冬甲木》: 「十月甲木, 庚丁为要, 丙火次之。忌壬水泛身,
    须戊土制之。……用庚, 土妻金子。用丁, 木妻火子。」 — the text names its own
    用神 as 庚 and 丁.

    The table had primary 丙戊 / secondary 庚 and no 丁 at all: the 「次之」 pair
    promoted to primary, the 「为要」 pair demoted or dropped. Its note read
    「丙戊两透」, which is verbatim the 乙木亥月 passage (「取丙为用, 戊土次之。
    丙戊两透, 科甲定然」) — the 乙 row appears to have been copied onto 甲.
    """
    cell = _tiaohou("甲|亥")
    assert cell["primary_yongshen"] == ["庚", "丁"], cell
    assert "丙" in cell["secondary_yongshen"] and "戊" in cell["secondary_yongshen"]


def test_tiaohou_yi_xu_excludes_bing():
    """《穷通宝鉴·论乙木·三秋乙木》: 「惟九月耑用癸水, 恐丙暖戊土为病也。」 — 丙 is
    named as the disease for this month specifically, and the 九月乙木 passage
    contains no 丙 anywhere.

    The table had primary 癸丙. The 丙 matches 乙|酉's primary (「必取丙火制金为急」)
    and appears to have bled across from the neighbouring month.
    """
    cell = _tiaohou("乙|戌")
    assert cell["primary_yongshen"] == ["癸"], cell
    assert "丙" not in cell["primary_yongshen"] + cell["secondary_yongshen"], cell
    assert cell["secondary_yongshen"] == ["辛"], cell


def test_tiaohou_records_its_audit_state():
    """The asset used to claim only 经现代术数家整理. Which cells have actually
    been checked against 原文, and which have not, must be visible — otherwise a
    partially audited table reads as a fully audited one."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "assets" / "tiaohou.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    audit = data["audit"]
    assert audit["verified_cells"], "no cell recorded as verified"
    assert len(audit["verified_cells"]) == 46
    assert {"甲|亥", "乙|戌", "辛|卯", "乙|卯"} <= set(audit["verified_cells"])
    # what was examined but deliberately left alone must stay visible
    assert audit["cells_examined"] == 120 and audit["of_total"] == 120
    assert audit["pending"]["not_examined"] == 0
    assert audit["pending"]["overturned_on_recheck"] == 17
    assert "secondary_yongshen" in audit["engine_note"]


def test_no_jishen_sits_in_secondary_yongshen():
    """The recurring defect this table had: a stem the passage names as 病/忌
    for that month sitting in secondary_yongshen, which inverts the reading.
    辛|卯 held 戊己 as 次用 where 《穷通宝鉴》 says 「见戊己为病」; 乙|卯 held 庚
    where the text says 「活木忌埋根之铁」. Eight cells were like this.
    """
    import json
    from pathlib import Path
    th = json.loads((Path(__file__).resolve().parent.parent / "assets" /
                     "tiaohou.json").read_text(encoding="utf-8"))["tiaohou"]
    bad = {k: sorted(set(c.get("ji_shen", [])) & set(c.get("secondary_yongshen", [])))
           for k, c in th.items()
           if set(c.get("ji_shen", [])) & set(c.get("secondary_yongshen", []))}
    assert not bad, f"忌神 listed as 次用: {bad}"


def test_verified_cells_carry_their_source_clause():
    """A cell claiming verification must show the sentence it was verified
    against, so the claim is checkable rather than asserted."""
    import json
    from pathlib import Path
    th = json.loads((Path(__file__).resolve().parent.parent / "assets" /
                     "tiaohou.json").read_text(encoding="utf-8"))["tiaohou"]
    verified = [k for k, c in th.items() if c.get("verified_against_source")]
    assert len(verified) >= 35, len(verified)
    missing = [k for k in verified
               if not (th[k].get("source_clause") or th[k].get("source"))]
    assert not missing, f"verified but no source quoted: {missing}"


def test_tiaohou_notes_do_not_contradict_a_named_jishen():
    """notes is printed verbatim into yong_shen.reason, so it reaches the
    reader. A note must not promise fortune from a stem the same cell marks
    as 忌 — 辛|卯's old note read 壬戊两透, 富贵显达 while its source says that
    pairing makes 平常之人."""
    import json
    import re
    from pathlib import Path
    th = json.loads((Path(__file__).resolve().parent.parent / "assets" /
                     "tiaohou.json").read_text(encoding="utf-8"))["tiaohou"]
    offenders = []
    for k, c in th.items():
        note = c.get("notes", "")
        for stem in c.get("ji_shen", []):
            if re.search(rf"{stem}[^。;,]{{0,6}}(两透|双透)[^。;,]{{0,8}}(富贵|显达|科甲)", note):
                offenders.append((k, stem))
    assert not offenders, offenders


def test_cimu_and_xuetang_match_their_own_reference():
    """词馆 is the 临官(禄) position of the day stem, 学堂 the 长生 position, and
    references/19-shensha.md §2.7 tabulates both. The asset shipped 戊申 己酉
    庚亥 辛子 壬寅 癸卯 for 词馆 — six of ten stems disagreeing with the repo's
    own reference and with 《三命通会》 卷三 论十干禄.
    """
    import json
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    md = (root / "references" / "19-shensha.md").read_text(encoding="utf-8")
    assets = json.loads((root / "assets" / "shensha.json").read_text(encoding="utf-8"))
    table = {e["name"]: e.get("qi_fa_table", {})
             for grp in ("ji_shen", "xiong_sha") for e in assets.get(grp, [])}

    def parse(section):
        # bound at the NEXT bold heading, not the next ###: 学堂 and 词馆 share
        # one ### section, so splitting on ### swallows both tables.
        rest = md.split(section)[1]
        body = rest.split(chr(10) + "**")[0]
        out = {}
        pat = r"\|\s*([甲乙丙丁戊己庚辛壬癸、]+)\s*\|\s*([寅卯辰巳午未申酉戌亥子丑])\s*\|"
        for stems, branch in re.findall(pat, body):
            for s in stems.split("、"):
                out[s] = branch
        return out

    for name, section in (("词馆", "**词馆起法**"), ("学堂", "**学堂起法**")):
        want = parse(section)
        assert len(want) == 10, (name, want)
        got = table[name]
        assert got == want, f"{name}: asset {got} != reference {want}"


def test_fuxing_guiren_is_the_day_stem_shishen_under_wushu_dun():
    """福星贵人 was flagged as a clear-error against 《三命通会》「丁宜亥」 — but
    the repo derives it from the DAY stem, and every one of the ten values is
    exactly where that day's 食神 falls in the 五鼠遁 hour cycle. Deriving the
    table from the rule reproduces the asset, so the entry is regular, not
    copied; the 起法 is now recorded on the entry and locked here.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    assets = json.loads((root / "assets" / "shensha.json").read_text(encoding="utf-8"))
    got = next(e for e in assets["ji_shen"] if e["name"] == "福星贵人")

    gan = "甲乙丙丁戊己庚辛壬癸"
    zhi = "子丑寅卯辰巳午未申酉戌亥"
    # 五鼠遁: 甲己起甲子, 乙庚起丙子, 丙辛起戊子, 丁壬起庚子, 戊癸起壬子.
    first_hour_stem = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
                       "辛": "戊", "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}
    want = {}
    for day_stem in gan:
        shi_shen = gan[(gan.index(day_stem) + 2) % 10]   # 食神: 同性而我生
        start = gan.index(first_hour_stem[day_stem])
        want[day_stem] = zhi[(gan.index(shi_shen) - start) % 10]

    assert got["qi_fa_table"] == want, (got["qi_fa_table"], want)
    assert "食神" in got["qi_fa"] and "五鼠遁" in got["qi_fa"]


# --------------------------------------------------------------------------- #
# --lunar 输入契约 — 农历日期必须先转公历, 再做真太阳时/经度校正
# --------------------------------------------------------------------------- #

def _run_bazi(*args):
    import json
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "bazi_calc.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.stdout.strip(), (
        f"no stdout (rc={proc.returncode})\nstderr={proc.stderr[-800:]}")
    return json.loads(proc.stdout), proc


def test_lunar_leap_day_birthdays_do_not_crash():
    """农历二月三十 是真实存在的生日 (1993 年那一天 = 公历 1993-03-22), 而
    longitude_correction 拿它当公历构造 date(1993, 2, 30) → 未捕获 ValueError,
    stdout 无 JSON, stderr 吐带绝对路径的 traceback。1900-2100 间这类生日 273 个。

    根因是农历→公历转换排在校正之后; 转换提前后, 校正永远只收到公历日期。
    """
    d, proc = _run_bazi("--lunar", "--year", 1993, "--month", 2, "--day", 30,
                        "--hour", 10, "--gender", "male")
    assert d["ok"] is True, d
    assert proc.returncode == 0
    assert (d["solar_date"]["year"], d["solar_date"]["month"]) == (1993, 3)
    assert d["four_pillars"]["year"]["ganzhi"] == "癸酉"


def test_lunar_day_rollover_does_not_fake_a_month_length_error():
    """day_offset 从前加在**农历**日上, 于是 农历五月三十 + 1 天 撞上「该农历月
    只有 30 天」, 一个完全合法的生日被一条假错误拒收。现在偏移加在公历日上。
    """
    d, _ = _run_bazi("--lunar", "--year", 1990, "--month", 5, "--day", 30,
                     "--hour", 23, "--minute", 55, "--longitude", 135,
                     "--gender", "male")
    assert d["ok"] is True, d
    # 23:55 @ 135°E 经度修正 +60 min → 翻到次日
    assert (d["solar_date"]["year"], d["solar_date"]["month"],
            d["solar_date"]["day"]) == (1990, 6, 23)


def test_gregorian_nonexistent_date_is_rejected_not_fabricated():
    """Solar.fromYmdHms 不校验日期真实性 —— 1990-02-31 会被接受并给出一个农历
    转换。_validate_args 的 1-31 也放行。必须自己用 date() 验一次。
    """
    d, _ = _run_bazi("--year", 1990, "--month", 2, "--day", 31,
                     "--hour", 10, "--gender", "male")
    assert d["ok"] is False
    assert d["error"] == "invalid_date"


def test_lunar_input_equation_of_time_comes_from_the_solar_day():
    """均时差按 day_of_year 求。农历日期当公历用时, 农历1990腊月初一 (= 公历
    1991-01-16) 会取到 +10.13 分而非 -9.69 分, 差 19.8 分钟 —— 足以让时辰边界
    附近的人整位跳时柱。这里直接比对 --lunar 与等价公历输入的真太阳时。
    """
    lun, _ = _run_bazi("--lunar", "--year", 1990, "--month", 12, "--day", 1,
                       "--hour", 12, "--longitude", 116.4,
                       "--gender", "male")
    sol, _ = _run_bazi("--year", 1991, "--month", 1, "--day", 16,
                       "--hour", 12, "--longitude", 116.4,
                       "--gender", "male")
    assert lun["ok"] and sol["ok"]
    assert lun["solar_date"] == sol["solar_date"]
    assert lun["true_solar_time"] == sol["true_solar_time"], (
        lun["true_solar_time"], sol["true_solar_time"])
    assert lun["four_pillars"] == sol["four_pillars"]


def test_lunar_input_resolves_timezone_from_the_solar_day():
    """resolve_timezone_offset 是第三个按公历日期取值的消费者, 上一轮只搬了两个。
    后果一: 农历二月三十 这类真实生日只要带 --city (会自动填 timezone, 是最常见
    用法) 就返回 ok:false + 误导性的 invalid_timezone。后果二: 历史夏令时按公历
    日期立法, 拿农历日期查表会整整差 1 小时 —— 1986-1991 窗口尤甚。
    """
    from lunar_python import Lunar
    d, _ = _run_bazi("--lunar", "--year", 1993, "--month", 2, "--day", 30,
                     "--hour", 10, "--city", "北京", "--gender", "male")
    assert d["ok"] is True, d
    assert d["four_pillars"]["year"]["ganzhi"] == "癸酉"

    # 夏令时窗口内, --lunar 与等价公历输入必须给出同一个偏移与同一副四柱。
    for ly, lm, ld in [(1986, 3, 26), (1988, 4, 15), (1990, 5, 1), (1991, 6, 10)]:
        s = Lunar.fromYmdHms(ly, lm, ld, 14, 0, 0).getSolar()
        a, _ = _run_bazi("--lunar", "--year", ly, "--month", lm, "--day", ld,
                         "--hour", 14, "--city", "北京", "--gender", "male")
        b, _ = _run_bazi("--year", s.getYear(), "--month", s.getMonth(),
                         "--day", s.getDay(), "--hour", 14, "--city", "北京",
                         "--gender", "male")
        assert a["ok"] and b["ok"], (a, b)
        assert a["timezone"] == b["timezone"], (ly, lm, ld, a["timezone"], b["timezone"])
        assert a["four_pillars"] == b["four_pillars"], (ly, lm, ld)


def test_tiaohou_primary_yongshen_reaches_the_output_for_representative_cells():
    """调候用神 决定大运流年吉凶/方位/颜色/行业 —— 一格错则整份批断反号。变异实证:
    把某格的 primary_yongshen 从 甲 改成 丙, 全量套件仍全绿。

    以往对 tiaohou.json 的断言只覆盖「已核对格的字段形状」, 不覆盖「这个值真的
    走到了输出」。这里挑四个不同日干/月支的格, 端到端跑到 yong_shen.primary。
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    table = json.loads(
        (root / "assets" / "tiaohou.json").read_text(encoding="utf-8"))["tiaohou"]

    # (公历生日, 期望的日干|月支, 该格的 primary_yongshen[0])
    cases = [
        ((1990, 5, 10, 14), "戊|巳"),
        ((1990, 1, 15, 10), "己|丑"),
        ((1985, 8, 20, 10), "丙|申"),
        ((2000, 11, 5, 10), "壬|亥"),
    ]
    checked = 0
    for (y, mo, dd, hh), _hint in cases:
        d, _ = _run_bazi("--year", y, "--month", mo, "--day", dd, "--hour", hh,
                         "--gender", "male")
        assert d["ok"], d
        key = f'{d["day_master"]["stem"]}|{d["four_pillars"]["month"]["branch"]}'
        cell = table[key]
        want = cell["primary_yongshen"][0]
        ys = d.get("yong_shen") or {}
        if not ys.get("tiaohou_match"):
            continue          # 该盘走的是扶抑路径, 不检验调候
        assert ys["primary"] == want, (
            f"{key}: 引擎输出用神 {ys['primary']}, 而 tiaohou.json 该格是 {want}")
        # notes 原样进 reason, 也一并锁住 —— 它会被 Claude 转述给用户
        assert cell["notes"][:8] in ys["reason"], (key, ys["reason"][:80])
        checked += 1
    assert checked >= 3, f"只有 {checked} 个用例走到调候路径, 覆盖不足"


def test_tiaohou_primary_yongshen_table_is_locked():
    """120 格的 primary_yongshen 整表锁死。

    上一条端到端测试只能覆盖它恰好排到的那几格; 缺陷可以落在另外 116 格的任何一格,
    而每一格都直接决定一份批断的用神 —— 进而决定大运流年吉凶、方位、颜色、行业。
    变异实证: 改任意一格的 primary 而不动别处, 端到端用例照样全绿。

    这里锁的是**当前值**, 不是「正确值」—— 46 格已与《穷通宝鉴》原文核对
    (见 audit.verified_cells), 其余 74 格仍应视为未核。改动任何一格都必须同时
    更新这里的哈希, 好让改动在 diff 里显形而不是静悄悄溜过去。
    """
    import hashlib
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    data = json.loads(
        (root / "assets" / "tiaohou.json").read_text(encoding="utf-8"))
    cells = data["tiaohou"]
    assert len(cells) == 120, len(cells)

    primaries = {k: v["primary_yongshen"] for k, v in sorted(cells.items())}
    blob = json.dumps(primaries, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    assert digest == "6521859ffbe59ad4cf10720781a8e59ec18f292bb3146c6e445ae7128cbfa741", (
        "调候 primary_yongshen 有改动。确认无误后更新此哈希, 并在提交信息里写清"
        f"改了哪几格、依据是什么。当前 sha256={digest}")

    # 每格必须非空且只含天干 —— 结构性护栏, 与上面的哈希互补。
    for key, prim in primaries.items():
        assert prim, f"{key} 的 primary_yongshen 为空"
        assert all(c in "甲乙丙丁戊己庚辛壬癸" for c in prim), (key, prim)

    verified = [k for k, v in cells.items() if v.get("verified_against_source")]
    assert len(verified) == 46, (
        f"已核对格数从 46 变成 {len(verified)} —— 若确有新核对, 更新此数并在"
        "audit.verified_cells 里同步登记")
