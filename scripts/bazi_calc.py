"""Compute a full BaZi (八字) chart.

Outputs four pillars, hidden stems, 十神, 五行 distribution, 纳音,
常见神煞, 大运 sequence, and 流年 hints. Backed by lunar_python.

Usage:
    python bazi_calc.py --year 1990 --month 6 --day 15 --hour 14 --minute 30 \\
        --gender male --tz 8 --longitude 121.47

Output: pretty UTF-8 JSON on stdout.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from utils import (
    DIZHI,
    DIZHI_ZODIAC,
    HIDDEN_STEMS,
    TIANGAN,
    TIANGAN_WUXING,
    DIZHI_WUXING,
    WUXING_GEN,
    WUXING_KE,
    json_print,
    longitude_correction,
    require_lunar,
    shi_shen,
    warn,
)


# --------------------------------------------------------------------------- #
# 神煞 tables
# --------------------------------------------------------------------------- #

# 天乙贵人 (day-stem -> [branches]) — 玉堂诀
TIAN_YI: dict[str, list[str]] = {
    "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
    "乙": ["子", "申"], "己": ["子", "申"],
    "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "壬": ["卯", "巳"], "癸": ["卯", "巳"],
    "辛": ["寅", "午"],
}

# 文昌贵人 (day-stem -> branch)
WEN_CHANG: dict[str, str] = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
    "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}

# 桃花 (year/day branch group -> branch)
# 三合局: 申子辰->酉, 寅午戌->卯, 巳酉丑->午, 亥卯未->子
TAO_HUA_MAP: dict[str, str] = {
    "申": "酉", "子": "酉", "辰": "酉",
    "寅": "卯", "午": "卯", "戌": "卯",
    "巳": "午", "酉": "午", "丑": "午",
    "亥": "子", "卯": "子", "未": "子",
}

# 驿马
YI_MA_MAP: dict[str, str] = {
    "申": "寅", "子": "寅", "辰": "寅",
    "寅": "申", "午": "申", "戌": "申",
    "巳": "亥", "酉": "亥", "丑": "亥",
    "亥": "巳", "卯": "巳", "未": "巳",
}

# 华盖
HUA_GAI_MAP: dict[str, str] = {
    "申": "辰", "子": "辰", "辰": "辰",
    "寅": "戌", "午": "戌", "戌": "戌",
    "巳": "丑", "酉": "丑", "丑": "丑",
    "亥": "未", "卯": "未", "未": "未",
}

# 羊刃 (day-stem -> branch) — 阳干刃在帝旺, 阴干本气帝旺
YANG_REN: dict[str, str] = {
    "甲": "卯", "乙": "寅",
    "丙": "午", "丁": "巳", "戊": "午", "己": "巳",
    "庚": "酉", "辛": "申",
    "壬": "子", "癸": "亥",
}

# 红艳煞 (day-stem -> branch)
HONG_YAN: dict[str, str] = {
    "甲": "午", "乙": "午",
    "丙": "寅", "丁": "未",
    "戊": "辰", "己": "辰",
    "庚": "戌", "辛": "酉",
    "壬": "子", "癸": "申",
}

# 孤辰 / 寡宿 (year branch -> 孤, 寡)
GU_GUA: dict[str, tuple[str, str]] = {
    "寅": ("巳", "丑"), "卯": ("巳", "丑"), "辰": ("巳", "丑"),
    "巳": ("申", "辰"), "午": ("申", "辰"), "未": ("申", "辰"),
    "申": ("亥", "未"), "酉": ("亥", "未"), "戌": ("亥", "未"),
    "亥": ("寅", "戌"), "子": ("寅", "戌"), "丑": ("寅", "戌"),
}

# 空亡 — depends on day-pillar's 旬 (10-day group)
# 甲子旬: 戌亥空; 甲戌旬: 申酉空; 甲申旬: 午未空; 甲午旬: 辰巳空;
# 甲辰旬: 寅卯空; 甲寅旬: 子丑空.
XUN_KONG_BY_START_STEM_OFFSET: dict[int, list[str]] = {
    0: ["戌", "亥"],   # 甲子
    1: ["申", "酉"],   # 甲戌
    2: ["午", "未"],   # 甲申
    3: ["辰", "巳"],   # 甲午
    4: ["寅", "卯"],   # 甲辰
    5: ["子", "丑"],   # 甲寅
}


def xun_kong_of_day(day_stem: str, day_branch: str) -> list[str]:
    """Return the two 地支 in 旬空 for the given day pillar."""
    ts = TIANGAN.index(day_stem)
    db = DIZHI.index(day_branch)
    # Find the 甲... that starts this 旬:
    # offset =(db - ts) mod 12 -> 0,10,8,6,4,2 corresponding to xun starts.
    diff = (db - ts) % 12
    # diff in {0,10,8,6,4,2}
    mapping = {0: 0, 10: 1, 8: 2, 6: 3, 4: 4, 2: 5}
    idx = mapping.get(diff, 0)
    return XUN_KONG_BY_START_STEM_OFFSET[idx]


# --------------------------------------------------------------------------- #
# 神煞 detection given the 4 pillars
# --------------------------------------------------------------------------- #

def detect_shensha(
    day_stem: str,
    year_branch: str,
    day_branch: str,
    branches: list[str],
) -> list[dict]:
    triggered: list[dict] = []

    # 天乙贵人
    ty = TIAN_YI.get(day_stem, [])
    for b in ty:
        if b in branches:
            triggered.append({"name": "天乙贵人", "branch": b,
                              "note": "贵人扶持, 逢凶化吉"})

    # 文昌
    wc = WEN_CHANG.get(day_stem)
    if wc and wc in branches:
        triggered.append({"name": "文昌贵人", "branch": wc,
                          "note": "聪慧好学, 利文书功名"})

    # 桃花 (以日支或年支取)
    for base in {day_branch, year_branch}:
        th = TAO_HUA_MAP.get(base)
        if th and th in branches:
            triggered.append({"name": "桃花", "branch": th,
                              "note": "异性缘佳, 主情爱与艺术"})
            break

    # 驿马
    for base in {day_branch, year_branch}:
        ym = YI_MA_MAP.get(base)
        if ym and ym in branches:
            triggered.append({"name": "驿马", "branch": ym,
                              "note": "主迁徙变动、奔波出行"})
            break

    # 华盖
    for base in {day_branch, year_branch}:
        hg = HUA_GAI_MAP.get(base)
        if hg and hg in branches:
            triggered.append({"name": "华盖", "branch": hg,
                              "note": "聪明孤高, 主艺术宗教"})
            break

    # 羊刃
    yr = YANG_REN.get(day_stem)
    if yr and yr in branches:
        triggered.append({"name": "羊刃", "branch": yr,
                          "note": "刚强果断, 易招血光"})

    # 红艳
    hy = HONG_YAN.get(day_stem)
    if hy and hy in branches:
        triggered.append({"name": "红艳", "branch": hy,
                          "note": "风流多情, 易招桃花"})

    # 孤辰 / 寡宿
    gg = GU_GUA.get(year_branch)
    if gg:
        gu, gua = gg
        if gu in branches:
            triggered.append({"name": "孤辰", "branch": gu,
                              "note": "性情孤独, 男忌"})
        if gua in branches:
            triggered.append({"name": "寡宿", "branch": gua,
                              "note": "孤僻寡合, 女忌"})

    # 空亡
    xk = xun_kong_of_day(day_stem, day_branch)
    for b in xk:
        if b in branches:
            triggered.append({"name": "空亡", "branch": b,
                              "note": "落空, 力减/事缓"})

    return triggered


# --------------------------------------------------------------------------- #
# Argparse
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="八字排盘 (BaZi chart) — 公历/农历皆可, 输出 JSON"
    )
    p.add_argument("--year", type=int, required=True, help="出生年 (公历或农历)")
    p.add_argument("--month", type=int, required=True, help="出生月 1-12")
    p.add_argument("--day", type=int, required=True, help="出生日 1-31")
    p.add_argument("--hour", type=int, required=True, help="出生时 0-23")
    p.add_argument("--minute", type=int, default=0, help="出生分 0-59")
    p.add_argument("--gender", choices=["male", "female"], required=True,
                   help="性别 (用于排大运)")
    p.add_argument("--tz", type=float, default=8.0,
                   help="时区偏移小时 (默认 8 即 GMT+8)")
    p.add_argument("--longitude", type=float, default=120.0,
                   help="出生地经度 (E°, 默认 120, 用于真太阳时)")
    p.add_argument("--lunar", action="store_true",
                   help="若指定, 视输入日期为农历")
    p.add_argument("--years", type=int, default=80,
                   help="大运覆盖年数 (默认 80)")
    return p


# --------------------------------------------------------------------------- #
# Pillar -> dict
# --------------------------------------------------------------------------- #

def pillar_dict(stem: str, branch: str, nayin: str) -> dict:
    return {
        "stem": stem,
        "branch": branch,
        "ganzhi": f"{stem}{branch}",
        "stem_wuxing": TIANGAN_WUXING.get(stem),
        "branch_wuxing": DIZHI_WUXING.get(branch),
        "hidden_stems": HIDDEN_STEMS.get(branch, []),
        "nayin": nayin,
        "zodiac": DIZHI_ZODIAC.get(branch),
    }


def wuxing_count(pillars: dict) -> dict:
    counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for p in pillars.values():
        w = TIANGAN_WUXING.get(p["stem"])
        if w:
            counts[w] += 1
        w = DIZHI_WUXING.get(p["branch"])
        if w:
            counts[w] += 1
        # add hidden stems (lighter weight: 0.5 each)
    # also count hidden stems weighted 0.5
    hidden_counts = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    for p in pillars.values():
        for hs in p["hidden_stems"]:
            hw = TIANGAN_WUXING.get(hs)
            if hw:
                hidden_counts[hw] += 0.5
    combined = {k: counts[k] + hidden_counts[k] for k in counts}
    return {"surface": counts, "with_hidden": combined}


def ten_gods_per_pillar(day_stem: str, pillars: dict) -> dict:
    out: dict = {}
    for label, p in pillars.items():
        entry: dict = {"stem": None, "hidden": []}
        try:
            entry["stem"] = shi_shen(day_stem, p["stem"])
        except Exception:
            entry["stem"] = None
        for hs in p["hidden_stems"]:
            try:
                entry["hidden"].append({"stem": hs, "shi_shen": shi_shen(day_stem, hs)})
            except Exception:
                pass
        out[label] = entry
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    lunar_pkg = require_lunar()
    from lunar_python import Solar, Lunar  # type: ignore

    # Longitude correction
    corr_hour, corr_minute = longitude_correction(
        args.hour, args.minute, args.longitude, args.tz
    )

    # Build solar object
    try:
        if args.lunar:
            lunar = Lunar.fromYmdHms(
                args.year, args.month, args.day, corr_hour, corr_minute, 0
            )
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(
                args.year, args.month, args.day, corr_hour, corr_minute, 0
            )
            lunar = solar.getLunar()
    except Exception as e:
        json_print({"error": "invalid_date", "message": str(e),
                    "input": vars(args)})
        return 1

    try:
        eight = lunar.getEightChar()
    except Exception as e:
        json_print({"error": "bazi_failed", "message": str(e),
                    "input": vars(args)})
        return 1

    # Try to set sect to 2 (子时归当日) which is standard for many almanacs.
    try:
        eight.setSect(2)
    except Exception:
        pass

    year_gz = (eight.getYearGan(), eight.getYearZhi())
    month_gz = (eight.getMonthGan(), eight.getMonthZhi())
    day_gz = (eight.getDayGan(), eight.getDayZhi())
    hour_gz = (eight.getTimeGan(), eight.getTimeZhi())

    year_nayin = eight.getYearNaYin()
    month_nayin = eight.getMonthNaYin()
    day_nayin = eight.getDayNaYin()
    hour_nayin = eight.getTimeNaYin()

    pillars = {
        "year":  pillar_dict(*year_gz,  year_nayin),
        "month": pillar_dict(*month_gz, month_nayin),
        "day":   pillar_dict(*day_gz,   day_nayin),
        "hour":  pillar_dict(*hour_gz,  hour_nayin),
    }

    day_stem = day_gz[0]
    branches = [year_gz[1], month_gz[1], day_gz[1], hour_gz[1]]
    shensha = detect_shensha(day_stem, year_gz[1], day_gz[1], branches)

    # 大运 via lunar_python
    da_yun_list = []
    try:
        yun = eight.getYun(1 if args.gender == "male" else 0)
        start_solar = yun.getStartSolar()
        cycles = yun.getDaYun(args.years // 10 + 2)
        # Skip the cycle representing 起运前 if applicable.
        for d in cycles:
            ganzhi = d.getGanZhi()
            if not ganzhi:
                continue
            da_yun_list.append({
                "start_age": d.getStartAge(),
                "start_year": d.getStartYear(),
                "end_year": d.getEndYear(),
                "ganzhi": ganzhi,
            })
        qiyun = {
            "start_year": start_solar.getYear(),
            "start_month": start_solar.getMonth(),
            "start_day": start_solar.getDay(),
            "start_age": yun.getStartYear(),
        }
    except Exception as e:
        warn(f"da_yun unavailable: {e}")
        qiyun = None

    # 流年 — current solar year + next 5
    liu_nian: list[dict] = []
    try:
        from datetime import datetime
        now_year = datetime.now().year
        for y in range(now_year, now_year + 6):
            ly = Solar.fromYmdHms(y, 6, 1, 12, 0, 0).getLunar()
            liu_nian.append({
                "year": y,
                "ganzhi": ly.getYearInGanZhi(),
                "zodiac": ly.getYearShengXiao(),
            })
    except Exception as e:
        warn(f"liu_nian failed: {e}")

    result = {
        "input": vars(args),
        "solar_date": {
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(), "hour": solar.getHour(),
            "minute": solar.getMinute(),
        },
        "lunar_date": {
            "year": lunar.getYear(), "month": lunar.getMonth(),
            "day": lunar.getDay(),
            "year_in_ganzhi": lunar.getYearInGanZhi(),
            "month_in_ganzhi": lunar.getMonthInGanZhi(),
            "day_in_ganzhi": lunar.getDayInGanZhi(),
            "time_in_ganzhi": lunar.getTimeInGanZhi(),
            "year_in_chinese": lunar.getYearInChinese(),
            "month_in_chinese": lunar.getMonthInChinese(),
            "day_in_chinese": lunar.getDayInChinese(),
            "zodiac": lunar.getYearShengXiao(),
        },
        "true_solar_time": {
            "hour": corr_hour, "minute": corr_minute,
            "longitude": args.longitude,
        },
        "four_pillars": pillars,
        "day_master": {
            "stem": day_stem,
            "wuxing": TIANGAN_WUXING.get(day_stem),
            "yin_yang": "阳" if TIANGAN.index(day_stem) % 2 == 0 else "阴",
        },
        "ten_gods": ten_gods_per_pillar(day_stem, pillars),
        "wuxing_count": wuxing_count(pillars),
        "na_yin": {
            "year": year_nayin, "month": month_nayin,
            "day": day_nayin, "hour": hour_nayin,
        },
        "shen_sha": shensha,
        "qi_yun": qiyun,
        "da_yun": da_yun_list,
        "liu_nian": liu_nian,
    }

    json_print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
