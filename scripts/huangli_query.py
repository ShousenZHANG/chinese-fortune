"""Daily 黄历 / 老黄历 query — almanac for a specific solar date.

Usage:
    python huangli_query.py [--date YYYY-MM-DD]

Outputs JSON with: 公历, 农历, 干支, 12 建除值神, 28 宿, 宜, 忌,
吉时/凶时, 喜神/财神/福神/贵神方位, 彭祖百忌, 胎神方位, 冲煞.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

from request_time import add_request_arguments, resolve_time
from utils import (
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    ok_envelope,
    require_lunar,
    warn,
)


def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception:
        return default


# --------------------------------------------------------------------------- #
# 十二建除 的一般倾向 — 与 references/12-huangli.md 「| 建除 | 含义 | 宜 | 忌 |」
# 那张表逐项一致 (tests/test_reference_consistency.py 强制)。
# --------------------------------------------------------------------------- #
#
# 注意这**不是** yi/ji 的替代品, yi/ji 也不是它的上级。lunar_python 的
# getDayYi/getDayJi 是按 (月干支, 日干支) 查一张内置通书表; 表里各条规则怎样取舍,
# 本库没有核到出处。二者在 2026 上半年 181 天里有 117 天字面冲突 (58 天引擎宜含
# 表忌、59 天引擎忌含表宜)。从前的提示说「通书结论已把神煞/宿/干支一并权衡」「遇冲突
# 以 yi/ji 为准」, 这两句都没有出处, 已删除。
#
# 从前引擎只发 yi/ji 且不注出处, 而 SKILL.md:51 声明黄历择日「为纲之典」是
# 《钦定协纪辨方书》、12-huangli.md:180 称建除是「黄历最核心的择日体系」——
# 读者会以为看到的就是建除的结论。现在两者并列, 冲突显式列出, 本工具不裁决。
JIAN_CHU_TENDENCY: dict[str, dict[str, list[str]]] = {
    "建": {"yi": ["上任", "入学", "求职", "出行"], "ji": ["动土", "破土"]},
    "除": {"yi": ["扫除", "求医", "祭祀", "解除"], "ji": ["嫁娶", "入宅"]},
    "满": {"yi": ["嫁娶", "开市", "入宅", "祈福"], "ji": ["动土", "安葬"]},
    "平": {"yi": ["平整地", "铺路"], "ji": ["求官", "求财"]},
    "定": {"yi": ["入宅", "安床", "订婚", "立约"], "ji": ["出行", "诉讼"]},
    "执": {"yi": ["祭祀", "捕猎", "立约"], "ji": ["出行", "开市"]},
    "破": {"yi": ["拆屋", "破土"], "ji": ["百事忌"]},
    "危": {"yi": ["安床", "祭祀"], "ji": ["出行", "登高", "行船"]},
    "成": {"yi": ["嫁娶", "入宅", "开市", "建造"], "ji": ["诉讼"]},
    "收": {"yi": ["入宅", "安葬", "纳财", "收成"], "ji": ["出行"]},
    "开": {"yi": ["开市", "上任", "入学", "出行"], "ji": ["动土", "安葬"]},
    "闭": {"yi": ["安葬", "筑堤", "封口"], "ji": ["嫁娶", "出行"]},
}


def _safe_method(obj: Any, name: str, default: Any = None) -> Any:
    """Call an optional method by name across lunar_python versions."""
    try:
        fn = getattr(obj, name)
    except AttributeError:
        return default
    return _safe(fn, default)


def _tiandi_conflicts(lunar: Any, day_yi: list[str] | None) -> list[dict]:
    """通书宜项里, 被天地转杀条款原文点名为「最忌」的那几项。

    只标出**原样**出现在条款原文里的宜项: 2026-10-14 辛酉 (秋季天转) 标出
    嫁娶, 不标动土 —— 把动土归入「造作」是本工具的解读, 不是条款的原话。
    与 jian_chu_conflicts 一样只并列两说, 不裁决。普通日子返回 []。
    """
    from fortune_ranking import SEASON_NAMES, season_of, tiandi_zhuan
    day = lunar.getDayInGanZhiExact()
    season = season_of(lunar.getMonthZhiExact())
    hit = tiandi_zhuan(day[0], day[1], season) if season else None
    if hit is None or season is None:
        return []
    named = [item for item in day_yi or [] if item in hit['quote']]
    if not named:
        return []
    return [{**hit, 'label': hit['kind'], 'day_ganzhi': day, 'season': season, 'yi_named_in_clause': named,
             'plain': f"{SEASON_NAMES[season]}的{hit['kind']}日，《渊海子平》说这天最忌{'、'.join(named)}",
             'note': '通书宜忌表把上列事项列为宜, 天地转杀条款原文把它们列为最忌。'
                     '两者是不同的体系; 本工具不裁决, 两说并列。'}]


# 通书宜项 -> the scenario whose 协纪 用事 name it is. 出行/移徙 rest on 卷十一's
# own notes 「出行同」「移徙同」 (see xieji_days.TERM_EQUIVALENCE).
_XIEJI_YI = {'出行': 'travel', '嫁娶': 'wedding', '移徙': 'moving', '开市': 'business'}


def _xieji_conflicts(lunar: Any, day_yi: list[str] | None) -> list[dict]:
    """通书宜项里, 《协纪辨方书》卷十写明「与吉神并仍忌」的那几项。

    例如 2020-06-02 丙子是夏季四忌, 协纪列嫁娶为所忌且「德神不能化解」,
    通书表却列嫁娶为宜。协纪自言「舊本無四忌今依起例補之」, 分歧由此而来。
    同样只并列, 不裁决。按正午所在的节气月判断; 交节当天上下午可能分属两月。
    """
    from xieji_days import prohibitions
    day, month = lunar.getDayInGanZhiExact(), lunar.getMonthZhiExact()
    found = []
    for item in day_yi or []:
        scenario = _XIEJI_YI.get(item)
        for hit in prohibitions(scenario, day, month) if scenario else []:
            found.append({**hit, 'yi_item': item,
                          'note': f'通书宜忌表列「{item}」为宜；《协纪辨方书》卷十把它列在{hit["label"]}的所忌里，'
                                  '并写明与吉神并仍忌。两者是不同的体系; 本工具不裁决, 两说并列。'})
    return found


# 事项 -> (通书表用字, 白话名). 通书表把搬家写作「移徙」, 与协纪注「移徙同」一致。
DAY_RULE_EVENTS = {'travel': ('出行', '出行'), 'wedding': ('嫁娶', '结婚'),
                   'moving': ('移徙', '搬家'), 'business': ('开市', '开业')}


def _asked_event(out: dict, scenario: str, kind: str, date: str) -> str:
    """The first sentence when the question names an event the rules know."""
    word, name = DAY_RULE_EVENTS[scenario]
    hits = out['day_prohibitions'][scenario]
    if hits:
        lead = (('不行。' if kind == 'yes_no' else '') + f'{date}{name}需要避开：是'
                + '；也是'.join(h['plain'] for h in hits) + '。')
        if word in (out['yi'] or []):
            lead += f'通书宜忌表却把「{word}」列为宜，与上面的条款不一致。'
        return lead
    listed = ('列为宜' if word in (out['yi'] or []) else '列为忌' if word in (out['ji'] or []) else '')
    table = f'通书宜忌表把「{word}」{listed}' if listed else f'通书宜忌表没有列「{word}」'
    opener = ('不建议。' if word in (out['ji'] or []) else '已查条款不忌。') if kind == 'yes_no' else ''
    return (f'{opener}{date}没有碰到本库已核的{name}忌日（天地转杀与《协纪辨方书》吉神化解不了的几种忌日）；'
            f'{table}。')


def _clash_items(clash: dict) -> list[str]:
    """The 宜 items one clause_conflicts entry flags."""
    return [clash['yi_item']] if 'yi_item' in clash else list(clash['yi_named_in_clause'])


def render_huangli(out: dict, question: str = '') -> str:
    """Plain-language 黄历 answer: the asked event first, then the day's facts."""
    from answer_style import event_of, question_kind, rule_detail
    lunar, gz = out['lunar_date'], out['ganzhi']
    date = (f"{out['solar_date']['iso']}（农历{lunar['month_chinese']}月{lunar['day_chinese']}，"
            f"{gz['day']}日）")
    scenario = event_of(question) if question else None
    yi, ji = '、'.join(out['yi'] or []) or '无', '、'.join(out['ji'] or []) or '无'
    if scenario:
        lead = _asked_event(out, scenario, question_kind(question), date)
    else:
        # A yes/no about an event the rules do not cover gets told so; a general
        # 「今天适合做什么」 is answered by the table itself.
        unknown = ('这件事不在本库核过条款的事项里（只核了出行、结婚、搬家、开业），只能看通书宜忌表：'
                   if question and question_kind(question) == 'yes_no' else '')
        lead = f"{unknown}{date}，值神「{out['zhi_shen_12jianchu']}」。通书宜忌表宜：{yi}；忌：{ji}。"
        barred = list(dict.fromkeys(item for clash in out['clause_conflicts'] for item in _clash_items(clash)))
        if barred:
            lead += f"其中「{'、'.join(barred)}」，已核条款说这天忌，见下文。"
    lines = [lead]
    if scenario:
        lines.append(f'通书宜忌表宜：{yi}；忌：{ji}。')
        for hit in out['day_prohibitions'][scenario]:
            lines.append(f"{DAY_RULE_EVENTS[scenario][1]}：{rule_detail(hit)}。")
    lines.append(f"通书宜忌表的来历：{out['yi_ji_source']}。表里的字按传统标签转述，不代表会发生什么。")
    zs, tendency = out['zhi_shen_12jianchu'], out['jian_chu_tendency']
    if tendency:
        lines.append(f"值神「{zs}」是十二建除之一，按本库建除表的一般倾向，宜：{'、'.join(tendency['yi'])}；"
                     f"忌：{'、'.join(tendency['ji'])}。")
    conflicts = out['jian_chu_conflicts']
    if conflicts:
        both = '、'.join(conflicts.get('engine_yi_but_jianchu_ji', []) + conflicts.get('engine_ji_but_jianchu_yi', []))
        lines.append(f'建除倾向与通书宜忌表在「{both}」上相反；两者是不同体系，本工具不裁决。')
    asked = DAY_RULE_EVENTS[scenario][0] if scenario else None
    for clash in out['clause_conflicts']:
        items = _clash_items(clash)
        if items == [asked]:
            continue  # the lead has already said it
        lines.append(f"通书宜忌表列「{'、'.join(items)}」为宜，而{rule_detail(clash)}。两者不一致，并列备查。")
    good = '、'.join(f"{s['shichen']}（{s['hour_range']}）" for s in out['ji_shi'])
    if good:
        lines.append(f'黄道时辰：{good}。这是时辰的传统分类，不是事故概率。')
    return '\n\n'.join(lines)


