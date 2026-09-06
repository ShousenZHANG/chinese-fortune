"""紫微斗数 (Zi Wei Dou Shu) — chart engine using documented project tables.

Implements a selected 排盘 pipeline. Some structural rules have located
《紫微斗数全书》transcriptions; brightness, school variants and later flying-star
concepts must retain their separate source status:

  1. 命宫 / 身宫              (寅宫起正月 + 子时定位)
  2. 五行局                  (命宫干支纳音)
  3. 紫微星                  (五行局 + 农历生日, 标准排盘表)
  4. 紫微/天府 14 主星      (北斗 6 + 南斗 8)
  5. 六吉                    (左辅/右弼/文昌/文曲/天魁/天钺)
  6. 六煞                    (擎羊/陀罗/火星/铃星/地空/地劫) + 禄存
  7. 杂曜                    (天马/红鸾/天喜/孤辰/寡宿/天哭/天虚/龙池/凤阁)
  8. 命主 / 身主             (分别按命宫支 / 生年支)
  9. 斗君                    (流年起算之锚)
 10. 四化                    (生年/大限/流年, 含自化离心向心)
 11. 12 宫                  (含借宫 — 命宫空宫自动借对宫主星)
 12. 12 大限                 (阴男阳女逆行修正)
 13. 格局                    (15 格自动识别: 紫府同宫/府相朝垣/阳梁昌禄/机月
                              同梁/杀破狼/火贪/铃贪/武贪/日月同宫/明珠出海/
                              辅弼夹命/昌曲夹命/羊陀夹忌/空劫夹命/马头带箭)

Accepts either calendar; use the calendar actually known by the user.

Usage:
    python ziwei_calc.py --year 1995 --month 7 --day 20 --hour 1 \\
        --gender female --lunar
"""

from __future__ import annotations

import argparse
import sys

from method_rules import method_reading_packet

# Section 17 — CLI / main
# --------------------------------------------------------------------------- #
from utils import (
    DIZHI,
    __version__,
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    lookup_city,
    normalize_birth_time,
    validate_birth_input,
    warn,
)
from ziwei_palaces import (
    MING_ZHU,
    SHEN_ZHU,
    SI_HUA,
    assign_palaces,
    borrow_from_opposite,
    calc_dou_jun,
    da_xian_ranges,
    detect_self_transformations,
    is_empty_palace,
    san_fang_si_zheng,
)
from ziwei_patterns import detect_patterns
from ziwei_stars import (
    BRIGHTNESS_NOTE,
    brightness_of,
    place_lucky_stars,
    place_main_stars,
    place_malefic_stars,
    place_miscellaneous_stars,
)
from ziwei_tables import (
    calc_ming_gong,
    calc_shen_gong,
    stem_of_palace,
    wuxing_ju,
    ziwei_position,
)

VERSION = __version__

SECT_LABELS = {
    1: "子初换日 (23:00 起整体视为次日: 日柱、农历日一并推进)",
    2: "子正换日 (日柱与农历日取当日, 仅时柱按次日干)",
}




EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version input sect birthplace timezone notes true_solar_time_applied solar_date lunar_date
  year_stem year_branch wuxing_ju ming_gong shen_gong ming_zhu shen_zhu
  dou_jun ziwei_position main_stars_positions lucky_stars_positions
  malefic_stars_positions miscellaneous_stars_positions twelve_palaces
  four_transformations_native da_xian liu_nian_sihua patterns notes
  dou_jun_basis zhi_shi_basis

--brief-palaces 时 twelve_palaces 只留 name/branch/stem/index/main_stars;
--no-da-xian 时 da_xian 为 null。两者不改变其余字段的值。

