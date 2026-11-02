"""奇门时家：默认《元灵经》已核地盘与值符值使，未核单元留空。

--plate-method dunjia-zhuanpan 按《遁甲演义》转盘排全盘并判卷二格局（qimen_zhuanpan、
qimen_patterns），每条格局与书中「假如」例对照过。旧全盘由 --plate-method rotating-compat
显式调用供比较，不判格局，不声称与元灵经同法。来源范围、异文及现代历法约定见 docs/QIMEN-LIUREN-METHODS.md。

CLI:
    python qimen_cast.py --date 2026-05-16 --time 14:30 [--longitude 120]
    python qimen_cast.py --ju-type yang --ju-number 7  # 手动定局

All algorithms are public-domain — expression here is original.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from qimen_dingju import (
    SOURCE_URL,
    determine_ju,
    futou,
    seasonal_context,
    zhi_shi_position,
)
from qimen_patterns import NOT_COMPUTED, detect
from qimen_tables import (  # noqa: F401  (re-exported for callers/tests)
    EIGHT_SHEN_ORDER,
    LIU_YI,
    MEN_HOME_PALACE,
    MEN_ORDER_BY_PALACE,
    PALACE_INFO,
    SAN_QI,
    STAR_HOME_PALACE,
    STAR_ORDER_BY_PALACE,
    XUN_HEADS,
    YANG_JIE_QI,
    YANG_PALACE_SEQ,
    YIN_JIE_QI,
    YIN_PALACE_SEQ,
    YIQI_ORDER,
)
from qimen_zhuanpan import palace_rows, plate
from request_time import add_request_arguments, resolve_time
from utils import (
    __version__,
    ensure_utf8_stdio,
    error_envelope,
    jiazi_index,
    json_print,
    longitude_correction,
    require_lunar,
)


def determine_ju_legacy(jieqi_name: str, days_since_jieqi: int) -> tuple[str, str, int]:
    """旧版日数法，仅 --ju-method legacy-days 显式选择。

    交节日期起每五个民用日分元；保留旧结果比较，不称古籍拆补或置闰法。
    """
    if days_since_jieqi < 5:
        yuan_idx, yuan_name = 0, "上元"
    elif days_since_jieqi < 10:
        yuan_idx, yuan_name = 1, "中元"
    else:
        yuan_idx, yuan_name = 2, "下元"

    if jieqi_name in YANG_JIE_QI:
        return "阳遁", yuan_name, YANG_JIE_QI[jieqi_name][yuan_idx]
    if jieqi_name in YIN_JIE_QI:
        return "阴遁", yuan_name, YIN_JIE_QI[jieqi_name][yuan_idx]
    raise ValueError(f"unknown 节气: {jieqi_name}")


# --------------------------------------------------------------------------- #
# 地盘 三奇六仪 placement
# --------------------------------------------------------------------------- #

def earth_plate(ju_type: str, ju_number: int) -> dict[int, str]:
    """Place 三奇六仪 across 9 palaces.

    阳遁 N 局: 戊起 N 宫, 顺布 (按 1..9 palace path) 六仪+三奇.
    阴遁 N 局: 戊起 N 宫, 逆布 (按 9..1 palace path) 六仪+三奇.

    Returns dict mapping palace_index (1..9) -> 干名.
    """
    if not (1 <= ju_number <= 9):
        raise ValueError(f"ju_number out of range: {ju_number}")

    # Build path of 9 palaces starting at ju_number, traversing in 顺/逆 direction.
    if ju_type == "阳遁":
        full_seq = YANG_PALACE_SEQ
    elif ju_type == "阴遁":
        full_seq = YIN_PALACE_SEQ
    else:
        raise ValueError(f"unknown ju_type: {ju_type}")

    start_idx = full_seq.index(ju_number)
    path = [full_seq[(start_idx + k) % 9] for k in range(9)]

    return {palace: YIQI_ORDER[k] for k, palace in enumerate(path)}


def dunjia_futou(instant: datetime, effective_clock: datetime | None = None) -> dict:
    """Automatic Dunjia plate at an actual instant, with a separate local day/hour clock."""
    require_lunar()
    from lunar_python import Lunar, Solar
    clock = effective_clock if effective_clock is not None else instant
    lunar = Solar.fromYmdHms(clock.year, clock.month, clock.day,
                            clock.hour, clock.minute, clock.second).getLunar()
    ganzhi = {'year': lunar.getYearInGanZhi(), 'month': lunar.getMonthInGanZhi(),
              'day': lunar.getDayInGanZhi(), 'hour': lunar.getTimeInGanZhi(),
              'month_shuo': Lunar.fromYmd(lunar.getYear(), lunar.getMonth(), 1).getDayInGanZhi()}
    term = seasonal_context(instant)
    ju_type, yuan, number = determine_ju(term['name'], ganzhi['day'])
    pl = plate(earth_plate(ju_type, number), ju_type, ganzhi['hour'])
    return {'ganzhi': ganzhi, 'solar_term': term, 'ju_type': ju_type,
            'san_yuan': yuan, 'ju_number': number, 'plate': pl,
            'patterns': detect(pl, ganzhi)}


# --------------------------------------------------------------------------- #
# 旬首 — given 日干支 (or 时干支), return which of the 6 甲 it belongs to,
# and the 六仪 (戊/己/庚/辛/壬/癸) for that 旬.
# --------------------------------------------------------------------------- #

def xun_head(stem: str, branch: str) -> tuple[str, str]:
    """Return (旬首名 e.g. '甲子', 对应六仪 e.g. '戊') for 干支."""
    idx = jiazi_index(stem, branch)
    head_idx = idx - (idx % 10)  # 0,10,20,30,40,50
    return XUN_HEADS[head_idx // 10]


def source_core(ju_type: str, ju_number: int, hour_ganzhi: str) -> dict:
    """Only the hourly anchors supported by Yuanling vol. 1; no guessed full plate.

    The vol. 8 examples do not validate extending the two opening examples
    into a complete star/door algorithm. Centre borrowing remains conditional.
    """
    earth = earth_plate(ju_type, ju_number)
    if len(hour_ganzhi) != 2:
        raise ValueError('时干支须为两个字')
    head, yi = xun_head(*hour_ganzhi)
    origin = next(p for p, stem in earth.items() if stem == yi)
    effective = yi if hour_ganzhi[0] == '甲' else hour_ganzhi[0]
    target = next(p for p, stem in earth.items() if stem == effective)
    star = next(name for name, palace in STAR_HOME_PALACE.items() if palace == origin)
    raw, _ = zhi_shi_position(origin, hour_ganzhi, ju_type)
    door_origin = 2 if origin == 5 and ju_type == '阳遁' else origin
    door = next((name for name, palace in MEN_HOME_PALACE.items() if palace == door_origin), None)
    unresolved = []
    if door is None:
        unresolved.append('阴遁旬首在中五时借门的转录异文尚未核清')
    if raw == 5:
        unresolved.append('值使数到中五，原落宫保留；寄宫去向尚未核清')
    return {'method': 'yuanling-core', 'completion_status': 'partial',
            'source_url': SOURCE_URL,
            'source_passage_ids': ['yuanling:c001:p0001', 'yuanling:c001:p0006',
                                   'yuanling:c001:p0008', 'yuanling:c001:p0009'],
            'verification': 'transcription_checked_not_facsimile',
            'earth': earth, 'xun_head': head, 'xun_yi': yi,
            'zhi_fu': {'origin_palace': origin, 'palace': target, 'star': star,
                       'heaven_stem': yi},
            'zhi_shi': {'raw_palace': raw, 'palace': None if raw == 5 else raw,
                        'door': door, 'unresolved': unresolved},
            'remaining': ['九星与奇仪全盘的跨卷例式差异', '八门全盘与中宫寄法',
                          '吉星、奇墓、门克及刑迫的完整适用条件']}


# --------------------------------------------------------------------------- #
# Heaven plate — rotate earth plate by 值符
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# 八宫环 (8-palace ring excluding 中5) — used for rotating 八门 / 九星.
# Order: 1→8→3→4→9→2→7→6 (八宫环；不是一至九宫飞布顺序).
# 阳遁 顺布 / 阴遁 逆布 — both use the same ring but traverse in
# opposite direction.
# --------------------------------------------------------------------------- #

EIGHT_RING_YANG: list[int] = [1, 8, 3, 4, 9, 2, 7, 6]
EIGHT_RING_YIN: list[int] = [1, 6, 7, 2, 9, 4, 3, 8]


def _resolve_ring_palace(palace: int) -> int:
    """If palace == 5, fall back to 2 (寄坤). Otherwise return as-is."""
    return 2 if palace == 5 else palace


# --------------------------------------------------------------------------- #
# 九星 rotation — follows 值符
# --------------------------------------------------------------------------- #

def star_plate(zhi_fu_palace: int, shi_gan_palace: int, ju_type: str) -> dict[int, str]:
    """Legacy eight-ring stars with 天禽 stored at 5; not Yuanling's method."""
    ring = EIGHT_RING_YANG if ju_type == "阳遁" else EIGHT_RING_YIN

    # Compatibility map. Actual co-location of 天禽 is not implemented here.
    home_ring: dict[int, str] = {
        1: "天蓬", 8: "天任", 3: "天冲", 4: "天辅",
        9: "天英", 2: "天芮", 7: "天柱", 6: "天心",
    }

    from_pal = _resolve_ring_palace(zhi_fu_palace)
    to_pal = _resolve_ring_palace(shi_gan_palace)
    from_idx = ring.index(from_pal)
    to_idx = ring.index(to_pal)
    shift = (to_idx - from_idx) % 8

    star_result: dict[int, str] = {}
    for k, palace in enumerate(ring):
        target = ring[(k + shift) % 8]
        star_result[target] = home_ring[palace]

    # Legacy storage: this is NOT an implemented co-location with 天芮.
    star_result[5] = "天禽"
    return star_result


