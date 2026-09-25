"""黄历引擎的独立 oracle。

黄历此前是**零校验**的六个引擎之一: yi/ji/值神/二十八宿 全部原样透传
lunar_python, 没有任何断言检查它们对不对。而择日是本仓库唯一一类会让用户做
不可逆现实决策 (婚期、搬迁、安葬) 的输出。

这里不引入第二个第三方库 —— 值神与二十八宿都是**可机械推导**的, 用生成规则重算
再与引擎逐日比对, 是比"再装一个库"更强的 oracle: 它检验的是规则本身, 不是两个
实现是否碰巧同源。
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

pytestmark = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")

DIZHI = "子丑寅卯辰巳午未申酉戌亥"
JIAN_CHU = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]


def run_day(d: date) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "huangli_query.py"),
         "--date", d.isoformat()],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)


def derive_zhi_shen(d: date) -> str:
    """按 references/12-huangli.md §6 的排列规律独立推导值神。

    「每月以节令之后第一天为『建』, 其后依次循环」——
    等价于: 值神 = JIAN_CHU[(日支序 - 月支序) mod 12]。
    寅月寅日为建、卯月卯日为建, 即日支与月建同支之日为「建」。
    """
    from lunar_python import Solar
    lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
    day_branch = lunar.getDayInGanZhi()[1]
    month_branch = lunar.getMonthInGanZhiExact()[1]      # 按节气定月
    return JIAN_CHU[(DIZHI.index(day_branch) - DIZHI.index(month_branch)) % 12]


def _grid(start: date, days: int, step: int = 1):
    return [start + timedelta(days=i * step) for i in range(days)]


@pytest.mark.parametrize("d", _grid(date(2026, 1, 1), 60, 6),
                         ids=lambda d: d.isoformat())
def test_zhi_shen_matches_the_documented_rule(d):
    """引擎透传的 getZhiXing 必须等于文档规则推出的值神。"""
    got = run_day(d)["zhi_shen_12jianchu"]
    want = derive_zhi_shen(d)
    assert got == want, f"{d}: 引擎={got} 规则推导={want}"


def test_zhi_shen_cycles_without_gap_across_a_month():
    """值神必须逐日推进一位, 只在交节处重复一日 (节令换月时同支两日皆为建之类)。

    这条抓的是「整段错位」——单日比对抓不到的那种。
    """
    days = _grid(date(2026, 3, 1), 45)
    seq = [run_day(d)["zhi_shen_12jianchu"] for d in days]
    steps = [(JIAN_CHU.index(b) - JIAN_CHU.index(a)) % 12
             for a, b in zip(seq, seq[1:], strict=False)]
    assert set(steps) <= {0, 1}, f"值神跳位: {sorted(set(steps))}\n{list(zip(days, seq, strict=True))}"
    assert steps.count(0) <= 2, f"45 天内重复 {steps.count(0)} 次, 交节至多 2 次"
    assert set(seq) == set(JIAN_CHU), f"45 天未走满十二值神: {sorted(set(seq))}"


def test_huangdao_heidao_split_matches_the_reference():
    """黄道/黑道 六六分, 且十二值神不重不漏。"""
    md = (ROOT / "references" / "12-huangli.md").read_text(encoding="utf-8")
    import re
    rows = {}
    for category in ('黄道类', '黑道类'):
        match = re.search(rf'^\|\s*{category}\s*\|([^|]+)\|', md, re.MULTILINE)
        assert match, f'缺少 {category} 十二值神分类'
        names = re.sub(r'（[^）]*）', '', match.group(1)).strip().split('、')
        assert len(names) == len(set(names)) == 6, names
        rows[category] = set(names)
    huang, hei = rows['黄道类'], rows['黑道类']
    assert huang == {'青龙', '明堂', '金匮', '天德', '玉堂', '司命'}
    assert hei == {'天刑', '朱雀', '白虎', '天牢', '玄武', '勾陈'}
    assert len(huang | hei) == 12
    assert not (huang & hei)


@pytest.mark.parametrize("d", _grid(date(2026, 1, 1), 30, 11),
                         ids=lambda d: d.isoformat())
def test_jianchu_conflicts_are_surfaced_not_hidden(d):
    """引擎必须并列 通书结论 与 建除倾向, 并显式列出二者字面冲突之处。

    2026 上半年 181 天里 117 天存在这种冲突 (58 天引擎宜含表忌、59 天反之)。
    从前只发 yi/ji 且不注出处, 而 SKILL.md:51 声明择日「为纲之典」是《协纪辨方书》,
    读者会以为看到的就是建除的结论。
    """
    r = run_day(d)
    assert "通书" in r["yi_ji_source"] and "lunar_python" in r["yi_ji_source"]
    zs = r["zhi_shen_12jianchu"]
    assert r["jian_chu_tendency"], zs
    yi, ji = set(r["yi"] or []), set(r["ji"] or [])
    tend = r["jian_chu_tendency"]
    真冲突 = sorted(yi & set(tend["ji"])), sorted(ji & set(tend["yi"]))
    if any(真冲突):
        c = r["jian_chu_conflicts"]
        assert c, f"{d} 有冲突却没有列出: {真冲突}"
        assert c.get("engine_yi_but_jianchu_ji", []) == 真冲突[0]
        assert c.get("engine_ji_but_jianchu_yi", []) == 真冲突[1]
        # 旧提示「遇冲突以 yi/ji (通书结论) 为准」「通书结论已把神煞/宿/干支
        # 一并权衡」都没有出处。两套体系并列, 工具不替用户裁决。
        note = "".join(c["note"])
        assert "为准" not in note and "一并权衡" not in note
        assert "不裁决" in note
    else:
        assert not r["jian_chu_conflicts"], (d, r["jian_chu_conflicts"])


def test_yi_ji_source_claims_only_what_the_engine_does():
    r = run_day(date(2026, 6, 1))
    assert "查表" in r["yi_ji_source"]
    assert "一并权衡" not in r["yi_ji_source"]


def test_clause_conflicts_flag_only_yi_items_the_clause_names_verbatim():
    """2026-10-14 辛酉 是秋季天转日, 通书表却列 嫁娶、动土 为宜。

    条款原文「上官受职、出行商贾、造作、嫁娶」点名了嫁娶; 动土要靠「造作」
    去归类, 那是本工具的解读, 不是原文, 所以不标。
    """
    r = run_day(date(2026, 10, 14))
    assert r["ganzhi"]["day"] == "辛酉"
    assert {"嫁娶", "动土"} <= set(r["yi"]), "前提变了: 通书表不再同时列这两项"
    (hit,) = r["clause_conflicts"]
    assert hit["passage_id"] == "yuanhai:c052:p0004" and hit["kind"] == "天转"
    assert hit["yi_named_in_clause"] == ["嫁娶"]
    assert "不裁决" in hit["note"]
    # 地转日同理, 出行 也是原文点名的。
    later = run_day(date(2026, 10, 26))
    assert later["ganzhi"]["day"] == "癸酉"
    assert set(later["clause_conflicts"][0]["yi_named_in_clause"]) == {"嫁娶", "出行"}
    # 夏季天转丙午: 2026-06-01。
    summer = run_day(date(2026, 6, 1))
    assert summer["ganzhi"]["day"] == "丙午" and summer["clause_conflicts"][0]["kind"] == "天转"


@pytest.mark.parametrize("d", [date(2026, 10, 13), date(2026, 3, 10), date(2026, 6, 2)],
                         ids=lambda d: d.isoformat())
def test_clause_conflicts_are_empty_on_an_ordinary_day(d):
    assert run_day(d)["clause_conflicts"] == []


def run_markdown(d: date, question: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "huangli_query.py"),
         "--date", d.isoformat(), "--question", question, "--markdown"],
        capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr[-400:]
    return proc.stdout


def test_markdown_answers_the_asked_event_first():
    """A 黄历 question used to get only JSON. The first sentence now answers it,
    from the sourced day rules, and says where the almanac table disagrees."""
    lead = run_markdown(date(2026, 10, 29), "10月29日搬家可以吗？").split("\n\n")[0]
    assert lead.startswith("不行。2026-10-29（农历九月二十，丙子日）搬家需要避开：是歸忌日")
    assert "通书宜忌表却把「移徙」列为宜，与上面的条款不一致" in lead
    lead = run_markdown(date(2020, 6, 2), "那天结婚好不好").split("\n\n")[0]
    assert lead.startswith("2020-06-02") and "四忌日（夏季丙子）" in lead and "忌嫁娶" in lead
    lead = run_markdown(date(2026, 10, 30), "这天出门可以吗").split("\n\n")[0]
    assert lead.startswith("已查条款不忌。2026-10-30") and "通书宜忌表没有列「出行」" in lead


def test_markdown_does_not_stretch_the_rules_to_other_events():
    lead = run_markdown(date(2026, 10, 29), "今天装修可以吗").split("\n\n")[0]
    assert lead.startswith("这件事不在本库核过条款的事项里（只核了出行、结婚、搬家、开业）")
    general = run_markdown(date(2026, 10, 29), "今天适合干什么")
    assert general.startswith("2026-10-29（农历九月二十，丙子日），值神「满」。通书宜忌表宜：")
    assert "本库未核出处" in general  # the table's own standing, in layer 2
    for banned in ("仅供参考", "两书相反", "passage_id", "算不了"):
        assert banned not in general.split("\n\n")[0]


def test_day_prohibitions_are_published_per_event():
    r = run_day(date(2026, 10, 29))
    rules = {s: [h["label"] for h in hits] for s, hits in r["day_prohibitions"].items()}
    assert rules == {"travel": [], "wedding": [], "moving": ["歸忌"], "business": []}


def test_the_question_classifier_is_shared_and_strict():
    sys.path.insert(0, str(ROOT / "scripts"))
    from answer_style import event_of, question_kind
    assert event_of("下周三搬家行不行") == "moving"
    assert event_of("先结婚再搬家") is None      # two events: do not guess
    assert event_of("订婚选哪天") is None         # 納采問名 is another 用事
    assert question_kind("可以吗") == "yes_no" and question_kind("哪天好") == "choice"


@pytest.mark.parametrize("d", [date(2026, 10, 29), date(2026, 10, 14), date(2020, 6, 2), date(2026, 3, 10)],
                         ids=lambda d: d.isoformat())
def test_markdown_keeps_to_the_direct_answer_word_lists(d):
    sys.path.insert(0, str(ROOT / "scripts"))
    from answer_style import style_violations
    for question in ("", "这天搬家可以吗", "哪天结婚好", "开业行不行", "今天装修可以吗"):
        text = run_markdown(d, question) if question else run_markdown(d, "今天适合干什么")
        assert not style_violations(text), (question, text.split("\n\n")[0])


def test_markdown_on_a_tiandi_day_names_the_clause_once():
    """A 天转 day crashed --markdown: its clause_conflicts entry had no reader
    sentence. The asked event is stated in the lead, not repeated below."""
    text = run_markdown(date(2026, 10, 14), "这天结婚可以吗")
    assert text.startswith("不行。2026-10-14（农历九月初五，辛酉日）结婚需要避开：是秋季的天转日")
    assert "并列备查" not in text
    general = run_markdown(date(2026, 10, 26), "今天适合干什么").split("\n\n")
    assert general[0].endswith("其中「嫁娶、出行」，已核条款说这天忌，见下文。")
    assert any("而秋季的地转日，《渊海子平》说这天最忌嫁娶、出行（yuanhai:c052:p0004）" in p for p in general[1:])