On error: {"ok": false, "tool": ..., "version": ..., "error": ..., "message": ...}
and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "紫微斗数排盘 v" + VERSION + " — 14主星 + 六吉六煞 + 杂曜 + "
            "命主身主 + 自化 + 大限/流年四化 + 借宫 + 格局识别"
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--hour", type=int, required=True)
    p.add_argument("--minute", type=int, default=0)
    p.add_argument("--gender", choices=["male", "female"], required=True)
    p.add_argument("--tz", type=float, default=8.0)
    p.add_argument("--fold", type=int, choices=(0, 1), default=None,
                   help="重复当地时间: 0=第一次, 1=第二次; 无歧义时不需要")
    p.add_argument("--time-standard", choices=("true-solar", "clock"),
                   default="true-solar", help="时间口径, 默认真太阳时; clock 为显式钟表时")
    p.add_argument("--longitude", type=float, default=None,
                   help="出生地经度 (E°, 默认 120, 用于真太阳时)")
    p.add_argument("--lunar", action="store_true",
                   help="若指定, 视输入为农历; 否则按公历换算")
    p.add_argument("--city", type=str, default=None,
                   help="出生地 (省市名/别名/拼音), 由 assets/cities_cn.json 解析为经度与"
                        "时区; 显式 --longitude / --timezone 优先")
    p.add_argument("--sect", type=int, choices=(1, 2), default=2,
                   help="晚子时取日流派: 2=子正换日 (默认) 1=子初换日 (23:00 起按次日"
                        "排盘). 与八字共用同一开关")
    p.add_argument("--timezone", type=str, default=None,
                   help="IANA 时区名 (如 Asia/Shanghai). 给出则按出生当刻的真实"
                        "偏移取时辰, 自动处理历史时区与夏令时")
    p.add_argument("--leap", action="store_true",
                   help="农历输入且该月为闰月 (等同传入负月份)")
    p.add_argument("--liu-year", type=int, default=None,
                   help="额外加算指定流年的四化 (公历)")
    p.add_argument("--no-patterns", action="store_true",
                   help="略过 格局 检测以缩减输出")
    p.add_argument("--no-sihua", action="store_true",
                   help="略过各宫自化（保留生年及岁限四化）")
    # twelve_palaces 与 da_xian 合占载荷 81.5%, 而此前两个开关只覆盖 1.3%+2.2%
    # 的小块 —— 开关造在了不占体积的地方, 实测裁剪只省 0.3%。
    p.add_argument("--no-da-xian", action="store_true",
                   help="略过 大限 (占载荷约 28%%; 只看本命盘时可关)")
    p.add_argument("--brief-palaces", action="store_true",
                   help="十二宫只留 宫名/地支/宫干/主星名 (占载荷约 53%%; "
                        "只需宫位骨架时用)")
    return p


def brief_palaces(palaces: list[dict]) -> list[dict]:
    """十二宫的精简形态 —— 只留骨架, 去掉星曜明细与逐宫注解。"""
    keep = ("name", "branch", "stem", "index")
    out = []
    for p_ in palaces:
        row = {k: p_[k] for k in keep if k in p_}
        row["main_stars"] = [s["name"] if isinstance(s, dict) else s
                             for s in p_.get("main_stars", [])]
        out.append(row)
    return out


