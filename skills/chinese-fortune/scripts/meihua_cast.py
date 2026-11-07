"""梅花易数 (Plum Blossom Numerology).

Subcommands:
    time                                  — 年月日时起卦
    numbers --upper N --lower N           — 二数起卦 (no explicit change line)
    name --text 中文                      — 字数起卦
    count --count N                       — 物数占（meihua:c001:p0021）
    sound --count N                       — 声音占（meihua:c001:p0022）
    length --zhang Z --chi C | --chi C --cun U — 丈尺占、尺寸占（meihua:c001:p0035、p0036）
    object --trigram 乾 --direction 南    — 后天端法：物卦为上、方卦为下（meihua:c001:p0049）

Every cast also carries ``timing``: 应期 only in the forms the book states (whole number of the
trigrams; 生体/比和 and 克体 elements as days; for 后天 casts walking/standing/sitting).

Output includes 主卦, 变卦, 互卦 and 体卦/用卦/体用关系 (生/克/比和).
The classical profile omits seasonal strength judgments; legacy-gregorian
can expose the old Gregorian-month diagnostic, explicitly labeled as such.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from classical_time_numbers import add_calendar_arguments, time_numbers
from request_time import add_request_arguments, resolve_time
from utils import (
    BAGUA,
    BINARY_TO_TRIGRAM,
    WUXING_GEN,
    WUXING_KE,
    XIANTIAN_NUM_TO_TRIGRAM,
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    ok_envelope,
    shichen_number,
)
from yijing_cast import (
    changed_lines,
    hex_lookup_by_trigrams,
    line_visual,
    lines_to_trigrams,
    load_hex_assets,
    nuclear_lines,
)


# 时辰 number: 子=1 .. 亥=12 (used for 起卦)
def shichen_num(hour: int) -> int:
    return shichen_number(hour)


# Build 6 raw line values from upper/lower trigram + a 1..6 changing line.
def build_lines(upper_tri: str, lower_tri: str, change_line: int) -> list[int]:
    upper_bin = BAGUA[upper_tri]["binary"]
    lower_bin = BAGUA[lower_tri]["binary"]
    lines: list[int] = []
    # BAGUA["binary"] is top-to-bottom, so 初爻 is bit 2 (see yijing_cast).
    for i in range(3):
        lines.append(7 if (lower_bin >> (2 - i)) & 1 else 8)
    for i in range(3):
        lines.append(7 if (upper_bin >> (2 - i)) & 1 else 8)
    idx = change_line - 1
    lines[idx] = 9 if lines[idx] == 7 else 6
    return lines


# 体用关系: which trigram contains the 动爻 (changing line) is 用; the other is 体.
def ti_yong(upper_tri: str, lower_tri: str, change_line: int) -> tuple[str, str]:
    if 1 <= change_line <= 3:
        return upper_tri, lower_tri  # 体 = upper, 用 = lower (动在下)
    return lower_tri, upper_tri      # 体 = lower, 用 = upper (动在上)


# Relation between two trigrams' 五行: 生我 (生体), 我生 (体生), 比和, 克我 (克体), 我克 (体克)
def ti_yong_relation(ti_tri: str, yong_tri: str) -> str:
    ti_wx = BAGUA[ti_tri]["wuxing"]
    yong_wx = BAGUA[yong_tri]["wuxing"]
    if ti_wx == yong_wx:
        return "比和"
    if WUXING_GEN.get(yong_wx) == ti_wx:
        return "用生体 (吉)"
    if WUXING_GEN.get(ti_wx) == yong_wx:
        return "体生用 (耗体)"
    if WUXING_KE.get(yong_wx) == ti_wx:
        return "用克体 (凶)"
    if WUXING_KE.get(ti_wx) == yong_wx:
        return "体克用 (吉)"
    return "未知"


# 体卦旺衰 — 按月令五行。
#
# 土王四季: 辰未戌丑四个季末月土旺 (严格说是每季末 18 天), 对应公历约 4/7/10/1 月。
# 这四个月从前被并进了木/火/金/水, 于是 SEASON_WX_BY_MONTH 十二个月里没有一个是
# 土, `.get(month, "土")` 的默认分支对任何合法月份都不可达 —— 体卦为 艮 或 坤
# (五行属土) 时, ti_state 结构性地永远拿不到「旺」, 八个卦里有两个的旺衰判断被
# 系统性压低, 而输出照样把它当确定结论交给用户。
#
# 仅 legacy-gregorian 兼容诊断使用本表。它没有计算节令瞬间或季末 18 天分界,
# 不能当作已核古法旺衰; classical 默认不输出这组判断。
SEASON_WX_BY_MONTH: dict[int, str] = {
    # 公历月 -> 当令五行 (对应 寅卯/巳午/申酉/亥子 四组 + 辰未戌丑 四季月)
    2: "木", 3: "木",
    5: "火", 6: "火",
    8: "金", 9: "金",
    11: "水", 12: "水",
    4: "土", 7: "土", 10: "土", 1: "土",
}


def ti_state(ti_tri: str, month: int) -> str:
    ti_wx = BAGUA[ti_tri]["wuxing"]
    season_wx = SEASON_WX_BY_MONTH[month]
    if ti_wx == season_wx:
        return "旺"
    if WUXING_GEN.get(season_wx) == ti_wx:
        return "相"
    if WUXING_GEN.get(ti_wx) == season_wx:
        return "休"
    if WUXING_KE.get(ti_wx) == season_wx:
        return "囚"
    if WUXING_KE.get(season_wx) == ti_wx:
        return "死"
    return "?"


# --------------------------------------------------------------------------- #
# Cast methods
# --------------------------------------------------------------------------- #

def cast_by_time(now: datetime, profile: str = 'classical', leap_policy: str | None = None) -> dict:
    numbers = time_numbers(now, profile, leap_policy)
    return {'method': 'time', 'now_iso': now.isoformat(),
            'ymd': [now.year, now.month, now.day], 'shichen': numbers['hour_number'],
            **numbers, 'upper_tri': XIANTIAN_NUM_TO_TRIGRAM[numbers['upper_num']],
            'lower_tri': XIANTIAN_NUM_TO_TRIGRAM[numbers['lower_num']]}


def cast_by_numbers(upper: int, lower: int) -> dict:
    upper_n = ((upper - 1) % 8) + 1
    lower_n = ((lower - 1) % 8) + 1
    total = upper + lower
    change = ((total - 1) % 6) + 1
    return {
        "method": "numbers",
        "upper_num": upper_n, "lower_num": lower_n, "change_num": change,
        "input_total": total,
        "upper_tri": XIANTIAN_NUM_TO_TRIGRAM[upper_n],
        "lower_tri": XIANTIAN_NUM_TO_TRIGRAM[lower_n],
    }


def cast_by_text(text: str) -> dict:
    s = "".join(ch for ch in text if not ch.isspace())
    n = len(s)
    half = n // 2
    upper_n = (half % 8) or 8
    lower_n = ((n - half) % 8) or 8
    change = (n % 6) or 6
    return {
        "method": "name",
        "text": text,
        "text_len": n,
        "upper_num": upper_n, "lower_num": lower_n, "change_num": change,
        "upper_tri": XIANTIAN_NUM_TO_TRIGRAM[upper_n],
        "lower_tri": XIANTIAN_NUM_TO_TRIGRAM[lower_n],
    }


MAX_COUNT = 100000
# 八卦萬物屬類各卦「方道」一行（乾坤震巽坎離艮兌依次）。
DIRECTION_TRIGRAM: dict[str, tuple[str, str]] = {
    '西北': ('乾', 'meihua:c001:p0121'), '西南': ('坤', 'meihua:c001:p0153'), '东': ('震', 'meihua:c001:p0183'),
    '东南': ('巽', 'meihua:c001:p0214'), '北': ('坎', 'meihua:c001:p0244'), '南': ('离', 'meihua:c001:p0275'),
    '东北': ('艮', 'meihua:c001:p0305'), '西': ('兑', 'meihua:c001:p0336'),
}
SIMPLIFY = str.maketrans('東離兌', '东离兑')
TRIGRAM_NUMBER = {name: info['number_xiantian'] for name, info in BAGUA.items()}


def _count(value: int, what: str) -> int:
    if not 1 <= value <= MAX_COUNT:
        raise ValueError(f'{what}须是 1–{MAX_COUNT} 的整数；原文没说零或负数怎么取卦')
    return value


def _tri(number: int) -> str:
    return XIANTIAN_NUM_TO_TRIGRAM[(number - 1) % 8 + 1]


def _numbers_cast(method: str, upper: int, lower: int, change: int, **extra: object) -> dict:
    return {'method': method, 'upper_num': (upper - 1) % 8 + 1, 'lower_num': (lower - 1) % 8 + 1,
            'change_num': (change - 1) % 6 + 1, 'upper_tri': _tri(upper), 'lower_tri': _tri(lower), **extra}


def cast_by_count(count: int, now: datetime) -> dict:
    """物数占：数为上卦，时数为下卦，卦数并时数除六取爻。"""
    hour = shichen_number(now.hour)
    n = _count(count, '物数')
    return _numbers_cast('count', n, hour, n + hour, count=n, hour_number=hour, source='meihua:c001:p0021')


def cast_by_sound(count: int, now: datetime) -> dict:
    """声音占：声数为上卦，声数加时数为下卦。"""
    hour = shichen_number(now.hour)
    n = _count(count, '声数')
    return _numbers_cast('sound', n, n + hour, n + hour, count=n, hour_number=hour, source='meihua:c001:p0022',
                         change_basis='原文只写上下卦；取爻照同章物數占例「卦數並時數總除六取動爻」')


def cast_by_length(now: datetime, *, zhang: int | None = None, chi: int | None = None,
                   cun: int | None = None) -> dict:
    """丈尺占不加时、寸数不用；尺寸占加时、分数不用。"""
    hour = shichen_number(now.hour)
    if zhang is not None and chi is not None:
        z, c = _count(zhang, '丈数'), _count(chi, '尺数')
        return _numbers_cast('length', z, c, z + c, zhang=z, chi=c, ignored=['寸'] if cun is not None else [],
                             source='meihua:c001:p0035')
    if zhang is None and chi is not None and cun is not None:
        c, u = _count(chi, '尺数'), _count(cun, '寸数')
        return _numbers_cast('length', c, u, c + u + hour, chi=c, cun=u, hour_number=hour, ignored=[],
                             source='meihua:c001:p0036')
    raise ValueError('丈尺占给 --zhang 和 --chi；尺寸占给 --chi 和 --cun')


def cast_by_object(trigram: str, direction: str, now: datetime) -> dict:
    """后天端法：物卦为上，方卦为下，两卦先天数加时数取爻（meihua:c002:p0007 起卦合用先天数）。"""
    upper = trigram.translate(SIMPLIFY)
    if upper not in BAGUA:
        raise ValueError(f'物卦须是八卦之一（乾兑离震巽坎艮坤）：{trigram!r}；按八卦萬物屬類先把物归到卦')
    place = direction.translate(SIMPLIFY)
    place = place[1:] if place.startswith('正') else place
    place = place[:-1] if place.endswith('方') else place
    if place not in DIRECTION_TRIGRAM:
        raise ValueError(f'方位须是八方之一（{"、".join(DIRECTION_TRIGRAM)}）：{direction!r}')
    lower, fang = DIRECTION_TRIGRAM[place]
    hour = shichen_number(now.hour)
    total = TRIGRAM_NUMBER[upper] + TRIGRAM_NUMBER[lower] + hour
    return {'method': 'object', 'object_trigram': upper, 'direction': place, 'direction_source': fang,
            'upper_num': TRIGRAM_NUMBER[upper], 'lower_num': TRIGRAM_NUMBER[lower], 'hour_number': hour,
            'change_num': (total - 1) % 6 + 1, 'upper_tri': upper, 'lower_tri': lower, 'houtian_total': total,
            'source': 'meihua:c001:p0049'}


# --------------------------------------------------------------------------- #
# 应期
# --------------------------------------------------------------------------- #

ELEMENT_BRANCHES = {'木': ['寅', '卯'], '火': ['巳', '午'], '土': ['辰', '戌', '丑', '未'], '金': ['申', '酉'],
                    '水': ['亥', '子']}
TIMING_SOURCES = (
    ('meihua:c003:p0040', '遠者，以全卦之數為年期；近者，以全卦之數為月期。又近者，以全卦為日期也',
     '全卦之数按远近作年、月、日'),
    ('meihua:c003:p0040', '但以生體及比和之年月為吉期，克體之年月為不吉之期也', '生体比和为吉期，克体为不吉之期'),
    ('meihua:c003:p0041', '巽五日而坤八日，離三朝而坎六朝', '卦数作日数'),
    ('meihua:c003:p0041', '假如天地否卦，上天一而下地八', '上下卦数相加'),
)
HOUTIAN_SOURCES = (
    ('meihua:c002:p0007', '後天則以卦數加時數，總之而分行臥坐立之遲速，以為事應之期', '后天卦数加时数'),
    ('meihua:c001:p0072', '故行則應速，以逐成卦之數，中分而取其半也。坐則事應遲，當倍其成卦之數而定之也。'
     '立則半遲半速，止以成卦之數定之可也', '行减半、坐加倍、立照数'),
)


def _relation(body: str, other: str) -> str | None:
    b, o = BAGUA[body]['wuxing'], BAGUA[other]['wuxing']
    if b == o:
        return '比和'
    if WUXING_GEN.get(o) == b:
        return '生体'
    if WUXING_KE.get(o) == b:
        return '克体'
    return None


def timing(meta: dict, *, body: str, use: str, nuclear: tuple[str, str], changed: str) -> dict:
    """应期 in the forms the book gives; the unit (年/月/日) depends on the matter and is left to the reader."""
    places: dict[str, list[str]] = {}
    for where, trigram in (('用卦', use), ('互卦上', nuclear[0]), ('互卦下', nuclear[1]), ('变卦', changed)):
        places.setdefault(trigram, []).append(where)
    favourable: list[dict] = []
    unfavourable: list[dict] = []
    for trigram, wheres in places.items():
        relation = _relation(body, trigram)
        if relation is None:
            continue
        element = BAGUA[trigram]['wuxing']
        row = {'trigram': trigram, 'where': '、'.join(wheres), 'relation': relation, 'element': element,
               'branches': ELEMENT_BRANCHES[element]}
        (unfavourable if relation == '克体' else favourable).append(row)
    out: dict = {
        'unit_by_matter': '远者以全卦之数为年期，近者为月期，又近为日期；按所问事项选，工具不替用户定',
        'element_days': {'body': body, 'body_element': BAGUA[body]['wuxing'], 'favourable': favourable,
                         'unfavourable': unfavourable,
                         'note': '只列卦中生体、比和（吉期）与克体（不吉之期）的卦；体生、体克的卦原文这段未说'},
    }
    sources: tuple[tuple[str, str, str], ...] = TIMING_SOURCES
    if meta['method'] == 'object':
        base = meta['houtian_total']
        out['posture'] = {'base': base,
                          'how': f"物卦{meta['upper_num']}＋方卦{meta['lower_num']}＋时数{meta['hour_number']}",
                          '行': base / 2, '立': base, '坐': base * 2,
                          'not_given': '原文提到行卧坐立，例中只给行、坐、立三种；卧未给数'}
        sources = TIMING_SOURCES + HOUTIAN_SOURCES
    else:
        upper, lower = meta['upper_tri'], meta['lower_tri']
        out['whole_number'] = {'value': TRIGRAM_NUMBER[upper] + TRIGRAM_NUMBER[lower],
                               'how': f"上卦{upper}{TRIGRAM_NUMBER[upper]}＋下卦{lower}{TRIGRAM_NUMBER[lower]}"}
    out['sources'] = [{'passage_id': pid, 'quote': quote, 'use': use_} for pid, quote, use_ in sources]
    return out


# --------------------------------------------------------------------------- #
# Pack output
# --------------------------------------------------------------------------- #

def hex_info(lines: list[int], assets: dict[int, dict]) -> dict:
    upper_bin, lower_bin = lines_to_trigrams(lines)
    num, name = hex_lookup_by_trigrams(upper_bin, lower_bin)
    a = assets.get(num, {})
    return {
        "number": num, "name": name,
        "upper_trigram": BINARY_TO_TRIGRAM.get(upper_bin),
        "lower_trigram": BINARY_TO_TRIGRAM.get(lower_bin),
        "lines": [{"position": i + 1, "value": v, "visual": line_visual(v)}
                  for i, v in enumerate(lines)],
        "judgment": a.get("judgment", "(暂无)"),
    }


def package(cast_meta: dict, question: str | None, month: int | None) -> dict:
    upper_tri = cast_meta["upper_tri"]
    lower_tri = cast_meta["lower_tri"]
    change = cast_meta["change_num"]
    lines = build_lines(upper_tri, lower_tri, change)

    ti_t, yong_t = ti_yong(upper_tri, lower_tri, change)
    relation = ti_yong_relation(ti_t, yong_t)
    state = ti_state(ti_t, month) if month is not None else None

    assets = load_hex_assets()
    main_h = hex_info(lines, assets)
    changed_h = hex_info(changed_lines(lines), assets)
    nuclear_h = hex_info(nuclear_lines(lines), assets)
    # 变卦里动爻所在的那一卦（用的位置）；体卦不动。
    changed_tri = changed_h['upper_trigram'] if change >= 4 else changed_h['lower_trigram']

    summary_parts = [
        f"主卦【{main_h['name']}】",
        f"动爻第{change}爻",
        f"变卦【{changed_h['name']}】",
        f"互卦【{nuclear_h['name']}】",
        f"体卦{ti_t}({BAGUA[ti_t]['wuxing']}), 用卦{yong_t}({BAGUA[yong_t]['wuxing']})",
        f"体用: {relation}",
    ]
    if state is not None:
        summary_parts.append(f"体卦当季(旧公历月诊断): {state}")

    return {
        **cast_meta,
        "question": question,
        "raw_lines": lines,
        "changing_line": change,
        "main_hex": main_h,
        "changed_hex": changed_h,
        "nuclear_hex": nuclear_h,
        "ti_yong": {
            "body_trigram": ti_t,
            "use_trigram": yong_t,
            "body_wuxing": BAGUA[ti_t]["wuxing"],
            "use_wuxing": BAGUA[yong_t]["wuxing"],
            "relation": relation,
            "body_strength": state,
            # 旺衰按 公历月 粗略取值。土王四季严格说是每季末 18 天, 定 18 天分界
            # 需要节气, 本引擎不提供 —— 落在月初/月末的盘可能实际处在相邻状态。
            "body_strength_granularity": ("旧公历月诊断：月令粗略 (未按节气细分, 四季月整月作土)"
                                          if month is not None else
                                          "未输出：所核取数条款不等于旺衰条件已核验"),
        },
        "summary": "; ".join(summary_parts),
        "timing": timing(cast_meta, body=ti_t, use=yong_t,
                         nuclear=(nuclear_h['upper_trigram'], nuclear_h['lower_trigram']), changed=changed_tri),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  method now_iso ymd shichen upper_num lower_num change_num upper_tri
  lower_tri question raw_lines changing_line main_hex changed_hex
  nuclear_hex ti_yong summary timing

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="梅花易数起卦 (时间/数字/字数)",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Shared target/replay context; legacy-gregorian also uses its civil month.
    p.add_argument("--datetime", dest="dt", type=str, default=None,
                   help="ISO 时间 (如 2026-06-24T13:05), 默认当下; 用于可复现起卦")
    add_request_arguments(p)
    add_calendar_arguments(p)
    sub = p.add_subparsers(dest="method", required=True)

    pt = sub.add_parser("time", help="年月日时起卦")
    pt.add_argument("--question", type=str, default=None)

    pn = sub.add_parser("numbers", help="两数起卦")
    pn.add_argument("--upper", type=int, required=True)
    pn.add_argument("--lower", type=int, required=True)
    pn.add_argument("--question", type=str, default=None)

    px = sub.add_parser("name", help="字数起卦")
    px.add_argument("--text", type=str, required=True)
    px.add_argument("--question", type=str, default=None)

    pc = sub.add_parser("count", help="物数占：可数之物的数目为上卦，时数为下卦")
    pc.add_argument("--count", type=int, required=True)
    pc.add_argument("--question", type=str, default=None)

    ps = sub.add_parser("sound", help="声音占：听到几声为上卦，声数加时数为下卦")
    ps.add_argument("--count", type=int, required=True)
    ps.add_argument("--question", type=str, default=None)

    pl = sub.add_parser("length", help="丈尺占（丈、尺，不加时）或尺寸占（尺、寸，加时）")
    pl.add_argument("--zhang", type=int, default=None)
    pl.add_argument("--chi", type=int, default=None)
    pl.add_argument("--cun", type=int, default=None)
    pl.add_argument("--question", type=str, default=None)

    po = sub.add_parser("object", help="后天端法：物卦为上卦，物来的方位为下卦")
    po.add_argument("--trigram", type=str, required=True, help="物所属的卦（按八卦萬物屬類归类）")
    po.add_argument("--direction", type=str, required=True, help="物来的方位：北、东北、东、东南、南、西南、西、西北")
    po.add_argument("--question", type=str, default=None)

    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        now, time_context = resolve_time(args, datetime_value=args.dt)
    except ValueError as e:
        json_print(error_envelope('meihua', "bad_datetime", str(e)))
        return 1

    if args.method == "time":
        try:
            meta = cast_by_time(now, args.calendar_profile, args.leap_month_policy)
        except ValueError as exc:
            json_print(error_envelope('meihua', 'invalid_calendar_profile', str(exc)))
            return 1
    elif args.method == "numbers":
        meta = cast_by_numbers(args.upper, args.lower)
    elif args.method == "name":
        meta = cast_by_text(args.text)
    elif args.method in ("count", "sound", "length", "object"):
        try:
            if args.method == "count":
                meta = cast_by_count(args.count, now)
            elif args.method == "sound":
                meta = cast_by_sound(args.count, now)
            elif args.method == "length":
                meta = cast_by_length(now, zhang=args.zhang, chi=args.chi, cun=args.cun)
            else:
                meta = cast_by_object(args.trigram, args.direction, now)
        except ValueError as exc:
            json_print(error_envelope('meihua', 'invalid_input', str(exc)))
            return 1
    else:
        json_print(error_envelope('meihua', "unknown_method", '输入无效'))
        return 2

    out = package(meta, args.question, now.month if args.calendar_profile == 'legacy-gregorian' else None)
    out["time_context"] = time_context
    json_print(ok_envelope("meihua", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