# --------------------------------------------------------------------------- #
# 八门 rotation — follows 值使 (= 旬首六仪 所对应 之地盘宫位的本门).
# --------------------------------------------------------------------------- #

def men_plate(zhi_fu_palace: int, shi_gan_palace: int, ju_type: str) -> dict[int, str]:
    """Rotate 八门. 值使门 = zhi_fu_palace's 本门; 该门飞到 时干宫.

    八门 home positions: 1坎-休门 2坤-死门 3震-伤门 4巽-杜门
                         5中-无门 6乾-开门 7兑-惊门 8艮-生门 9离-景门
    """
    ring = EIGHT_RING_YANG if ju_type == "阳遁" else EIGHT_RING_YIN
    home_ring: dict[int, str] = {
        1: "休门", 8: "生门", 3: "伤门", 4: "杜门",
        9: "景门", 2: "死门", 7: "惊门", 6: "开门",
    }

    from_pal = _resolve_ring_palace(zhi_fu_palace)
    to_pal = _resolve_ring_palace(shi_gan_palace)
    from_idx = ring.index(from_pal)
    to_idx = ring.index(to_pal)
    shift = (to_idx - from_idx) % 8

    men_result: dict[int, str] = {}
    for k, palace in enumerate(ring):
        target = ring[(k + shift) % 8]
        men_result[target] = home_ring[palace]
    # 中5 stays without 八门.
    return men_result


