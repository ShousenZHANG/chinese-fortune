"""独立原例、可辨别反例和真实 CLI；来源见 docs/QIMEN-LIUREN-METHODS.md。"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
pytest.importorskip("lunar_python")

from liuren_cast import (  # noqa: E402
    build_si_ke,
    build_tian_di_pan,
    detect_zei_ke,
    fa_yong,
    fa_yong_yao_ke,
)
from qimen_cast import earth_plate, men_plate  # noqa: E402
from qimen_dingju import (  # noqa: E402
    determine_ju,
    futou,
    seasonal_context,
    zhi_shi_position,
)


def run(script, *args):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args],
                          capture_output=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("day,head,yuan", [
    ("甲子", "甲子", "上元"), ("戊辰", "甲子", "上元"),
    ("己卯", "己卯", "上元"), ("癸未", "己卯", "上元"),
    ("甲寅", "甲寅", "中元"), ("己巳", "己巳", "中元"),
    ("甲辰", "甲辰", "下元"), ("己未", "己未", "下元"),
    ("癸亥", "己未", "下元"),
])
def test_futou_uses_branch_of_five_day_head(day, head, yuan):
    assert futou(day) == (head, yuan)


@pytest.mark.parametrize("term,day,want", [
    ("芒种", "癸亥", ("阳遁", "下元", 9)),
    ("霜降", "甲寅", ("阴遁", "中元", 8)),
    ("冬至", "甲子", ("阳遁", "上元", 1)),
    ("夏至", "甲子", ("阴遁", "上元", 9)),
])
def test_yuanlingjing_dingju_examples(term, day, want):
    assert determine_ju(term, day) == want


@pytest.mark.parametrize("origin,hour,dun,raw,resolved", [
    (5, "丙辰", "阳遁", 7, 7),  # 原例：芒种癸亥，甲寅癸原在五。
    (8, "辛未", "阴遁", 1, 1),  # 原例：霜降甲寅，甲子戊原在八。
    (4, "乙丑", "阳遁", 5, 2),  # 4+1=5，数完才寄二。
    (1, "乙丑", "阴遁", 9, 9),  # 1-1回九；能检出阴遁双逆。
    (5, "甲子", "阳遁", 5, 2),
    (9, "癸酉", "阳遁", 9, 9),  # 旬内九步，九宫一圈。
])
def test_zhi_shi_counts_nine_palaces(origin, hour, dun, raw, resolved):
    assert zhi_shi_position(origin, hour, dun) == (raw, resolved)


def test_yuanlingjing_earth_and_door_examples():
    assert earth_plate("阳遁", 9) == {
        9: "戊", 1: "己", 2: "庚", 3: "辛", 4: "壬", 5: "癸", 6: "丁", 7: "丙", 8: "乙"}
    assert earth_plate("阴遁", 8) == {
        8: "戊", 7: "己", 6: "庚", 5: "辛", 4: "壬", 3: "癸", 2: "丁", 1: "丙", 9: "乙"}
    assert men_plate(5, 7, "阳遁")[7] == "死门"
    assert men_plate(8, 1, "阴遁")[1] == "生门"


@pytest.mark.parametrize("clock,term,dun", [
    ("2026-06-21T16:24:29+08:00", "芒种", "阳遁"),
    ("2026-06-21T16:24:30+08:00", "夏至", "阴遁"),
    ("2025-12-21T23:03:04+08:00", "大雪", "阴遁"),
    ("2025-12-21T23:03:05+08:00", "冬至", "阳遁"),
])
def test_actual_solstice_boundary_and_timezone_invariance(clock, term, dun):
    # 固定历表时刻，不从被测函数生成边界；晚一秒必须改变节气。
    instant = datetime.fromisoformat(clock)
    for zone in ("Asia/Shanghai", "Australia/Sydney", "America/New_York"):
        got = seasonal_context(instant.astimezone(ZoneInfo(zone)))
        assert got["name"] == term
        assert got["status"] == "instant_resolved"
        assert determine_ju(got["name"], "甲子")[0] == dun


def test_floating_time_cannot_claim_known_astronomical_instant():
    got = seasonal_context(datetime(2026, 6, 21, 16, 24))
    assert got["status"] == "floating_calendar_assumption"
    assert got["boundary_utc"] is None
    assert "不能确认" in got["note"]


def test_qimen_end_to_end_original_pattern_and_no_direction_score():
    got = run("qimen_cast.py", "--date", "2026-06-18", "--time", "08:00",
              "--target-timezone", "Asia/Shanghai")
    assert got["ganzhi"]["day"] == "癸亥"
    assert got["ganzhi"]["hour"] == "丙辰"
    assert (got["jieqi"], got["san_yuan"], got["ju_number"]) == ("芒种", "下元", 9)
    assert (got["zhi_fu_origin_palace"], got["zhi_shi_palace"], got["zhi_shi_men"]) == (5, 7, "死门")
    assert "auspicious_directions" not in got and "inauspicious_directions" not in got
    assert all(p["interpretation_status"] == "trigger_only_pending_rule_verification"
               for p in got["patterns"])


def test_legacy_days_is_explicit_and_only_covers_dingju():
    args = ("--date", "2026-06-18", "--time", "08:00", "--target-timezone", "Asia/Shanghai")
    got = run("qimen_cast.py", *args, "--ju-method", "legacy-days")
    assert got["method_profile"]["ding_ju"] == "legacy-days"
    assert "不回退" in got["method_profile"]["legacy_note"]


def test_qimen_midnight_changes_day_futou_without_resetting_term():
    before = run("qimen_cast.py", "--date", "2026-06-18", "--time", "23:59",
                 "--target-timezone", "Asia/Shanghai")
    after = run("qimen_cast.py", "--date", "2026-06-19", "--time", "00:00",
                "--target-timezone", "Asia/Shanghai")
    assert (before["ganzhi"]["day"], before["method_profile"]["futou"], before["san_yuan"]) == (
        "癸亥", "己未", "下元")
    assert (after["ganzhi"]["day"], after["method_profile"]["futou"], after["san_yuan"]) == (
        "甲子", "甲子", "上元")
    assert before["jieqi"] == after["jieqi"] == "芒种"


def test_solar_clock_correction_cannot_move_the_actual_solstice():
    got = run("qimen_cast.py", "--date", "2026-06-21", "--time", "16:25",
              "--target-timezone", "Asia/Shanghai", "--longitude", "105")
    assert got["time_context"]["effective_local"] < "2026-06-21T16:24"
    assert got["jieqi"] == "夏至" and got["ju_type"] == "阴遁"
    assert got["method_profile"]["solar_term"]["status"] == "instant_resolved"


@pytest.mark.parametrize("manual_args", [
    ["--ju-type", "yang"], ["--ju-number", "3"],
    ["--ju-type", "yang", "--ju-number", "0"],
])
def test_incomplete_or_zero_manual_ju_cannot_silently_revert_to_automatic(manual_args):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/qimen_cast.py"),
                           "--date", "2026-06-18", "--time", "08:00", *manual_args],
                          capture_output=True, encoding="utf-8")
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False


def cast(day, general, hour):
    pan = build_tian_di_pan(general, hour)
    lessons = build_si_ke(pan, day[0], day[1])
    return fa_yong(lessons, day[0], day[1], pan, general, hour)


@pytest.mark.parametrize("day,general,hour,tri,method", [
    ("甲寅", "丑", "辰", "丑亥亥", "八专"),  # 卷七原例；有申金遥克甲，卷一八专不论遥。
    ("丁未", "巳", "未", "丑巳巳", "八专"),  # 辰阴卯逆三至丑，不能从辰阳巳起。
    ("己未", "酉", "未", "酉酉酉", "八专"),  # 卷七独足原例，三传全同合法。
    ("癸巳", "午", "午", "丑戌未", "伏吟"),  # 阴日有克仍取干上丑，不能取支巳。
    ("乙亥", "午", "午", "辰亥巳", "伏吟"),  # 有克、初自刑交换日辰。
    ("壬辰", "酉", "酉", "亥辰戌", "伏吟"),  # 初次均自刑。
    ("丁卯", "子", "子", "卯子午", "伏吟"),  # 卷七杜传：子卯刑不复再传。
    ("甲寅", "子", "子", "寅巳申", "伏吟"),  # 与八专日重叠仍先伏吟。
    ("庚戌", "申", "寅", "寅申寅", "反吟"),  # 有克原例，初末相同合法。
    ("辛丑", "亥", "巳", "亥未辰", "反吟"),  # 无克井栏原例。
    ("丁未", "丑", "未", "巳丑丑", "反吟"),  # 井栏六日与八专重叠，不能作八专。
    ("甲寅", "卯", "寅", "辰巳午", "贼克"),  # 第二课卯克辰，先克后八专。
])
def test_siku_examples_and_condition_counterexamples(day, general, hour, tri, method):
    got = cast(day, general, hour)
    assert got["status"] == "supported"
    assert "".join(got[key] for key in ("chu_chuan", "zhong_chuan", "mo_chuan")) == tri
    assert method in got["method"]


def test_bazhuan_ignores_remote_control_only_after_checking_direct_control():
    pan = build_tian_di_pan("丑", "辰")
    lessons = build_si_ke(pan, "甲", "寅")
    assert detect_zei_ke(lessons) == ([], [])
    remote = fa_yong_yao_ke(lessons, "甲", pan)
    assert remote["chu_chuan"] == "申" and "蒿矢" in remote["method"]
    assert cast("甲寅", "丑", "辰")["chu_chuan"] == "丑"


@pytest.mark.parametrize("day,general,hour,method", [
    ("庚寅", "酉", "未", "涉害"),  # 下贼得辰与子，皆阳，不能任选第一。
    ("戊辰", "丑", "子", "别责"),
    ("己巳", "丑", "子", "昴星"),
])
def test_unsupported_branches_do_not_invent_transmissions(day, general, hour, method):
    got = cast(day, general, hour)
    assert got["status"] == "unsupported" and method in got["method"]
    assert [got[k] for k in ("chu_chuan", "zhong_chuan", "mo_chuan")] == [None] * 3
    assert got["reason"]


def test_liuren_partial_cli_preserves_lessons_and_nulls_derived_outputs():
    got = run("liuren_cast.py", "--date", "2026-05-16", "--time", "14:30")
    assert got["ok"] and got["completion_status"] == "partial"
    assert got["san_chuan"]["status"] == "unsupported"
    assert len(got["si_ke"]) == 4 and len(got["tian_pan"]) == 12
    assert got["san_chuan"]["chu_chuan_wuxing"] is None
    assert got["wang_xiang"] is None
    assert "三传未完成" in got["summary"]


def test_all_720_configurations_have_closed_status_and_no_fake_fallback():
    # 这是接口穷举，不声称 720 个独立原典预期。
    branches = "子丑寅卯辰巳午未申酉戌亥"
    for day_index in range(60):
        day = "甲乙丙丁戊己庚辛壬癸"[day_index % 10] + branches[day_index % 12]
        for general in branches:
            got = cast(day, general, "子")
            tri = [got[k] for k in ("chu_chuan", "zhong_chuan", "mo_chuan")]
            if got["status"] == "supported":
                assert all(item in branches for item in tri), (day, general, got)
            else:
                assert got["status"] == "unsupported" and tri == [None] * 3
                assert got["reason"]
            assert "简化" not in got["method"] and "取首位" not in got["method"]


def test_first_course_uses_day_stem_element_not_lodging_branch():
    # 辛金寄戌土，辛克卯为下贼；按戌土会误判卯木上克。
    pan = {b: b for b in "子丑寅卯辰巳午未申酉戌亥"}
    pan["戌"] = "卯"
    lessons = build_si_ke(pan, "辛", "子")
    below, above = detect_zei_ke(lessons)
    assert lessons[0]["lower_wuxing"] == "金"
    assert lessons[0] in below and lessons[0] not in above