def _hour_pillars(lunar: Any) -> list[dict]:
    """Return the queried day's 13 时辰 blocks: 早子 … 亥 … 夜子.

    时辰 boundaries follow the classical odd-start convention (丑 01-03,
    寅 03-05 … 亥 21-23) — NOT even clock blocks (00-02, 02-04 …), which
    straddle two 时辰 and mislabel the second half. Each block is sampled at
    its midpoint so 干支/天神 are correct for the whole block.

    子时 is emitted as TWO rows because one civil day contains two different
    子 时柱 under the 晚子时 (sect-2) convention this project uses throughout
    (see bazi_calc.setSect(2)):

        早子 00:00-01:00 → 时干 from 五鼠遁 of the queried day's 日干
        夜子 23:00-24:00 → 时干 from 五鼠遁 of the NEXT day's 日干

    Collapsing them into one 23:00-01:00 row (as before v1.4.0) forced that
    row to carry the next day's 干支/天神/冲煞 while the object's own
    ganzhi.day and chong_sha described the queried day.

    Rows are emitted in clock order, so 早子 … 亥 form a contiguous run of the
    六十甲子 and 夜子 closes the day.

    吉凶 comes from the hour's 天神 黄道/黑道 (getTimeTianShenLuck), NOT from
    whether the hour has any 宜 — every 时辰 has non-empty 宜, so the latter
    would mark all 12 as 吉.
    """
    out: list[dict] = []
    try:
        from lunar_python import Solar  # type: ignore
        solar = lunar.getSolar()
        # (label, 时辰, sample hour, displayed range) in clock order.
        blocks = [("早子", "子", 0, "00:00-01:00")]
        blocks += [(b, b, h, f"{h:02d}:00-{h + 2:02d}:00") for b, h in zip(
            "丑寅卯辰巳午未申酉戌亥", [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21],
            strict=True)]
        blocks.append(("夜子", "子", 23, "23:00-24:00"))
        for label, branch, start, rng in blocks:
            s = Solar.fromYmdHms(solar.getYear(), solar.getMonth(),
                                 solar.getDay(), start, 30, 0)
            lh = s.getLunar()
            out.append({
                "shichen": label,
                "branch": branch,
                "hour_range": rng,
                "ganzhi": lh.getTimeInGanZhi(),
                "tian_shen": _safe_method(lh, "getTimeTianShen", None),
                "huang_hei_dao": _safe_method(lh, "getTimeTianShenType", None),
                "luck": _safe_method(lh, "getTimeTianShenLuck", None),
                "yi": _safe_method(lh, "getTimeYi", []),
                "ji": _safe_method(lh, "getTimeJi", []),
                "chong_sha": _safe_method(lh, "getTimeChongDesc", None),
            })
    except Exception as e:
        warn(f"hour pillars failed: {e}")
    return out