# --------------------------------------------------------------------------- #
# 八神 — starts at 值符宫 (which gets 值符), then 阳顺/阴逆 along palace path.
# --------------------------------------------------------------------------- #

def shen_plate(shi_gan_palace: int, ju_type: str) -> dict[int, str]:
    """八神: 值符 起于 时干宫 (即 值符 当前所在宫位),
    阳顺/阴逆 沿 8-palace ring 排布. 中宫 5 无神.
    """
    ring = EIGHT_RING_YANG if ju_type == "阳遁" else EIGHT_RING_YIN
    start = _resolve_ring_palace(shi_gan_palace)
    start_idx = ring.index(start)

    shen_result: dict[int, str] = {}
    for k, name in enumerate(EIGHT_SHEN_ORDER):
        palace = ring[(start_idx + k) % 8]
        shen_result[palace] = name
    return shen_result


# --------------------------------------------------------------------------- #
# Build palace records
# --------------------------------------------------------------------------- #

def build_palaces(
    earth: dict[int, str],
    heaven: dict[int, str],
    men: dict[int, str],
    star: dict[int, str],
    shen: dict[int, str],
) -> list[dict]:
    out: list[dict] = []
    for p in range(1, 10):
        info = PALACE_INFO[p]
        notes: list[str] = []
        if p == 5:
            notes.append("中宫；寄宫须按所选方法另核，不能固定称天芮天禽同宫")
        out.append({
            "index": p,
            "palace": info["palace"],
            "direction": info["direction"],
            "wuxing": info["wuxing"],
            "earth_yi_qi": earth.get(p),
            "heaven_yi_qi": heaven.get(p),
            "men": men.get(p),
            "star": star.get(p),
            "shen": shen.get(p),
            "notes": "; ".join(notes) if notes else "",
        })
    return out