def calculate_ziwei(request: argparse.Namespace) -> dict:
    """Compute a chart without stdout; accepts arguments from build_parser()."""
    args = argparse.Namespace(**vars(request))

    # 边界校验必须在碰 lunar_python 之前。Solar.fromYmdHms 不校验日期真实性 ——
    # 1990-02-31 会被接受并归一化成一张完整命盘随 ok:true 返回, 调用方无从分辨。
    err = validate_birth_input(
        args.year, args.month, args.day, args.hour, args.minute, lunar=args.lunar,
    )
    if err:
        return error_envelope("ziwei", "invalid_input", err, input=vars(args))

    try:
        from lunar_python import Lunar, Solar  # type: ignore
    except ImportError:
        return error_envelope("ziwei", "missing_dependency", "pip install -r scripts/requirements.txt")

    try:
        if args.lunar:
            # lunar_python encodes 闰月 as a negative month.
            month = -abs(args.month) if args.leap else args.month
            lunar = Lunar.fromYmdHms(
                args.year, month, args.day,
                args.hour, args.minute, 0,
            )
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(
                args.year, args.month, args.day,
                args.hour, args.minute, 0,
            )
            lunar = solar.getLunar()
    except Exception as exc:
        return error_envelope("ziwei", "invalid_date", str(exc), input=vars(args))

    # Resolve place before the shared time normalization.
    birthplace = None
    if args.city:
        row = lookup_city(args.city)
        if row is None:
            return error_envelope('ziwei', "unknown_city", f"未收录出生地: {args.city}; 请改传 --longitude 与 --timezone")
        lon_explicit = args.longitude is not None
        if not lon_explicit:
            args.longitude = row["lon"]
        if not args.timezone:
            args.timezone = row["tz"]
        birthplace = {"name": row["name"], "province": row["province"],
                      "lon": row["lon"], "lat": row["lat"], "tz": row["tz"],
                      "longitude_source": "explicit" if lon_explicit else "city_table"}

    if args.longitude is None:
        args.longitude = 120.0  # GMT+8 reference meridian

    try:
        normalized = normalize_birth_time(
            solar.getYear(), solar.getMonth(), solar.getDay(), args.hour,
            args.minute, args.longitude, args.tz, args.timezone, args.fold,
            args.time_standard)
    except ValueError as exc:
        return error_envelope("ziwei", "invalid_time", str(exc))
    tz_info = normalized['timezone']
    tst_info = normalized['true_solar_time']
    tst_applied = tst_info['applied']
    sd = normalized['solar_date']
    solar = Solar.fromYmdHms(sd['year'], sd['month'], sd['day'], sd['hour'], sd['minute'], 0)
    lunar = solar.getLunar()
    birth_hour = sd['hour']

    # 晚子时取日 (shared convention with bazi_calc --sect). 子初换日 treats 23:00
    # onwards as the next day outright, so the entire lunar date rolls before
    # any 命宫 / 五行局 / 紫微星表 / 闰月 rule is applied — one coherent shift,
    # never a second one layered on top of the leap-month split.
    sect_note: list[str] = []
    if args.sect == 1 and birth_hour == 23:
        from datetime import date as _d
        from datetime import timedelta as _td
        nxt = _d(solar.getYear(), solar.getMonth(), solar.getDay()) + _td(days=1)
        solar = Solar.fromYmdHms(nxt.year, nxt.month, nxt.day, 0, 0, 0)
        lunar = solar.getLunar()
        birth_hour = 0
        sect_note.append("晚子时按子初换日 (--sect 1): 已整体推进至次日 00:00 排盘。")
    sect_info = {"value": args.sect, "label": SECT_LABELS[args.sect]}

    year_stem = lunar.getYearGan()
    year_branch = lunar.getYearZhi()
    # 项目闰月归属：十五日及以前算本月，十五日后算下月；与所引全书转录不同。
    # 紫微 keys 命宫/身宫/斗君/辅星 off the lunar month, so attributing a whole
    # 闰月 to its base month shifted every one of those by a palace for births
    # after the 15th. bazi is unaffected: its 月柱 is 节气-based, not lunar.
    raw_month = lunar.getMonth()
    is_leap_month = raw_month < 0
    lunar_day = lunar.getDay()
    lunar_month = abs(raw_month)
    leap_note: list[str] = []
    if is_leap_month and lunar_day > 15:
        lunar_month = (lunar_month % 12) + 1
        leap_note.append(
            f"闰月十五日后, 按项目取法算作下月 ({abs(raw_month)} -> {lunar_month} 月) "
            f"排命宫/身宫/斗君; 见 references/02-ziwei-paipan.md 闰月处理。"
        )
    elif is_leap_month:
        leap_note.append(
            f"闰月十五日及以前, 按项目取法算作本月 ({lunar_month} 月); "
            f"见 references/02-ziwei-paipan.md 闰月处理。"
        )

    # 1. 命宫 / 身宫 / 宫干.
    mg_branch = calc_ming_gong(lunar_month, birth_hour)
    sg_branch = calc_shen_gong(lunar_month, birth_hour)
    mg_stem = stem_of_palace(year_stem, mg_branch)

    # 2. 五行局.
    ju_num, ju_name = wuxing_ju(year_stem, mg_branch)

    # 3. 紫微 + 14 主星.
    zw_branch = ziwei_position(ju_num, lunar_day)
    main_pos = place_main_stars(zw_branch)

    # 4. 六吉 + 六煞 + 杂曜.
    lucky_pos = place_lucky_stars(year_stem, lunar_month, birth_hour)
    malefic_pos = place_malefic_stars(year_stem, year_branch, birth_hour)
    misc_pos = place_miscellaneous_stars(year_branch)

    # 5. 命主 / 身主 / 斗君.
    # 安命主诀 keys on the 命宫 branch (子宫贪狼丑亥巨门…); 安身主诀 on the 年支.
    # Keying both by 年支 gave the wrong 命主 on most charts — caught by the
    # iztro-py differential, which agreed with us on every other field.
    ming_zhu = MING_ZHU.get(mg_branch, "?")
    shen_zhu = SHEN_ZHU.get(year_branch, "?")
    # 本命斗君 (以生年太岁起). 流年斗君须以该年太岁代入 calc_dou_jun.
    dou_jun_branch = calc_dou_jun(year_branch, lunar_month, birth_hour)

    # 6. 反向索引 — branch -> list of stars by category.
    branch_to_main: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in main_pos.items():
        branch_to_main[b].append(star)
    branch_to_lucky: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in lucky_pos.items():
        branch_to_lucky[b].append(star)
    branch_to_malefic: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in malefic_pos.items():
        branch_to_malefic[b].append(star)
    branch_to_misc: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in misc_pos.items():
        branch_to_misc[b].append(star)
    branch_to_all: dict[str, list[str]] = {
        b: branch_to_main[b] + branch_to_lucky[b]
        + branch_to_malefic[b] + branch_to_misc[b]
        for b in DIZHI
    }

    # 7. 生年四化 lookup.
    sihua_native = SI_HUA.get(year_stem, {})

    # 8. 12 宫排盘 + 借宫 + 自化.
    palaces = assign_palaces(mg_branch)
    annotated: list[dict] = []
    for p in palaces:
        b = p["branch"]
        stem = stem_of_palace(year_stem, b)
        mains = list(branch_to_main[b])
        luckies = list(branch_to_lucky[b])
        malefics = list(branch_to_malefic[b])
        miscs = list(branch_to_misc[b])
        sfsz = san_fang_si_zheng(b)

        # Sihua markers (生年四化): which stars in this palace are 化X targets.
        sihua_marks: list[str] = []
        for hua_type, target in sihua_native.items():
            if target in mains + luckies:
                sihua_marks.append(f"化{hua_type}({target})")

        # 自化.
        if args.no_sihua:
            self_huas: list[str] = []
        else:
            self_huas = detect_self_transformations(stem, mains + luckies)

        # 借宫.
        borrowed = False
        borrowed_stars: list[str] = []
        borrowed_from: str | None = None
        if is_empty_palace(mains):
            opp_b, opp_main = borrow_from_opposite(b, branch_to_main)
            if opp_main:
                borrowed = True
                borrowed_stars = opp_main
                borrowed_from = opp_b

        annotated.append({
            "index": p["index"],
            "name": p["name"],
            "branch": b,
            "stem": stem,
            "ganzhi": f"{stem}{b}",
            "main_stars": [
                {"name": s, "brightness": brightness_of(s, b)} for s in mains
            ],
            "lucky_stars": luckies,
            "malefic_stars": malefics,
            "miscellaneous_stars": miscs,
            "sihua_native": sihua_marks,
            "self_transformations": self_huas,
            "borrowed": borrowed,
            "borrowed_stars": borrowed_stars,
            "borrowed_from_branch": borrowed_from,
            "san_fang_si_zheng": sfsz,
            "is_ming_gong": (p["index"] == 0),
            "is_shen_gong": (b == sg_branch),
        })

    # 9. 大限 + 流年四化.
    da_xian = da_xian_ranges(ju_num, args.gender, year_stem, palaces, SI_HUA)
    liu_nian_sihua = None
    if args.liu_year:
        try:
            from lunar_python import Solar as _Solar  # type: ignore
            ly_lunar = _Solar.fromYmdHms(
                args.liu_year, 6, 15, 12, 0, 0,
            ).getLunar()
            ly_stem = ly_lunar.getYearGan()
            ly_branch = ly_lunar.getYearZhi()
            liu_nian_sihua = {
                "year": args.liu_year,
                "year_stem": ly_stem,
                "year_branch": ly_branch,
                "transformations": SI_HUA.get(ly_stem, {}),
                "liu_nian_ming_gong_branch": ly_branch,
            }
        except Exception as exc:
            warn(f"liu_year compute failed: {exc}")

    # 10. 格局识别.
    patterns: list[dict] = []
    if not args.no_patterns:
        patterns = detect_patterns(
            mg_branch, branch_to_main, branch_to_all,
            palaces, sihua_native,
        )

    out = {
        "ok": True,
        "tool": "ziwei",
        "version": VERSION,
        "input": {**vars(args), "effective_lunar_month": lunar_month,
                  "is_leap_month": is_leap_month},
        "true_solar_time_applied": tst_applied,
        "true_solar_time": tst_info,
        "solar_date": {
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(), "hour": solar.getHour(),
            "minute": solar.getMinute(),
        },
        "lunar_date": {
            "year": lunar.getYear(),
            "month": lunar_month,
            "day": lunar_day,
            "year_ganzhi": lunar.getYearInGanZhi(),
            "month_chinese": lunar.getMonthInChinese(),
            "day_chinese": lunar.getDayInChinese(),
        },
        "year_stem": year_stem,
        "year_branch": year_branch,
        "wuxing_ju": {"number": ju_num, "name": ju_name},
        "ming_gong": {"branch": mg_branch, "stem": mg_stem,
                      "ganzhi": f"{mg_stem}{mg_branch}"},
        "shen_gong": {"branch": sg_branch},
        "ming_zhu": ming_zhu,
        "shen_zhu": shen_zhu,
        "dou_jun": f"{dou_jun_branch}宫",
        "dou_jun_basis": "生年太岁 (流年斗君以该年太岁代入)",
        "ziwei_position": zw_branch,
        "main_stars_positions": main_pos,
        "lucky_stars_positions": lucky_pos,
        "malefic_stars_positions": malefic_pos,
        "miscellaneous_stars_positions": misc_pos,
        "twelve_palaces": (brief_palaces(annotated) if args.brief_palaces
                           else annotated),
        "four_transformations_native": sihua_native,
        "da_xian": None if args.no_da_xian else da_xian,
        "liu_nian_sihua": liu_nian_sihua,
        "patterns": patterns,
        "sect": sect_info,
        "birthplace": birthplace,
        "timezone": tz_info,
        "notes": sect_note + leap_note
        + ([tz_info["note"]] if tz_info and tz_info["note"] else [])
        + [
            "本输出含 命宫/身宫/五行局/紫微/14主星/六吉六煞/9杂曜/12宫/借宫/自化/大限四化/格局识别。",
            BRIGHTNESS_NOTE,
            "流年/流月/流日 需配合 斗君 起算; 本盘输出 dou_jun 提供锚位。",
            "安星采用项目所选表；魁钺、部分四化和历法口径与个别《全书》转录存在差异，自化采用后起飞星概念，不能统称全书原法。",
        ],
    }
    out['schema_version'] = '2.0'
    out['reading_support'] = {
        'status': 'requires_semantic_review',
        'school': 'project-synthesis',
        'limits': [
            '星曜与宫位为排盘结果; 象征含义不是个人经历或未来事件',
            '格局标签不直接推出富贵贫贱、健康或关系结论',
            '亮度采用项目简化表, 未完成全表原刻影像校勘',
            '自化等分歧规则须标明所用口径, 不冒充全书共识',
        ],
        'method_rules': method_reading_packet('ziwei', out, brief=args.brief_palaces),
    }
    return out


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    result = calculate_ziwei(args)
    json_print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
