"""紫微斗数 (Zi Wei Dou Shu) — core chart.

Implements the standard core formulas:
    1. 命宫 / 身宫 (with 寅宫起正月 起例)
    2. 五行局 (from 命宫 stem-branch)
    3. 紫微星 position (五行局 + 农历生日)
    4. 14 主星 positions (relative to 紫微/天府)
    5. 12 大限 by 五行局
    6. 三方四正 for each palace
    7. 四化 (禄/权/科/忌) by 年干

Scope:
    - Calculates the stable core chart layers used for first-pass readings.
    - Advanced layers such as full auxiliary stars, malefics, self-transformations,
      annual/monthly/daily charts, and 命主身主 require a dedicated school table
      or a user-supplied chart.

Args mirror bazi_calc.py — lunar birthday is recommended for accuracy.

Usage:
    python ziwei_calc.py --year 1990 --month 5 --day 15 --hour 14 --minute 0 \\
        --gender male --lunar
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from utils import (
    DIZHI, TIANGAN, TIANGAN_WUXING,
    json_print, require_lunar, warn,
)


# 寅宫起正月 — month 1 -> 寅, month 2 -> 卯, ..., 12 -> 丑
def branch_of_lunar_month(lunar_month: int) -> str:
    """Lunar month 1..12 -> branch starting from 寅."""
    return DIZHI[(2 + (lunar_month - 1)) % 12]  # 寅 is index 2


# 时辰 branch by hour. 子=23-1, 丑=1-3, 寅=3-5, ...
def branch_of_hour(hour: int) -> str:
    if hour == 23 or hour == 0:
        return "子"
    return DIZHI[((hour + 1) // 2) % 12]


# --------------------------------------------------------------------------- #
# 命宫 / 身宫
# --------------------------------------------------------------------------- #
# 寅宫起正月, 顺数到生月; 再从生月宫起子时, 逆数至生时, 落点 = 命宫.
# 身宫: 同上, 但从生月宫起子时顺数至生时.

def calc_ming_gong(lunar_month: int, hour: int) -> str:
    month_branch_idx = (2 + (lunar_month - 1)) % 12  # 寅 起
    hour_idx = DIZHI.index(branch_of_hour(hour))     # 子=0, 丑=1, ...
    # 起子时于月宫, 逆数至生时
    mg_idx = (month_branch_idx - hour_idx) % 12
    return DIZHI[mg_idx]


def calc_shen_gong(lunar_month: int, hour: int) -> str:
    month_branch_idx = (2 + (lunar_month - 1)) % 12
    hour_idx = DIZHI.index(branch_of_hour(hour))
    sg_idx = (month_branch_idx + hour_idx) % 12
    return DIZHI[sg_idx]


# --------------------------------------------------------------------------- #
# 命宫天干 — by 五虎遁 from 年干
# --------------------------------------------------------------------------- #
# 寅月之干即 五虎遁: 甲己丙寅, 乙庚戊寅, 丙辛庚寅, 丁壬壬寅, 戊癸甲寅.
# 命宫天干 = 五虎遁推到命宫所在的月支序号.

YIN_MONTH_STEM = {
    "甲": "丙", "己": "丙",
    "乙": "戊", "庚": "戊",
    "丙": "庚", "辛": "庚",
    "丁": "壬", "壬": "壬",
    "戊": "甲", "癸": "甲",
}


def stem_of_palace(year_stem: str, palace_branch: str) -> str:
    """Return 天干 of a palace using 五虎遁 from 年干."""
    start_stem = YIN_MONTH_STEM[year_stem]  # 寅 月之干
    yin_idx = DIZHI.index("寅")
    target_idx = DIZHI.index(palace_branch)
    diff = (target_idx - yin_idx) % 12
    start_idx = TIANGAN.index(start_stem)
    return TIANGAN[(start_idx + diff) % 10]


# --------------------------------------------------------------------------- #
# 五行局
# --------------------------------------------------------------------------- #
# Determined by 命宫 的 (天干, 地支) -> 六十甲子纳音 五行变体.
# 标准对照: 命宫 干支 → 五行局 (一共五种):
#   水二局 / 木三局 / 金四局 / 土五局 / 火六局
# Convenient formula: 用 命宫 干支 之纳音 -> 五行局.
# 纳音五行 对应 局数: 水=2, 木=3, 金=4, 土=5, 火=6.

# 六十甲子纳音表 — index 0..59 = 甲子 ~ 癸亥
NAYIN_60 = [
    "海中金", "海中金", "炉中火", "炉中火", "大林木", "大林木",
    "路旁土", "路旁土", "剑锋金", "剑锋金", "山头火", "山头火",
    "涧下水", "涧下水", "城头土", "城头土", "白蜡金", "白蜡金",
    "杨柳木", "杨柳木", "井泉水", "井泉水", "屋上土", "屋上土",
    "霹雳火", "霹雳火", "松柏木", "松柏木", "长流水", "长流水",
    "沙中金", "沙中金", "山下火", "山下火", "平地木", "平地木",
    "壁上土", "壁上土", "金箔金", "金箔金", "覆灯火", "覆灯火",
    "天河水", "天河水", "大驿土", "大驿土", "钗钏金", "钗钏金",
    "桑柘木", "桑柘木", "大溪水", "大溪水", "沙中土", "沙中土",
    "天上火", "天上火", "石榴木", "石榴木", "大海水", "大海水",
]


def jiazi_index(stem: str, branch: str) -> int:
    s = TIANGAN.index(stem)
    b = DIZHI.index(branch)
    for i in range(60):
        if i % 10 == s and i % 12 == b:
            return i
    raise ValueError(f"invalid 甲子: {stem}{branch}")


NAYIN_WX_KEYWORD = {
    "金": ["海中金", "剑锋金", "白蜡金", "沙中金", "金箔金", "钗钏金"],
    "火": ["炉中火", "山头火", "霹雳火", "山下火", "覆灯火", "天上火"],
    "木": ["大林木", "杨柳木", "松柏木", "平地木", "桑柘木", "石榴木"],
    "水": ["涧下水", "井泉水", "长流水", "天河水", "大溪水", "大海水"],
    "土": ["路旁土", "城头土", "屋上土", "壁上土", "大驿土", "沙中土"],
}


def nayin_wuxing(stem: str, branch: str) -> str:
    name = NAYIN_60[jiazi_index(stem, branch)]
    for wx, names in NAYIN_WX_KEYWORD.items():
        if name in names:
            return wx
    return "?"


# 五行局 number per 命宫 纳音 五行
WUXING_JU_NUM = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
WUXING_JU_NAME = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}


def wuxing_ju(year_stem: str, ming_gong_branch: str) -> tuple[int, str]:
    stem = stem_of_palace(year_stem, ming_gong_branch)
    wx = nayin_wuxing(stem, ming_gong_branch)
    num = WUXING_JU_NUM.get(wx, 5)
    return num, WUXING_JU_NAME[num]


# --------------------------------------------------------------------------- #
# 紫微星 position
# --------------------------------------------------------------------------- #
# Standard formula:
#   Let n = 局数 (2..6), d = 农历生日.
#   q = ceil(d / n)   (商, 余数 r = q*n - d)
#   if r is even (含 0): 紫微在 q-起寅地支顺数; if r odd, 逆数.
# 实际我们使用查表: position table for each ju/day pair.
# A more robust direct algorithm:
#   q = (d + n - 1) // n  (the quotient when d is divided by n, rounding up)
#   r = q * n - d         (the remainder; r is 0..n-1)
#   if r even: 起寅顺数 (q-1) 宫
#   if r odd:  起寅逆数 (q-1) 宫
# Wait — this is not quite the standard. The classical method uses a per-day
# table because direct division leaves edge cases. We embed the well-known
# table here for full accuracy.
# --------------------------------------------------------------------------- #

# Table: row = 局 (2..6), col = 生日 (1..30) -> 紫微所在地支
# Compiled from a standard 紫微斗数 排盘参考表.
ZIWEI_TABLE: dict[int, list[str]] = {
    2: [  # 水二局
        "丑", "寅", "寅", "卯", "卯", "辰", "辰", "巳", "巳", "午",
        "午", "未", "未", "申", "申", "酉", "酉", "戌", "戌", "亥",
        "亥", "子", "子", "丑", "丑", "寅", "寅", "卯", "卯", "辰",
    ],
    3: [  # 木三局
        "辰", "丑", "寅", "巳", "寅", "卯", "午", "卯", "辰", "未",
        "辰", "巳", "申", "巳", "午", "酉", "午", "未", "戌", "未",
        "申", "亥", "申", "酉", "子", "酉", "戌", "丑", "戌", "亥",
    ],
    4: [  # 金四局
        "亥", "辰", "丑", "寅", "子", "巳", "寅", "卯", "丑", "午",
        "卯", "辰", "寅", "未", "辰", "巳", "卯", "申", "巳", "午",
        "辰", "酉", "午", "未", "巳", "戌", "未", "申", "午", "亥",
    ],
    5: [  # 土五局
        "午", "亥", "辰", "丑", "寅", "未", "子", "巳", "寅", "卯",
        "申", "丑", "午", "卯", "辰", "酉", "寅", "未", "辰", "巳",
        "戌", "卯", "申", "巳", "午", "亥", "辰", "酉", "午", "未",
    ],
    6: [  # 火六局
        "酉", "午", "亥", "辰", "丑", "寅", "戌", "未", "子", "巳",
        "寅", "卯", "亥", "申", "丑", "午", "卯", "辰", "子", "酉",
        "寅", "未", "辰", "巳", "丑", "戌", "卯", "申", "巳", "午",
    ],
}


def ziwei_position(ju: int, lunar_day: int) -> str:
    d = max(1, min(30, lunar_day))
    return ZIWEI_TABLE.get(ju, ZIWEI_TABLE[5])[d - 1]


# --------------------------------------------------------------------------- #
# 14 主星 positions, relative to 紫微 / 天府
# --------------------------------------------------------------------------- #

# 紫微系 (six): 紫微, 天机, 太阳, 武曲, 天同, 廉贞.
# Movement relative to 紫微 — fixed offsets going BACKWARDS (逆时针):
#   紫微: 0
#   天机: -1 (紫微逆一位)
#   太阳: -3 (紫微逆三位)
#   武曲: -4
#   天同: -5
#   廉贞: -8

ZIWEI_OFFSETS = {
    "紫微": 0,
    "天机": -1,
    "太阳": -3,
    "武曲": -4,
    "天同": -5,
    "廉贞": -8,
}

# 天府系 (eight): 天府, 太阴, 贪狼, 巨门, 天相, 天梁, 七杀, 破军.
# 天府 position:
#   On the 寅申 axis, 紫微 & 天府 are mirror images.
#   Practical rule: 天府 = 12 - (紫微 index relative to 寅) starting from 寅 going forward...
#   Simpler: 紫微 & 天府 are 沿丑未连线的镜像. If 紫微 at 寅, 天府 at 戌; the mapping is:
#     紫微 寅<->天府 戌, 卯<->酉, 辰<->申, 巳<->未, 午<->午, 未<->巳, 申<->辰, 酉<->卯, 戌<->寅,
#     亥<->丑, 子<->子, 丑<->亥.
#   (i.e., reflection about the 子-午 axis.)

TIANFU_MIRROR = {
    "寅": "戌", "卯": "酉", "辰": "申", "巳": "未", "午": "午",
    "未": "巳", "申": "辰", "酉": "卯", "戌": "寅", "亥": "丑",
    "子": "子", "丑": "亥",
}

# 天府系 forward offsets from 天府 (顺时针, i.e. +1, +2, ...):
TIANFU_OFFSETS = {
    "天府": 0,
    "太阴": 1,
    "贪狼": 2,
    "巨门": 3,
    "天相": 4,
    "天梁": 5,
    "七杀": 6,
    "破军": 10,  # 七杀后三位的"破军" — 实际 +10
}


def place_main_stars(ziwei_branch: str) -> dict[str, str]:
    out: dict[str, str] = {}
    zw_idx = DIZHI.index(ziwei_branch)
    for star, off in ZIWEI_OFFSETS.items():
        out[star] = DIZHI[(zw_idx + off) % 12]
    tf_branch = TIANFU_MIRROR[ziwei_branch]
    tf_idx = DIZHI.index(tf_branch)
    for star, off in TIANFU_OFFSETS.items():
        out[star] = DIZHI[(tf_idx + off) % 12]
    return out


# --------------------------------------------------------------------------- #
# 12 palace names — fixed sequence anti-clockwise from 命宫
# --------------------------------------------------------------------------- #

PALACE_NAMES = [
    "命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
    "迁移宫", "奴仆宫", "官禄宫", "田宅宫", "福德宫", "父母宫",
]


def assign_palaces(ming_gong_branch: str) -> list[dict]:
    """Return 12 palaces in forward order starting from 命宫."""
    mg_idx = DIZHI.index(ming_gong_branch)
    out = []
    for i in range(12):
        # 命宫 going 逆时针 (反方向) gives 兄弟, 夫妻, ... per classical layout
        branch_idx = (mg_idx - i) % 12
        out.append({
            "name": PALACE_NAMES[i],
            "branch": DIZHI[branch_idx],
            "branch_index": branch_idx,
        })
    return out


# --------------------------------------------------------------------------- #
# 三方四正 — for each palace
# --------------------------------------------------------------------------- #
# 本宫 + 对宫(+6) + 三合宫(±4)
def san_fang_si_zheng(palace_idx_in_12: int, palaces: list[dict]) -> dict:
    branch = palaces[palace_idx_in_12]["branch"]
    b_idx = DIZHI.index(branch)
    duigong = DIZHI[(b_idx + 6) % 12]
    sanhe1 = DIZHI[(b_idx + 4) % 12]
    sanhe2 = DIZHI[(b_idx - 4) % 12]
    return {"本宫": branch, "对宫": duigong, "三合": [sanhe1, sanhe2]}


# --------------------------------------------------------------------------- #
# 大限 — based on 五行局, 阳男阴女顺行 阴男阳女逆行
# --------------------------------------------------------------------------- #

def da_xian_ranges(ju: int, gender: str, year_stem: str,
                   palaces: list[dict]) -> list[dict]:
    yang_stem = TIANGAN.index(year_stem) % 2 == 0  # 阳干
    forward = (yang_stem and gender == "male") or (not yang_stem and gender == "female")
    out = []
    for i, p in enumerate(palaces):
        # palace at index i (with name PALACE_NAMES[i])
        start_age = ju + i * 10
        out.append({
            "palace": p["name"],
            "branch": p["branch"],
            "start_age": start_age,
            "end_age": start_age + 9,
            "direction": "顺行" if forward else "逆行",
        })
    # If 逆行, swap the order of 大限 (well — 大限 follows reverse palace order)
    if not forward:
        # 大限 starts at 命宫 but follows reverse direction
        reversed_palaces = [palaces[0]] + list(reversed(palaces[1:]))
        for i, p in enumerate(reversed_palaces):
            out[i]["palace"] = PALACE_NAMES[i] if i == 0 else palaces[(12 - i) % 12]["name"]
            out[i]["branch"] = p["branch"]
    return out


# --------------------------------------------------------------------------- #
# 四化 — 年干 -> {禄, 权, 科, 忌}
# --------------------------------------------------------------------------- #

SI_HUA: dict[str, dict[str, str]] = {
    "甲": {"禄": "廉贞", "权": "破军", "科": "武曲", "忌": "太阳"},
    "乙": {"禄": "天机", "权": "天梁", "科": "紫微", "忌": "太阴"},
    "丙": {"禄": "天同", "权": "天机", "科": "文昌", "忌": "廉贞"},
    "丁": {"禄": "太阴", "权": "天同", "科": "天机", "忌": "巨门"},
    "戊": {"禄": "贪狼", "权": "太阴", "科": "右弼", "忌": "天机"},
    "己": {"禄": "武曲", "权": "贪狼", "科": "天梁", "忌": "文曲"},
    "庚": {"禄": "太阳", "权": "武曲", "科": "太阴", "忌": "天同"},
    "辛": {"禄": "巨门", "权": "太阳", "科": "文曲", "忌": "文昌"},
    "壬": {"禄": "天梁", "权": "紫微", "科": "左辅", "忌": "武曲"},
    "癸": {"禄": "破军", "权": "巨门", "科": "太阴", "忌": "贪狼"},
}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="紫微斗数核心排盘 (命宫/身宫/五行局/紫微/14主星/12宫/大限/四化)"
    )
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--hour", type=int, required=True)
    p.add_argument("--minute", type=int, default=0)
    p.add_argument("--gender", choices=["male", "female"], required=True)
    p.add_argument("--tz", type=float, default=8.0)
    p.add_argument("--longitude", type=float, default=120.0)
    p.add_argument("--lunar", action="store_true",
                   help="若指定, 视输入年月日为农历")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    require_lunar()
    from lunar_python import Solar, Lunar  # type: ignore

    try:
        if args.lunar:
            lunar = Lunar.fromYmdHms(
                args.year, args.month, args.day, args.hour, args.minute, 0
            )
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(
                args.year, args.month, args.day, args.hour, args.minute, 0
            )
            lunar = solar.getLunar()
    except Exception as e:
        json_print({"error": "invalid_date", "message": str(e), "input": vars(args)})
        return 1

    year_stem = lunar.getYearGan()
    year_branch = lunar.getYearZhi()
    lunar_month = abs(lunar.getMonth())
    lunar_day = lunar.getDay()

    mg_branch = calc_ming_gong(lunar_month, args.hour)
    sg_branch = calc_shen_gong(lunar_month, args.hour)
    mg_stem = stem_of_palace(year_stem, mg_branch)

    ju_num, ju_name = wuxing_ju(year_stem, mg_branch)

    zw_branch = ziwei_position(ju_num, lunar_day)
    main_stars_pos = place_main_stars(zw_branch)

    palaces = assign_palaces(mg_branch)

    # Inverse map: branch -> list of stars
    branch_to_stars: dict[str, list[str]] = {b: [] for b in DIZHI}
    for star, b in main_stars_pos.items():
        branch_to_stars[b].append(star)

    # 四化
    sihua = SI_HUA.get(year_stem, {})

    # Annotate palaces with stars + 四化 markers
    annotated: list[dict] = []
    for i, p in enumerate(palaces):
        stars = branch_to_stars[p["branch"]]
        hua_markers: list[dict] = []
        for hua_type, star in sihua.items():
            if star in stars:
                hua_markers.append({"type": hua_type, "star": star})
        sfsz = san_fang_si_zheng(i, palaces)
        annotated.append({
            "index": i,
            "name": p["name"],
            "branch": p["branch"],
            "stem": stem_of_palace(year_stem, p["branch"]),
            "main_stars": stars,
            "si_hua": hua_markers,
            "san_fang_si_zheng": sfsz,
            "is_ming_gong": (i == 0),
            "is_shen_gong": (p["branch"] == sg_branch),
            "advanced_layers_note": "副星/辅星/煞曜需按指定流派表另排；本脚本输出核心主星盘。",
        })

    da_xian = da_xian_ranges(ju_num, args.gender, year_stem, palaces)

    out = {
        "input": vars(args),
        "solar_date": {
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(), "hour": solar.getHour(),
            "minute": solar.getMinute(),
        },
        "lunar_date": {
            "year": lunar.getYear(), "month": lunar_month,
            "day": lunar_day,
            "year_ganzhi": lunar.getYearInGanZhi(),
            "month_chinese": lunar.getMonthInChinese(),
            "day_chinese": lunar.getDayInChinese(),
        },
        "ming_gong": {
            "branch": mg_branch,
            "stem": mg_stem,
            "ganzhi": f"{mg_stem}{mg_branch}",
        },
        "shen_gong": {"branch": sg_branch},
        "wuxing_ju": {"number": ju_num, "name": ju_name},
        "ziwei_position": zw_branch,
        "main_stars_positions": main_stars_pos,
        "twelve_palaces": annotated,
        "four_transformations": sihua,
        "da_xian": da_xian,
        "notes": [
            "本输出为核心命盘: 命宫/身宫/五行局/紫微/14主星/12宫名/三方四正/大限/年干四化均已计算。",
            "副星、煞星、长生十二神、命主身主、自化、流年/流月/流日等高级层建议按指定流派表或用户提供的完整命盘解读。",
            "如需高精度, 建议结合 lunar_python 节气、北斗导航等数据校准时辰边界。",
        ],
    }

    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