# --------------------------------------------------------------------------- #
# Helper: figure out 节气 + 三元 from lunar_python
# --------------------------------------------------------------------------- #

def jieqi_context(solar_year: int, solar_month: int, solar_day: int) -> tuple[str, int]:
    """Return (current_jieqi_name, days_since_that_jieqi).

    Uses 前节气 (prev) — i.e. the most recent jieqi at-or-before given date.
    """
    require_lunar()
    from lunar_python import Solar  # type: ignore

    s = Solar.fromYmdHms(solar_year, solar_month, solar_day, 12, 0, 0)
    lunar = s.getLunar()

    prev = lunar.getPrevJieQi()
    today_jq = lunar.getJieQi()
    if today_jq:
        # 节气当日
        return today_jq, 0

    prev_name = prev.getName()
    prev_solar = prev.getSolar()
    py, pm, pd = prev_solar.getYear(), prev_solar.getMonth(), prev_solar.getDay()
    from datetime import date
    delta = (date(solar_year, solar_month, solar_day)
             - date(py, pm, pd)).days
    return prev_name, delta


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version input ganzhi jieqi san_yuan ju_type ju_number shi_gan
  shi_zhi xun_head xun_yi zhi_fu_star zhi_fu_palace zhi_fu_origin_palace
  zhi_shi_men zhi_shi_palace palaces patterns patterns_not_computed method_profile summary

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="奇门时家 — 元灵经已核地盘及值符值使；旧全盘可显式对照",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_request_arguments(p)
    p.add_argument("--date", type=str, default=None,
                   help="公历日期 YYYY-MM-DD (默认今日)")
    p.add_argument("--time", type=str, default=None,
                   help="时间 HH:MM (默认当前)")
    p.add_argument("--longitude", type=float, default=None,
                   help="经度 (用于真太阳时修正, 可选)")
    p.add_argument("--ju-type", type=str, choices=["yang", "yin"], default=None,
                   help="手动指定 阳遁/阴遁 (覆盖自动算法)")
    p.add_argument("--ju-number", type=int, default=None,
                   help="手动指定 局数 1..9 (与 --ju-type 配合)")
    p.add_argument("--ju-method", choices=["futou", "legacy-days"], default="futou",
                   help="定局口径: 默认符头三元+实交节; legacy-days仅复现旧节气日数法")
    p.add_argument('--plate-method', choices=['yuanling-core', 'dunjia-zhuanpan', 'rotating-compat'],
                   default='yuanling-core',
                   help='默认输出元灵经已核地盘及值符值使；dunjia-zhuanpan 按遁甲演义转盘排全盘并判格局；'
                        '旧全盘仅用 rotating-compat 显式对照')
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)

    try:
        dt, time_context = resolve_time(args, date_value=args.date, time_value=args.time)
    except ValueError as exc:
        json_print(error_envelope('qimen', 'invalid_time_context', str(exc)))
        return 1
    y, m, d, hh, mm = dt.year, dt.month, dt.day, dt.hour, dt.minute

    # Longitude correction (apply day roll-over near midnight)
    if args.longitude is not None:
        import math
        if not math.isfinite(args.longitude) or not -180 <= args.longitude <= 180:
            json_print(error_envelope('qimen', 'invalid_longitude', '经度须在 -180..180'))
            return 1
        if time_context['offset_hours'] is None:
            json_print(error_envelope('qimen', 'missing_timezone', '经度修正需要目标时区，不能默认 UTC+8'))
            return 1
        _doff, hh, mm = longitude_correction(hh, mm, args.longitude,
                                             tz_offset_hours=time_context["offset_hours"],
                                             year=y, month=m, day=d)
        if _doff != 0:
            from datetime import date as _date
            from datetime import timedelta as _td
            _nd = _date(y, m, d) + _td(days=_doff)
            y, m, d = _nd.year, _nd.month, _nd.day

    time_context['time_standard'] = 'true-solar' if args.longitude is not None else 'clock'
    time_context['effective_local'] = f'{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}'

    # Compute ganzhi via lunar_python
    require_lunar()
    from lunar_python import Solar  # type: ignore
    solar = Solar.fromYmdHms(y, m, d, hh, mm, 0)
    lunar = solar.getLunar()
    year_gz = lunar.getYearInGanZhi()
    month_gz = lunar.getMonthInGanZhi()
    day_gz = lunar.getDayInGanZhi()
    hour_gz = lunar.getTimeInGanZhi()
    hour_stem = lunar.getTimeGan()
    hour_branch = lunar.getTimeZhi()

    # 1. 定局：真太阳时修正只改当地日时，不移动实际交节瞬间。
    if (args.ju_type is None) != (args.ju_number is None):
        json_print(error_envelope('qimen', 'incomplete_manual_ju',
                                  '--ju-type 与 --ju-number 必须一起提供'))
        return 1
    if args.ju_number is not None and not 1 <= args.ju_number <= 9:
        json_print(error_envelope('qimen', 'invalid_ju_number', '局数须为 1..9'))
        return 1
    term_context = None
    day_futou = None
    automatic_dunjia = None
    if args.ju_type and args.ju_number:
        ju_type = "阳遁" if args.ju_type == "yang" else "阴遁"
        ju_number = args.ju_number
        san_yuan = "手动"
        jq_name = "(手动)"
    else:
        try:
            if args.ju_method == "legacy-days":
                jq_name, days_since = jieqi_context(y, m, d)
                ju_type, san_yuan, ju_number = determine_ju_legacy(jq_name, days_since)
            else:
                if args.plate_method == 'dunjia-zhuanpan':
                    automatic_dunjia = dunjia_futou(dt, datetime(y, m, d, hh, mm, dt.second))
                    term_context = automatic_dunjia['solar_term']
                    ju_type = automatic_dunjia['ju_type']
                    san_yuan = automatic_dunjia['san_yuan']
                    ju_number = automatic_dunjia['ju_number']
                else:
                    term_context = seasonal_context(dt)
                    ju_type, san_yuan, ju_number = determine_ju(term_context['name'], day_gz)
                jq_name = term_context['name']
                day_futou, _ = futou(day_gz)
        except (ValueError, KeyError) as e:
            json_print(error_envelope('qimen', "ju_determination_failed", str(e)))
            return 1

    # 2. 地盘
    earth = earth_plate(ju_type, ju_number)

    # 3. 旬首 + 值符宫 + 时干宫 + 天盘
    head_name, head_yi = xun_head(hour_stem, hour_branch)

    # 时干 可能 是 甲: 甲 隐在 旬首六仪 之下. 处理 时干=甲 的情形.
    effective_shi_gan = hour_stem
    if hour_stem == "甲":
        effective_shi_gan = head_yi  # 甲 遁于 六仪
    zhi_fu_palace = next(p for p, yq in earth.items() if yq == head_yi)
    shi_gan_palace = next(p for p, yq in earth.items() if yq == effective_shi_gan)

    core = source_core(ju_type, ju_number, hour_gz)
    zhi_shi_raw = core['zhi_shi']['raw_palace']
    zhi_fu_landed = shi_gan_palace
    not_computed: list[dict] = []
    if args.plate_method == 'dunjia-zhuanpan':
        pl = automatic_dunjia['plate'] if automatic_dunjia else plate(earth, ju_type, hour_gz)
        zhi_fu_star = pl['zhi_fu']['star']
        zhi_fu_landed = pl['zhi_fu']['palace']
        zhi_shi_men = pl['zhi_shi']['door']
        zhi_shi_palace = pl['zhi_shi']['palace']
        palaces = palace_rows(pl)
        from lunar_python import Lunar  # type: ignore
        shuo = Lunar.fromYmd(lunar.getYear(), lunar.getMonth(), 1).getDayInGanZhi()
        patterns = (automatic_dunjia['patterns'] if automatic_dunjia else
                    detect(pl, {'year': year_gz, 'month': month_gz, 'month_shuo': shuo,
                                'day': day_gz, 'hour': hour_gz}))
        not_computed = NOT_COMPUTED
    elif args.plate_method == 'yuanling-core':
        # Never fill unsupported cells with another method's arrangement.
        zhi_fu_star = core['zhi_fu']['star']
        zhi_shi_men = core['zhi_shi']['door']
        zhi_shi_palace = core['zhi_shi']['palace']
        heaven = {shi_gan_palace: head_yi}
        star = {shi_gan_palace: zhi_fu_star}
        men = ({zhi_shi_palace: zhi_shi_men}
               if zhi_shi_palace is not None and zhi_shi_men is not None else {})
        palaces = build_palaces(earth, heaven, men, star, {})
        patterns = []
    else:
        # Explicit legacy comparison only; never used by personal selection.
        full_seq = YANG_PALACE_SEQ if ju_type == "阳遁" else YIN_PALACE_SEQ
        shift = (full_seq.index(shi_gan_palace) - full_seq.index(zhi_fu_palace)) % 9
        heaven = {full_seq[(k + shift) % 9]: earth[p] for k, p in enumerate(full_seq)}
        star = star_plate(zhi_fu_palace, shi_gan_palace, ju_type)
        zhi_fu_star = star[_resolve_ring_palace(shi_gan_palace)]
        _, zhi_shi_palace = zhi_shi_position(zhi_fu_palace, hour_gz, ju_type)
        men = men_plate(zhi_fu_palace, zhi_shi_palace, ju_type)
        zhi_shi_men = men[_resolve_ring_palace(zhi_shi_palace)]
        shen = shen_plate(shi_gan_palace, ju_type)
        palaces = build_palaces(earth, heaven, men, star, shen)
        # 旧盘天盘按九宫飞布、星门按八宫转，与遁甲演义书例不合，不在其上判格局。
        patterns = []

    # 10. Summary
    summary_parts = [
        f"{ju_type}{ju_number}局({san_yuan})",
        f"节气: {jq_name}",
        f"时干 {hour_stem} 落于 {shi_gan_palace}宫({PALACE_INFO[shi_gan_palace]['palace']})",
        f"值符 {zhi_fu_star} 居 {zhi_fu_landed}宫",
        f"值使 {zhi_shi_men or '借门待核'}，原数至{zhi_shi_raw}宫",
    ]
    named = list(dict.fromkeys(pp["name"] for pp in patterns if pp["category"] != "门迫" and not pp["variant"]))
    if named:
        summary_parts.append(f"格局: {', '.join(named)}")

    out = {
        "ok": True,
        "tool": "qimen",
        "version": __version__,
        "time_context": time_context,
        "completion_status": "complete" if args.plate_method == 'dunjia-zhuanpan' else "partial",
        "source_core": core,
        "method_profile": {
            "plate_method": args.plate_method,
            "ding_ju": "manual" if args.ju_type else args.ju_method,
            "source": SOURCE_URL,
            "verification": "transcription_checked_not_facsimile",
            "futou": day_futou,
            "solar_term": term_context,
            "day_boundary": "当地有效钟面00:00换日；23:00小时干支按历库晚子时规则",
            "intercalation": "none",
            "scope": {"yuanling-core": "已核地盘、旬首、值符原星及落宫、值使计数；空值为待核，不表示无星无门",
                      "dunjia-zhuanpan": ("遁甲演义转盘：八宫环整体转、中五寄坤二、八神阳顺阴逆；格局照卷二原文判，"
                                          "与元灵经不同书，source_core 单列元灵经结果"),
                      "rotating-compat": "旧转盘仅供对照，不判格局，不与元灵经原例混作同一盘；source_core单列已核结果",
                      }[args.plate_method],
            "legacy_note": "legacy-days只兼容旧定局，其他已修正组件不回退旧错误",
        },
        "input": {
            "date": f"{y:04d}-{m:02d}-{d:02d}",
            "time": f"{hh:02d}:{mm:02d}",
            "longitude": args.longitude,
        },
        "ganzhi": {
            "year": year_gz,
            "month": month_gz,
            "day": day_gz,
            "hour": hour_gz,
        },
        "jieqi": jq_name,
        "san_yuan": san_yuan,
        "ju_type": ju_type,
        "ju_number": ju_number,
        "shi_gan": hour_stem,
        "shi_zhi": hour_branch,
        "xun_head": head_name,
        "xun_yi": head_yi,
        "zhi_fu_star": zhi_fu_star,
        "zhi_fu_palace": zhi_fu_landed,
        "zhi_fu_origin_palace": zhi_fu_palace,
        "zhi_shi_men": zhi_shi_men,
        "zhi_shi_palace": zhi_shi_palace,
        "zhi_shi_raw_palace": zhi_shi_raw,
        "zhi_shi_basis": {"yuanling-core": "元灵经卷一：旬首原宫沿一至九宫阳顺阴逆数旬时；中五寄法未决时不填目的宫",
                          "dunjia-zhuanpan": "遁甲演义：九宫数旬时，数到中五寄坤二（dunjia:c002:p0024）",
                          "rotating-compat": "兼容方法：九宫数旬时，数完中五寄坤二；寄二不代表已核原典通则",
                          }[args.plate_method],
        "palaces": palaces,
        "patterns": patterns,
        "patterns_not_computed": not_computed,
        "summary": "; ".join(summary_parts),
    }
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
