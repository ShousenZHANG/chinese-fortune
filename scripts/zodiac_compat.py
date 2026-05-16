"""Chinese zodiac (生肖) info and compatibility.

Subcommands:
    info     --zodiac 鼠
    compat   --a 鼠 --b 牛
    year     --year 1990
    taisui   --year 2026
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from utils import (
    DIZHI,
    DIZHI_ZODIAC,
    ZODIAC_TO_DIZHI,
    json_print,
    require_lunar,
)


ZODIAC_DATA: dict[str, dict] = {
    "鼠": {
        "wuxing": "水", "yinyang": "阳",
        "traits": "机敏灵活, 善察言观色, 适应力强",
        "strengths": ["聪明", "勤俭", "随机应变"],
        "weaknesses": ["疑心重", "见利忘义倾向", "格局易小"],
        "industries": ["金融", "信息", "商贸", "策划"],
    },
    "牛": {
        "wuxing": "土", "yinyang": "阴",
        "traits": "踏实勤恳, 坚毅守信, 不善变通",
        "strengths": ["勤奋", "稳重", "责任心"],
        "weaknesses": ["固执", "保守", "节奏慢"],
        "industries": ["农业", "建筑", "制造", "公共事业"],
    },
    "虎": {
        "wuxing": "木", "yinyang": "阳",
        "traits": "豪迈进取, 勇于开拓, 不畏强权",
        "strengths": ["果断", "魄力", "领导力"],
        "weaknesses": ["冲动", "刚愎", "易树敌"],
        "industries": ["军警", "管理", "体育", "创业"],
    },
    "兔": {
        "wuxing": "木", "yinyang": "阴",
        "traits": "温和谦逊, 细腻多虑, 重情感",
        "strengths": ["温雅", "审美", "外交"],
        "weaknesses": ["优柔", "敏感", "缺魄力"],
        "industries": ["艺术", "设计", "外交", "教育"],
    },
    "龙": {
        "wuxing": "土", "yinyang": "阳",
        "traits": "气宇轩昂, 抱负远大, 不甘平庸",
        "strengths": ["志向", "魅力", "创造力"],
        "weaknesses": ["自负", "好面子", "急躁"],
        "industries": ["政界", "影视", "高科技", "玄学"],
    },
    "蛇": {
        "wuxing": "火", "yinyang": "阴",
        "traits": "智谋深远, 神秘内敛, 沉静多虑",
        "strengths": ["智慧", "洞察", "深谋远虑"],
        "weaknesses": ["多疑", "嫉妒", "城府"],
        "industries": ["哲学", "宗教", "研究", "投资"],
    },
    "马": {
        "wuxing": "火", "yinyang": "阳",
        "traits": "热情奔放, 行动力强, 喜自由",
        "strengths": ["活力", "热情", "执行力"],
        "weaknesses": ["浮躁", "三分钟热度", "缺耐心"],
        "industries": ["销售", "运动", "运输", "媒体"],
    },
    "羊": {
        "wuxing": "土", "yinyang": "阴",
        "traits": "温柔善良, 包容退让, 重内在",
        "strengths": ["温和", "艺术", "同理心"],
        "weaknesses": ["懦弱", "依赖", "悲观"],
        "industries": ["艺术", "宗教", "教育", "服务"],
    },
    "猴": {
        "wuxing": "金", "yinyang": "阳",
        "traits": "机灵多变, 才思敏捷, 喜欢挑战",
        "strengths": ["聪慧", "幽默", "多才"],
        "weaknesses": ["浮夸", "投机", "缺定力"],
        "industries": ["科技", "传媒", "演艺", "金融"],
    },
    "鸡": {
        "wuxing": "金", "yinyang": "阴",
        "traits": "勤勉认真, 注重细节, 喜表现",
        "strengths": ["精细", "守时", "口才"],
        "weaknesses": ["挑剔", "好辩", "敏感"],
        "industries": ["管理", "财务", "法律", "传播"],
    },
    "狗": {
        "wuxing": "土", "yinyang": "阳",
        "traits": "忠诚正直, 讲义气, 富同情心",
        "strengths": ["忠诚", "正直", "责任"],
        "weaknesses": ["保守", "焦虑", "敏感"],
        "industries": ["公检法", "医护", "教育", "公益"],
    },
    "猪": {
        "wuxing": "水", "yinyang": "阴",
        "traits": "宽厚乐观, 真诚直率, 享乐主义",
        "strengths": ["宽厚", "乐观", "包容"],
        "weaknesses": ["懒散", "享乐", "易轻信"],
        "industries": ["餐饮", "休闲", "服务", "贸易"],
    },
}


# --------------------------------------------------------------------------- #
# 合冲刑害破
# --------------------------------------------------------------------------- #

# 六合: 子丑/寅亥/卯戌/辰酉/巳申/午未
LIU_HE = {
    "子": "丑", "丑": "子", "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳", "午": "未", "未": "午",
}

# 三合: 申子辰/亥卯未/寅午戌/巳酉丑
SAN_HE_GROUPS = [
    {"申", "子", "辰"},
    {"亥", "卯", "未"},
    {"寅", "午", "戌"},
    {"巳", "酉", "丑"},
]

# 六冲
LIU_CHONG = {
    "子": "午", "午": "子", "丑": "未", "未": "丑",
    "寅": "申", "申": "寅", "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}

# 相刑 (常见说法: 三刑+自刑)
# 寅刑巳, 巳刑申, 申刑寅 (无恩之刑)
# 丑刑戌, 戌刑未, 未刑丑 (恃势之刑)
# 子刑卯, 卯刑子 (无礼之刑)
# 自刑: 辰辰, 午午, 酉酉, 亥亥
XING_PAIRS = {
    ("寅", "巳"), ("巳", "申"), ("申", "寅"),
    ("丑", "戌"), ("戌", "未"), ("未", "丑"),
    ("子", "卯"), ("卯", "子"),
    ("辰", "辰"), ("午", "午"), ("酉", "酉"), ("亥", "亥"),
}

# 六害: 子未/丑午/寅巳/卯辰/申亥/酉戌
LIU_HAI = {
    "子": "未", "未": "子", "丑": "午", "午": "丑",
    "寅": "巳", "巳": "寅", "卯": "辰", "辰": "卯",
    "申": "亥", "亥": "申", "酉": "戌", "戌": "酉",
}

# 相破: 子酉/卯午/巳申/寅亥/辰丑/戌未
LIU_PO = {
    "子": "酉", "酉": "子", "卯": "午", "午": "卯",
    "巳": "申", "申": "巳", "寅": "亥", "亥": "寅",
    "辰": "丑", "丑": "辰", "戌": "未", "未": "戌",
}


def compat(a: str, b: str) -> dict:
    if a not in ZODIAC_TO_DIZHI or b not in ZODIAC_TO_DIZHI:
        return {"error": "unknown_zodiac", "input_a": a, "input_b": b}

    da, db = ZODIAC_TO_DIZHI[a], ZODIAC_TO_DIZHI[b]
    relations: list[str] = []
    score = 5  # baseline neutral

    if LIU_HE.get(da) == db:
        relations.append("六合")
        score += 4
    in_sanhe = False
    for group in SAN_HE_GROUPS:
        if da in group and db in group:
            relations.append("三合")
            score += 3
            in_sanhe = True
            break

    if LIU_CHONG.get(da) == db:
        relations.append("相冲")
        score -= 5
    if (da, db) in XING_PAIRS:
        relations.append("相刑")
        score -= 3
    if LIU_HAI.get(da) == db:
        relations.append("相害")
        score -= 2
    if LIU_PO.get(da) == db:
        relations.append("相破")
        score -= 2

    if not relations:
        relations = ["普通"]

    score = max(1, min(10, score))

    if score >= 9:
        verdict = "极佳, 天作之合"
    elif score >= 7:
        verdict = "良好, 相辅相成"
    elif score >= 5:
        verdict = "中等, 各有利弊"
    elif score >= 3:
        verdict = "偏差, 需要包容"
    else:
        verdict = "不合, 慎重对待"

    return {
        "a": a, "b": b,
        "branches": [da, db],
        "relations": relations,
        "score": score,
        "verdict": verdict,
        "summary": f"{a}与{b}: {' / '.join(relations)}, 评分 {score}/10 ({verdict})",
    }


# --------------------------------------------------------------------------- #
# Year -> zodiac
# --------------------------------------------------------------------------- #

def zodiac_of_year(year: int) -> dict:
    # Strict 八字 uses 立春. Folk usually uses 农历正月.
    require_lunar()
    from lunar_python import Solar  # type: ignore
    # Use 立春 boundary for strict; show both.
    s_lichun = Solar.fromYmdHms(year, 2, 5, 12, 0, 0).getLunar()
    s_lunar_newyear = Solar.fromYmdHms(year, 3, 1, 12, 0, 0).getLunar()
    return {
        "year": year,
        "strict_bazi_zodiac": s_lichun.getYearShengXiao(),
        "folk_zodiac": s_lunar_newyear.getYearShengXiao(),
        "note": "八字以立春换岁, 民俗多以正月初一换岁",
    }


# --------------------------------------------------------------------------- #
# 太岁
# --------------------------------------------------------------------------- #

def taisui_zodiacs(year: int) -> dict:
    require_lunar()
    from lunar_python import Solar  # type: ignore
    lunar = Solar.fromYmdHms(year, 6, 1, 12, 0, 0).getLunar()
    year_branch = lunar.getYearZhi()
    year_zodiac = DIZHI_ZODIAC[year_branch]

    chong = LIU_CHONG.get(year_branch)
    xing_list: list[str] = []
    for pair in XING_PAIRS:
        if pair[0] == year_branch:
            xing_list.append(pair[1])
        elif pair[1] == year_branch and pair[0] != year_branch:
            xing_list.append(pair[0])
    hai = LIU_HAI.get(year_branch)
    po = LIU_PO.get(year_branch)

    def to_zodiac(b: Optional[str]) -> Optional[str]:
        return DIZHI_ZODIAC.get(b) if b else None

    return {
        "year": year,
        "year_branch": year_branch,
        "year_zodiac": year_zodiac,
        "year_ganzhi": lunar.getYearInGanZhi(),
        "犯太岁": year_zodiac,                # 值太岁
        "冲太岁": to_zodiac(chong),
        "刑太岁": list({to_zodiac(b) for b in xing_list if b}),
        "害太岁": to_zodiac(hai),
        "破太岁": to_zodiac(po),
        "note": "犯/冲/刑/害/破太岁皆建议谨慎行事, 可拜太岁化解",
    }


# --------------------------------------------------------------------------- #
# Info subcommand
# --------------------------------------------------------------------------- #

def info_zodiac(z: str) -> dict:
    if z not in ZODIAC_DATA:
        return {"error": "unknown_zodiac", "input": z,
                "valid": list(ZODIAC_DATA.keys())}
    base = dict(ZODIAC_DATA[z])
    base["zodiac"] = z
    base["branch"] = ZODIAC_TO_DIZHI[z]

    # 相合/相冲 列表
    da = ZODIAC_TO_DIZHI[z]
    matches: list[str] = []
    if da in LIU_HE:
        matches.append(DIZHI_ZODIAC[LIU_HE[da]])
    for group in SAN_HE_GROUPS:
        if da in group:
            for b in group:
                if b != da:
                    matches.append(DIZHI_ZODIAC[b])
    base["best_match"] = sorted(set(matches))
    base["worst_match"] = [DIZHI_ZODIAC[LIU_CHONG[da]]] if da in LIU_CHONG else []
    return base


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="生肖 信息 / 相配 / 太岁 查询")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("info", help="生肖详情")
    p1.add_argument("--zodiac", type=str, required=True,
                    help="生肖中文名 (鼠/牛/虎/...)")

    p2 = sub.add_parser("compat", help="两生肖相配度")
    p2.add_argument("--a", type=str, required=True)
    p2.add_argument("--b", type=str, required=True)

    p3 = sub.add_parser("year", help="某年的生肖 (立春 vs 春节)")
    p3.add_argument("--year", type=int, required=True)

    p4 = sub.add_parser("taisui", help="某年的犯/冲/刑/害/破太岁")
    p4.add_argument("--year", type=int, required=True)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "info":
        json_print(info_zodiac(args.zodiac))
    elif args.cmd == "compat":
        json_print(compat(args.a, args.b))
    elif args.cmd == "year":
        json_print(zodiac_of_year(args.year))
    elif args.cmd == "taisui":
        json_print(taisui_zodiacs(args.year))
    else:
        json_print({"error": "unknown_cmd"})
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
