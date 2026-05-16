"""六爻 (Liu Yao) full chart — extends 周易 with 装卦.

Adds: 八宫归属, 世应, 六亲, 六神, 纳甲 (each line's stem/branch),
旺相休囚, 月破/日破/旬空 markers, and a brief 用神 hint.

Usage:
    python liuyao_cast.py coins [--seed N] [--date YYYY-MM-DD] [--time HH:MM]
                                [--question "..."]
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime
from typing import Optional

from utils import (
    BAGUA,
    BINARY_TO_TRIGRAM,
    DIZHI,
    DIZHI_WUXING,
    TIANGAN,
    TIANGAN_WUXING,
    WUXING_GEN,
    WUXING_KE,
    json_print,
    require_lunar,
    warn,
)

from yijing_cast import (
    cast_coins, lines_to_trigrams, hex_lookup_by_trigrams,
    line_visual, active_lines, changed_lines, nuclear_lines,
    load_hex_assets,
)


# --------------------------------------------------------------------------- #
# 八宫 — assign each of the 64 hexagrams to one of 8 palaces.
# 京房纳甲 standard mapping. Each palace has 8 hexagrams in fixed order:
#   1. 本宫卦 (8 纯卦)
#   2. 一世
#   3. 二世
#   4. 三世
#   5. 四世
#   6. 五世
#   7. 游魂
#   8. 归魂
# The 世爻 position is: 1世=line1, 2世=line2, 3世=line3, 4世=line4, 5世=line5,
# 6世/本宫=line6, 游魂=line4 (because 5th flips back), 归魂=line3.
# 应爻 = 世爻 + 3 (mod 6, 1-indexed).
# --------------------------------------------------------------------------- #

EIGHT_PALACES: dict[str, list[tuple[int, str]]] = {
    # palace_name -> [(king_wen_num, role), ...]
    "乾宫": [
        (1, "本宫"), (44, "一世"), (33, "二世"), (12, "三世"),
        (20, "四世"), (23, "五世"), (35, "游魂"), (14, "归魂"),
    ],
    "兑宫": [
        (58, "本宫"), (47, "一世"), (45, "二世"), (31, "三世"),
        (39, "四世"), (15, "五世"), (62, "游魂"), (54, "归魂"),
    ],
    "离宫": [
        (30, "本宫"), (56, "一世"), (50, "二世"), (64, "三世"),
        (4,  "四世"), (59, "五世"), (6,  "游魂"), (13, "归魂"),
    ],
    "震宫": [
        (51, "本宫"), (16, "一世"), (40, "二世"), (32, "三世"),
        (46, "四世"), (48, "五世"), (28, "游魂"), (17, "归魂"),
    ],
    "巽宫": [
        (57, "本宫"), (9,  "一世"), (37, "二世"), (42, "三世"),
        (25, "四世"), (21, "五世"), (27, "游魂"), (18, "归魂"),
    ],
    "坎宫": [
        (29, "本宫"), (60, "一世"), (3,  "二世"), (63, "三世"),
        (49, "四世"), (55, "五世"), (36, "游魂"), (7,  "归魂"),
    ],
    "艮宫": [
        (52, "本宫"), (22, "一世"), (26, "二世"), (41, "三世"),
        (38, "四世"), (10, "五世"), (61, "游魂"), (53, "归魂"),
    ],
    "坤宫": [
        (2,  "本宫"), (24, "一世"), (19, "二世"), (11, "三世"),
        (34, "四世"), (43, "五世"), (5,  "游魂"), (8,  "归魂"),
    ],
}

ROLE_TO_SHIYAO: dict[str, int] = {
    "本宫": 6, "一世": 1, "二世": 2, "三世": 3,
    "四世": 4, "五世": 5, "游魂": 4, "归魂": 3,
}


def find_palace(hex_num: int) -> tuple[Optional[str], Optional[str]]:
    for palace, entries in EIGHT_PALACES.items():
        for n, role in entries:
            if n == hex_num:
                return palace, role
    return None, None


def shi_yao_position(role: str) -> int:
    return ROLE_TO_SHIYAO.get(role, 0)


def ying_yao_position(shi: int) -> int:
    return ((shi - 1 + 3) % 6) + 1


# --------------------------------------------------------------------------- #
# 纳甲 — 京房纳甲法.
# Per-trigram, the 6 yao receive specific stems and branches.
# Lower trigram fills lines 1,2,3 (bottom→top), upper fills 4,5,6.
# Reference table:
# 乾: 子寅辰 / 午申戌  (stem 甲 for inner, 壬 for outer)
# 坎: 寅辰午 / 申戌子  (stem 戊)
# 艮: 辰午申 / 戌子寅  (stem 丙)
# 震: 子寅辰 / 午申戌  (stem 庚)
# 巽: 丑亥酉 / 未巳卯  (stem 辛)  — 阴卦逆排
# 离: 卯丑亥 / 酉未巳  (stem 己)
# 坤: 未巳卯 / 丑亥酉  (stem 乙, 癸)
# 兑: 巳卯丑 / 亥酉未  (stem 丁)
# Stems: lower / upper stems differ per palace (内甲, 外甲).
# --------------------------------------------------------------------------- #

NAJIA_TABLE: dict[str, dict] = {
    "乾": {"lower_stem": "甲", "upper_stem": "壬",
            "lower_branches": ["子", "寅", "辰"],
            "upper_branches": ["午", "申", "戌"]},
    "坎": {"lower_stem": "戊", "upper_stem": "戊",
            "lower_branches": ["寅", "辰", "午"],
            "upper_branches": ["申", "戌", "子"]},
    "艮": {"lower_stem": "丙", "upper_stem": "丙",
            "lower_branches": ["辰", "午", "申"],
            "upper_branches": ["戌", "子", "寅"]},
    "震": {"lower_stem": "庚", "upper_stem": "庚",
            "lower_branches": ["子", "寅", "辰"],
            "upper_branches": ["午", "申", "戌"]},
    "巽": {"lower_stem": "辛", "upper_stem": "辛",
            "lower_branches": ["丑", "亥", "酉"],
            "upper_branches": ["未", "巳", "卯"]},
    "离": {"lower_stem": "己", "upper_stem": "己",
            "lower_branches": ["卯", "丑", "亥"],
            "upper_branches": ["酉", "未", "巳"]},
    "坤": {"lower_stem": "乙", "upper_stem": "癸",
            "lower_branches": ["未", "巳", "卯"],
            "upper_branches": ["丑", "亥", "酉"]},
    "兑": {"lower_stem": "丁", "upper_stem": "丁",
            "lower_branches": ["巳", "卯", "丑"],
            "upper_branches": ["亥", "酉", "未"]},
}


def najia(upper_trigram: str, lower_trigram: str) -> list[dict]:
    """Return 6 entries bottom-to-top with stem+branch+wuxing each."""
    lt = NAJIA_TABLE[lower_trigram]
    ut = NAJIA_TABLE[upper_trigram]
    out: list[dict] = []
    for i in range(3):
        out.append({
            "position": i + 1,
            "stem": lt["lower_stem"],
            "branch": lt["lower_branches"][i],
            "wuxing": DIZHI_WUXING[lt["lower_branches"][i]],
        })
    for i in range(3):
        out.append({
            "position": 4 + i,
            "stem": ut["upper_stem"],
            "branch": ut["upper_branches"][i],
            "wuxing": DIZHI_WUXING[ut["upper_branches"][i]],
        })
    return out


# --------------------------------------------------------------------------- #
# 六亲 — relative to 本宫 (palace) 五行
# Palace 五行 from BAGUA[name]["wuxing"]; line 五行 from najia branch.
# Rules (相对宫五行):
#   同我:   兄弟
#   生我:   父母
#   我生:   子孙
#   克我:   官鬼
#   我克:   妻财
# --------------------------------------------------------------------------- #

def liu_qin(palace_wx: str, line_wx: str) -> str:
    if palace_wx == line_wx:
        return "兄弟"
    if WUXING_GEN.get(line_wx) == palace_wx:
        return "父母"  # line 五行 generates palace 五行 (生我)
    if WUXING_GEN.get(palace_wx) == line_wx:
        return "子孙"  # palace generates line (我生)
    if WUXING_KE.get(line_wx) == palace_wx:
        return "官鬼"  # line controls palace (克我)
    if WUXING_KE.get(palace_wx) == line_wx:
        return "妻财"
    return "未知"


# --------------------------------------------------------------------------- #
# 六神 — by 起卦日干
# 甲乙起青龙, 丙丁起朱雀, 戊起勾陈, 己起腾蛇, 庚辛起白虎, 壬癸起玄武
# Then assign in order from line 1 to line 6.
# --------------------------------------------------------------------------- #

LIU_SHEN_ORDER = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]

LIU_SHEN_START: dict[str, str] = {
    "甲": "青龙", "乙": "青龙",
    "丙": "朱雀", "丁": "朱雀",
    "戊": "勾陈",
    "己": "腾蛇",
    "庚": "白虎", "辛": "白虎",
    "壬": "玄武", "癸": "玄武",
}


def liu_shen(day_stem: str) -> list[str]:
    start_name = LIU_SHEN_START.get(day_stem, "青龙")
    start = LIU_SHEN_ORDER.index(start_name)
    return [LIU_SHEN_ORDER[(start + i) % 6] for i in range(6)]


# --------------------------------------------------------------------------- #
# 旺相休囚 — relative to season represented by 月支
# Season 五行 -> 当令五行:
#   春 (寅卯辰): 木
#   夏 (巳午未): 火
#   秋 (申酉戌): 金
#   冬 (亥子丑): 水
#   四季末 (辰戌丑未): 土 also strong (土王四季)
# State:
#   当令五行 = 旺
#   当令所生 = 相
#   生当令者 = 休
#   克当令者 = 囚
#   当令所克 = 死
# --------------------------------------------------------------------------- #

def month_branch_season_wuxing(month_branch: str) -> str:
    return {
        "寅": "木", "卯": "木", "辰": "土",
        "巳": "火", "午": "火", "未": "土",
        "申": "金", "酉": "金", "戌": "土",
        "亥": "水", "子": "水", "丑": "土",
    }[month_branch]


def wang_xiang(line_wx: str, season_wx: str) -> str:
    if line_wx == season_wx:
        return "旺"
    if WUXING_GEN.get(season_wx) == line_wx:
        return "相"
    if WUXING_GEN.get(line_wx) == season_wx:
        return "休"
    if WUXING_KE.get(line_wx) == season_wx:
        return "囚"
    if WUXING_KE.get(season_wx) == line_wx:
        return "死"
    return "?"


# --------------------------------------------------------------------------- #
# 月破 / 日破 / 旬空
# 月破: line_branch 与 月建 相冲 (六冲)
# 日破: line_branch 与 日辰 相冲
# 六冲对: 子午 丑未 寅申 卯酉 辰戌 巳亥
# 旬空: lookup by 日干支 旬首
# --------------------------------------------------------------------------- #

LIU_CHONG_PAIRS = {
    "子": "午", "午": "子", "丑": "未", "未": "丑",
    "寅": "申", "申": "寅", "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}


def xun_kong(day_stem: str, day_branch: str) -> list[str]:
    ts = TIANGAN.index(day_stem)
    db = DIZHI.index(day_branch)
    diff = (db - ts) % 12
    table = {
        0:  ["戌", "亥"],
        10: ["申", "酉"],
        8:  ["午", "未"],
        6:  ["辰", "巳"],
        4:  ["寅", "卯"],
        2:  ["子", "丑"],
    }
    return table.get(diff, [])


# --------------------------------------------------------------------------- #
# Dress full chart
# --------------------------------------------------------------------------- #

def dress_chart(lines: list[int], day_stem: str, day_branch: str,
                month_branch: str) -> dict:
    upper_bin, lower_bin = lines_to_trigrams(lines)
    hex_num, hex_name = hex_lookup_by_trigrams(upper_bin, lower_bin)
    upper_tri = BINARY_TO_TRIGRAM[upper_bin]
    lower_tri = BINARY_TO_TRIGRAM[lower_bin]
    palace, role = find_palace(hex_num)
    palace_wx = BAGUA[palace[:-1]]["wuxing"] if palace else None
    shi = shi_yao_position(role) if role else 0
    ying = ying_yao_position(shi) if shi else 0

    nj = najia(upper_tri, lower_tri)
    ls = liu_shen(day_stem)
    season_wx = month_branch_season_wuxing(month_branch)
    kong = xun_kong(day_stem, day_branch)

    dressed_lines: list[dict] = []
    for i, line_v in enumerate(lines):
        b = nj[i]["branch"]
        wx = nj[i]["wuxing"]
        markers: list[str] = []
        if LIU_CHONG_PAIRS.get(b) == month_branch:
            markers.append("月破")
        if LIU_CHONG_PAIRS.get(b) == day_branch:
            markers.append("日破")
        if b in kong:
            markers.append("旬空")
        if line_v in (6, 9):
            markers.append("动爻")

        entry = {
            "position": i + 1,
            "value": line_v,
            "visual": line_visual(line_v),
            "stem": nj[i]["stem"],
            "branch": b,
            "wuxing": wx,
            "liu_qin": liu_qin(palace_wx, wx) if palace_wx else None,
            "liu_shen": ls[i],
            "state": wang_xiang(wx, season_wx),
            "is_shi": (i + 1 == shi),
            "is_ying": (i + 1 == ying),
            "markers": markers,
        }
        dressed_lines.append(entry)

    return {
        "hex_number": hex_num,
        "hex_name": hex_name,
        "upper_trigram": upper_tri,
        "lower_trigram": lower_tri,
        "palace": palace,
        "palace_wuxing": palace_wx,
        "palace_role": role,
        "shi_position": shi,
        "ying_position": ying,
        "lines": dressed_lines,
    }


# --------------------------------------------------------------------------- #
# 用神 hint — by question keywords
# --------------------------------------------------------------------------- #

QUESTION_KEYWORDS = {
    "感情": "妻财 (问情, 男以妻财为用神)",
    "婚姻": "妻财 / 官鬼 (男看妻财, 女看官鬼)",
    "财运": "妻财",
    "事业": "官鬼",
    "工作": "官鬼",
    "考试": "父母 / 官鬼",
    "学业": "父母",
    "求名": "官鬼",
    "求子": "子孙",
    "健康": "子孙 (主医药)",
    "病": "官鬼 (病情) / 子孙 (医药)",
    "出行": "父母 (车船) / 兄弟 (同伴)",
    "求财": "妻财",
    "诉讼": "官鬼",
}


def yongshen_hint(question: Optional[str]) -> Optional[str]:
    if not question:
        return None
    for k, v in QUESTION_KEYWORDS.items():
        if k in question:
            return f"参考用神: {v}"
    return None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="六爻起卦 (装六亲/六神/纳甲/世应)")
    sub = p.add_subparsers(dest="method", required=True)

    pc = sub.add_parser("coins", help="三枚硬币 6 次")
    pc.add_argument("--seed", type=int, default=None)
    pc.add_argument("--date", type=str, default=None,
                    help="起卦日 YYYY-MM-DD (默认今日)")
    pc.add_argument("--time", type=str, default=None,
                    help="起卦时 HH:MM (默认现在)")
    pc.add_argument("--question", type=str, default=None,
                    help="所问之事 (用于推断用神)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    require_lunar()
    from lunar_python import Solar  # type: ignore

    # Determine cast date/time
    now = datetime.now()
    y, m, d = now.year, now.month, now.day
    h, mi = now.hour, now.minute
    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
            y, m, d = dt.year, dt.month, dt.day
        except ValueError as e:
            json_print({"error": "invalid_date", "message": str(e)})
            return 1
    if args.time:
        try:
            ht, mit = map(int, args.time.split(":"))
            h, mi = ht, mit
        except Exception:
            json_print({"error": "invalid_time", "expected": "HH:MM"})
            return 1

    solar = Solar.fromYmdHms(y, m, d, h, mi, 0)
    lunar = solar.getLunar()
    day_stem = lunar.getDayGan()
    day_branch = lunar.getDayZhi()
    month_branch = lunar.getMonthZhi()

    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    lines = cast_coins(rng)

    main_chart = dress_chart(lines, day_stem, day_branch, month_branch)

    actives = active_lines(lines)
    changed_chart: Optional[dict] = None
    if actives:
        new_lines = changed_lines(lines)
        changed_chart = dress_chart(new_lines, day_stem, day_branch, month_branch)

    nuclear_chart = dress_chart(nuclear_lines(lines), day_stem, day_branch, month_branch)

    assets = load_hex_assets()
    main_text = assets.get(main_chart["hex_number"], {})
    active_line_texts = []
    for pos in actives:
        lines_text = main_text.get("lines", [])
        active_line_texts.append({
            "position": pos,
            "text": lines_text[pos - 1] if pos - 1 < len(lines_text) else "(暂无)",
        })

    out = {
        "method": "coins",
        "question": args.question,
        "yongshen_hint": yongshen_hint(args.question),
        "cast_time": {
            "solar": f"{y:04d}-{m:02d}-{d:02d} {h:02d}:{mi:02d}",
            "lunar_date": lunar.getDayInChinese(),
            "year_ganzhi": lunar.getYearInGanZhi(),
            "month_ganzhi": lunar.getMonthInGanZhi(),
            "day_ganzhi": lunar.getDayInGanZhi(),
            "hour_ganzhi": lunar.getTimeInGanZhi(),
            "day_stem": day_stem,
            "day_branch": day_branch,
            "month_branch": month_branch,
        },
        "raw_lines": lines,
        "main_chart": main_chart,
        "changed_chart": changed_chart,
        "nuclear_chart": nuclear_chart,
        "active_lines": actives,
        "main_judgment": main_text.get("judgment", "(暂无)"),
        "main_image": main_text.get("image", "(暂无)"),
        "active_line_text": active_line_texts,
    }
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
