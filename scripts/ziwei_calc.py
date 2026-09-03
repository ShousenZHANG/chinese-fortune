"""紫微斗数 (Zi Wei Dou Shu) — production-grade chart engine.

Implements the canonical排盘 pipeline derived from《紫微斗数全书》(罗洪先, 明) and
《紫微斗数全集》(陈希夷传), independent of any third-party AGPL codebase:

  1. 命宫 / 身宫              (寅宫起正月 + 子时定位)
  2. 五行局                  (命宫干支纳音)
  3. 紫微星                  (五行局 + 农历生日, 标准排盘表)
  4. 紫微/天府 14 主星      (北斗 6 + 南斗 8)
  5. 六吉                    (左辅/右弼/文昌/文曲/天魁/天钺)
  6. 六煞                    (擎羊/陀罗/火星/铃星/地空/地劫) + 禄存
  7. 杂曜                    (天马/红鸾/天喜/孤辰/寡宿/天哭/天虚/龙池/凤阁)
  8. 命主 / 身主             (年支主星)
  9. 斗君                    (流年起算之锚)
 10. 四化                    (生年/大限/流年, 含自化离心向心)
 11. 12 宫                  (含借宫 — 命宫空宫自动借对宫主星)
 12. 12 大限                 (阴男阳女逆行修正)
 13. 格局                    (15 格自动识别: 紫府同宫/府相朝垣/阳梁昌禄/机月
                              同梁/杀破狼/火贪/铃贪/武贪/日月同宫/明珠出海/
                              辅弼夹命/昌曲夹命/羊陀夹忌/空劫夹命/马头带箭)

Args mirror bazi_calc.py — lunar birthday is recommended for accuracy.

Usage:
    python ziwei_calc.py --year 1995 --month 7 --day 20 --hour 1 \\
        --gender female --lunar
"""

from __future__ import annotations

import argparse
import sys

# Section 17 — CLI / main
# --------------------------------------------------------------------------- #
from utils import (
    DIZHI,
    __version__,
    ensure_utf8_stdio,
    json_print,
    longitude_correction,
    lookup_city,
    require_lunar,
    resolve_timezone_offset,
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

On error: {"error": ..., "message": ...} and exit 1."""


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
                   help="略过 自化/大限四化/流年四化")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)

    require_lunar()
    from lunar_python import Lunar, Solar  # type: ignore

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
        json_print({
            "ok": False, "tool": "ziwei",
            "error": "invalid_date", "message": str(exc),
            "input": vars(args),
        })
        return 1

    # 真太阳时校正 — 仅当用户显式提供非默认经度/时区时应用。
    # 紫微输入通常是粗粒度时辰; 默认经度(120)/时区(8) 表示"未提供精确出生地",
    # 此时保留所输入时辰原样, 避免 EOT 把临界时辰(如 01:00)误推过 时辰边界。
    # 给出真实经度即视为有精确出生地, 按 bazi 同法校正(近子时可滚日)。
    birthplace = None
    if args.city:
        row = lookup_city(args.city)
        if row is None:
            json_print({"ok": False, "tool": "ziwei", "error": "unknown_city",
                        "message": f"未收录出生地: {args.city}; 请改传 --longitude 与 --timezone"})
            return 1
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

    tz_info = None
    tz_offset = args.tz
    if args.timezone:
        try:
            tz_info = resolve_timezone_offset(
                args.timezone, solar.getYear(), solar.getMonth(),
                solar.getDay(), args.hour, args.minute,
            )
        except ValueError as exc:
            json_print({"ok": False, "tool": "ziwei",
                        "error": "invalid_timezone", "message": str(exc)})
            return 1
        tz_offset = tz_info["offset_hours"]

    tst_applied = False
    birth_hour = args.hour
    if args.longitude != 120.0 or tz_offset != 8.0:
        try:
            day_off, corr_hour, corr_minute = longitude_correction(
                args.hour, args.minute, args.longitude, tz_offset,
                year=solar.getYear(), month=solar.getMonth(), day=solar.getDay(),
            )
            if (day_off, corr_hour, corr_minute) != (0, args.hour, args.minute):
                from datetime import date, timedelta
                base = date(solar.getYear(), solar.getMonth(), solar.getDay())
                if day_off:
                    base = base + timedelta(days=day_off)
                solar = Solar.fromYmdHms(base.year, base.month, base.day,
                                         corr_hour, corr_minute, 0)
                lunar = solar.getLunar()
            birth_hour = corr_hour
            tst_applied = True
        except Exception as exc:
            warn(f"true_solar_time correction skipped: {exc}")
            birth_hour = args.hour

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
    # 闰月归属 — 02-ziwei-paipan.md:15: 十五日前算本月, 十五日后算下月 (主流).
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
            f"闰月十五日后, 按主流取法算作下月 ({abs(raw_month)} -> {lunar_month} 月) "
            f"排命宫/身宫/斗君; 见 references/02-ziwei-paipan.md 闰月处理。"
        )
    elif is_leap_month:
        leap_note.append(
            f"闰月十五日前, 按主流取法算作本月 ({lunar_month} 月); "
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
    dou_jun_branch = calc_dou_jun(lunar_month, birth_hour)

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
        "ziwei_position": zw_branch,
        "main_stars_positions": main_pos,
        "lucky_stars_positions": lucky_pos,
        "malefic_stars_positions": malefic_pos,
        "miscellaneous_stars_positions": misc_pos,
        "twelve_palaces": annotated,
        "four_transformations_native": sihua_native,
        "da_xian": da_xian,
        "liu_nian_sihua": liu_nian_sihua,
        "patterns": patterns,
        "sect": sect_info,
        "birthplace": birthplace,
        "timezone": tz_info,
        "notes": sect_note + leap_note
        + ([tz_info["note"]] if tz_info and tz_info["note"] else [])
        + [
            "本输出含 命宫/身宫/五行局/紫微/14主星/六吉六煞/9杂曜/12宫/借宫/自化/大限四化/格局识别。",
            "亮度依《紫微斗数全书·形性赋》简化为 庙/旺/平/陷, 实战可再细化为 庙旺得地利平不闲陷 七级。",
            "流年/流月/流日 需配合 斗君 起算; 本盘输出 dou_jun 提供锚位。",
            "三合派与飞星派对火铃起例及部分自化有分歧, 本脚本采用《紫微斗数全书》主流。",
        ],
    }

    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