EPILOG = """Top-level JSON keys on stdout (UTF-8):
  input solar_date lunar_date ganzhi zhi_shen_12jianchu xiu_28 yi ji
  yi_ji_source jian_chu_tendency jian_chu_conflicts clause_conflicts
  day_prohibitions ji_shi xiong_shi shichen_detail directions peng_zu_bai_ji
  tai_shen_fang_wei chong_sha jieqi

day_prohibitions: {travel, wedding, moving, business} -> the sourced day rules
  that bar that event today (天地转杀 where it names it; 协纪 rules no 吉神
  lifts). [] means none of those rules applies, not that the day suits it.

--markdown prints a plain-language answer; with --question it answers that
  question first (出行/结婚/搬家/开业).

clause_conflicts: [] on most days. 宜 items that 天地转杀 names as 最忌, or that
  《协纪辨方书》卷十 forbids even beside 吉神 (月破/四廢/四忌/四窮/往亡/歸忌),
  with passage_id; side by side, not adjudicated.

shichen_detail: 13 rows, 早子 00:00-01:00 ... 亥 ... 夜子 23:00-24:00.
  Each row: shichen branch hour_range ganzhi tian_shen huang_hei_dao
  luck yi ji chong_sha

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="黄历日历查询 (今日宜忌 / 神位 / 吉凶时辰)"
    ,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_request_arguments(p)
    p.add_argument("--date", type=str, default=None,
                   help="日期 YYYY-MM-DD (默认今日)")
    p.add_argument("--question", type=str, default="",
                   help="所问之事, 例如「这天搬家可以吗」; 用于 --markdown 的首句")
    p.add_argument("--markdown", action="store_true",
                   help="输出白话回答而非 JSON")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    require_lunar()
    from lunar_python import Solar  # type: ignore

    try:
        dt, time_context = resolve_time(args, date_value=args.date, day_only=True)
    except ValueError as exc:
        json_print(error_envelope('huangli', 'invalid_time_context', str(exc)))
        return 1

    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, 12, 0, 0)
    lunar = solar.getLunar()

    # Almanac entries (lunar_python provides rich daily info)
    day_yi = _safe_method(lunar, "getDayYi", [])
    day_ji = _safe_method(lunar, "getDayJi", [])
    zhi_xing = _safe_method(lunar, "getZhiXing", None)
    # 建除倾向, 以及它与通书结论字面冲突之处 —— 不做裁决, 只如实并列。
    jian_chu = JIAN_CHU_TENDENCY.get(zhi_xing or "")
    conflicts: dict[str, list[str]] = {}
    if jian_chu:
        yi_set, ji_set = set(day_yi or []), set(day_ji or [])
        both_yi = sorted(yi_set & set(jian_chu["ji"]))
        both_ji = sorted(ji_set & set(jian_chu["yi"]))
        if both_yi:
            conflicts["engine_yi_but_jianchu_ji"] = both_yi
        if both_ji:
            conflicts["engine_ji_but_jianchu_yi"] = both_ji
        if conflicts:
            conflicts["note"] = [
                f"值神「{zhi_xing}」的建除倾向与通书宜忌表在上列项目上相左。",
                "两者是不同的体系; 本工具不裁决哪一方优先, 两说并列, 并向用户说明存在分歧。",
            ]
    xiu = _safe_method(lunar, "getXiu", None)
    zheng = _safe_method(lunar, "getZheng", None)
    animal_28 = _safe_method(lunar, "getAnimal", None)

    xi_shen = _safe_method(lunar, "getDayPositionXi", None)        # 喜神方位
    cai_shen = _safe_method(lunar, "getDayPositionCai", None)      # 财神方位
    fu_shen = _safe_method(lunar, "getDayPositionFu", None)        # 福神方位
    yang_gui = _safe_method(lunar, "getDayPositionYangGui", None)  # 阳贵神
    yin_gui = _safe_method(lunar, "getDayPositionYinGui", None)    # 阴贵神

    tai_shen = _safe_method(lunar, "getDayPositionTai", None)

    chong = _safe_method(lunar, "getDayChongDesc", None) or _safe_method(lunar, "getDayChongGan", None)
    sha = _safe_method(lunar, "getDaySha", None)

    peng_zu_gan = _safe_method(lunar, "getPengZuGan", None)
    peng_zu_zhi = _safe_method(lunar, "getPengZuZhi", None)

    # 今日吉时/凶时 — 按 时辰黄黑道吉凶 (黄道=吉, 黑道=凶), 非"有无宜事"
    ji_xiong_shichen = _hour_pillars(lunar)
    ji_shi = [s for s in ji_xiong_shichen if s.get("luck") == "吉"]
    xiong_shi = [s for s in ji_xiong_shichen if s.get("luck") == "凶"]

    # Nearest jieqi
    jieqi_now = _safe(lunar.getJieQi, None)
    prev_jq = _safe(lunar.getPrevJieQi, None)
    next_jq = _safe(lunar.getNextJieQi, None)

    out = {
        "input": vars(args),
        "time_context": time_context,
        "solar_date": {
            "iso": f"{solar.getYear():04d}-{solar.getMonth():02d}-{solar.getDay():02d}",
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(),
        },
        "lunar_date": {
            "year": lunar.getYear(), "month": lunar.getMonth(), "day": lunar.getDay(),
            "year_chinese": lunar.getYearInChinese(),
            "month_chinese": lunar.getMonthInChinese(),
            "day_chinese": lunar.getDayInChinese(),
            "zodiac": lunar.getYearShengXiao(),
        },
        "ganzhi": {
            "year": lunar.getYearInGanZhi(),
            "month": lunar.getMonthInGanZhi(),
            "day": lunar.getDayInGanZhi(),
        },
        "zhi_shen_12jianchu": zhi_xing,
        "xiu_28": {
            "xiu": xiu, "zheng": zheng, "animal": animal_28,
            "full": (f"{xiu}{zheng}{animal_28}" if xiu else None),
        },
        "yi": day_yi,
        "ji": day_ji,
        "yi_ji_source": (
            "lunar_python getDayYi/getDayJi — 通书系内置宜忌表, 按月干支与日干支查表; "
            "表内各条规则如何取舍, 本库未核出处"
        ),
        "jian_chu_tendency": jian_chu,
        "jian_chu_conflicts": conflicts,
        "clause_conflicts": _tiandi_conflicts(lunar, day_yi) + _xieji_conflicts(lunar, day_yi),
        "ji_shi": ji_shi,
        "xiong_shi": xiong_shi,
        "shichen_detail": ji_xiong_shichen,
        "directions": {
            "喜神": xi_shen,
            "财神": cai_shen,
            "福神": fu_shen,
            "阳贵神": yang_gui,
            "阴贵神": yin_gui,
        },
        "peng_zu_bai_ji": {
            "gan": peng_zu_gan, "zhi": peng_zu_zhi,
        },
        # 胎神只有方位; lunar_python 无 getDayPositionTaiDesc, 旧的 desc 键
        # 恒为 None (勿改调 getDayPositionTaiSuiDesc —— 那是太岁不是胎神).
        "tai_shen_fang_wei": {
            "position": tai_shen,
        },
        "chong_sha": {
            "chong": chong, "sha": sha,
        },
        "jieqi": {
            "today": jieqi_now,
            "prev": {"name": prev_jq.getName(), "solar": str(prev_jq.getSolar())} if prev_jq else None,
            "next": {"name": next_jq.getName(), "solar": str(next_jq.getSolar())} if next_jq else None,
        },
    }

    from fortune_ranking import day_prohibitions
    exact_day, exact_month = lunar.getDayInGanZhiExact(), lunar.getMonthZhiExact()
    out["day_prohibitions"] = {scenario: day_prohibitions(scenario, exact_day, exact_month)
                               for scenario in DAY_RULE_EVENTS}
    if args.markdown:
        print(render_huangli(ok_envelope("huangli", out), args.question))
    else:
        json_print(ok_envelope("huangli", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
