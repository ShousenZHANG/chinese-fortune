"""Chinese zodiac (生肖) calendar labels and branch relationships.

Subcommands:
    info     --zodiac 鼠
    compat   --a 鼠 --b 牛
    year     --year 1990
    taisui   --year 2026
"""

from __future__ import annotations

import argparse
import sys

from utils import (
    DIZHI_ZODIAC,
    ZODIAC_TO_DIZHI,
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    ok_envelope,
    require_lunar,
    validate_birth_input,
)

ZODIAC_DATA: dict[str, dict] = {
    "鼠": {
        "wuxing": "水", "yinyang": "阳",
    },
    "牛": {
        "wuxing": "土", "yinyang": "阴",
    },
    "虎": {
        "wuxing": "木", "yinyang": "阳",
    },
    "兔": {
        "wuxing": "木", "yinyang": "阴",
    },
    "龙": {
        "wuxing": "土", "yinyang": "阳",
    },
    "蛇": {
        "wuxing": "火", "yinyang": "阴",
    },
    "马": {
        "wuxing": "火", "yinyang": "阳",
    },
    "羊": {
        "wuxing": "土", "yinyang": "阴",
    },
    "猴": {
        "wuxing": "金", "yinyang": "阳",
    },
    "鸡": {
        "wuxing": "金", "yinyang": "阴",
    },
    "狗": {
        "wuxing": "土", "yinyang": "阳",
    },
    "猪": {
        "wuxing": "水", "yinyang": "阴",
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
    for group in SAN_HE_GROUPS:
        # 三合需两个 *不同* 地支同组; 同生肖(da==db)是比和/自刑, 非三合。
        if da != db and da in group and db in group:
            relations.append("三合")
            score += 3
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

    return {
        "a": a, "b": b,
        "branches": [da, db],
        "relations": relations,
        "score": score,
        "score_kind": "legacy_heuristic_relation_index",
        "score_calibrated": False,
        "verdict": None,
        "boundary": "score 仅为兼容旧程序保留的自设关系权重, 不代表婚恋相配度或个人结论。",
        "summary": f"{a}与{b}: 地支 {da}、{db} 的表中关系为 {' / '.join(relations)}",
    }


# --------------------------------------------------------------------------- #
# Year -> zodiac
# --------------------------------------------------------------------------- #

def zodiac_of_year(year: int) -> dict:
    """一年的生肖, 外加两种换岁法的分界日。

    从前这里探两个硬编码日期 (2月5日 / 3月1日) 再对**同一个** getYearShengXiao()
    取值。getYearShengXiao() 按农历年 (正月初一) 换岁, 不按立春; 而春节约有一半
    年份晚于 2月5日, 于是 strict_bazi_zodiac 在 1950-2050 的 49/101 年返回上一年
    的生肖 —— 恰恰是它自称遵循的立春法唯一排除掉的那个答案 (2026 给「蛇」, 实为
    丙午马年)。同文件的 taisui 子命令对 2026 给「马」, 两条命令自相矛盾。

    换岁法之争只对**正月/二月出生的人**有意义: 一整年的生肖标签在两种算法下必然
    相同 (两个分界都落在 1-2 月, 年中取值必在同一区间内)。所以这里改为年中取值,
    两个字段都由各自的正确 API 得出, 并把真正有信息量的东西 —— 两个分界日 ——
    直接输出, 让调用方能判断一个 1-2 月的生日落在哪一侧。
    """
    require_lunar()
    from lunar_python import Lunar, Solar  # type: ignore
    mid = Solar.fromYmdHms(year, 6, 1, 12, 0, 0).getLunar()
    li_chun = mid.getJieQiTable()["立春"].toYmd()
    lunar_new_year = Lunar.fromYmd(year, 1, 1).getSolar().toYmd()
    return {
        "year": year,
        "zodiac": mid.getYearShengXiaoByLiChun(),
        "strict_bazi_zodiac": mid.getYearShengXiaoByLiChun(),
        "folk_zodiac": mid.getYearShengXiao(),
        "li_chun": li_chun,
        "lunar_new_year": lunar_new_year,
        "note": (
            f"八字以立春换岁 ({li_chun}), 民俗多以正月初一换岁 ({lunar_new_year})。"
            "整年标签两法一致; 仅当出生日落在这两个日期之间时, 两法才给出不同生肖 —— "
            "此时以出生日期查 bazi_calc.py 的年柱为准。"
        ),
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

    def to_zodiac(b: str | None) -> str | None:
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
        "note": "仅列该年地支与各生肖的表中关系, 未据此推断个人事件。",
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
    base["liuhe_sanhe"] = sorted(set(matches))
    base["liuchong"] = [DIZHI_ZODIAC[LIU_CHONG[da]]] if da in LIU_CHONG else []
    base["interpretation_status"] = "relations_only"
    return base


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  info: zodiac branch wuxing yinyang liuhe_sanhe liuchong interpretation_status
compat / year / taisui have their own keys.

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="生肖分类 / 地支关系 / 年界查询",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("info", help="生肖详情")
    p1.add_argument("--zodiac", type=str, required=True,
                    help="生肖中文名 (鼠/牛/虎/...)")

    p2 = sub.add_parser("compat", help="两生肖地支关系")
    p2.add_argument("--a", type=str, required=True)
    p2.add_argument("--b", type=str, required=True)

    p3 = sub.add_parser("year", help="某年的生肖 (立春 vs 春节)")
    p3.add_argument("--year", type=int, required=True)

    p4 = sub.add_parser("taisui", help="某年的犯/冲/刑/害/破太岁")
    p4.add_argument("--year", type=int, required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)

    if args.cmd == "info":
        result = info_zodiac(args.zodiac)
    elif args.cmd == "compat":
        result = compat(args.a, args.b)
    elif args.cmd in ("year", "taisui"):
        # 越界年份从前会一路走到 lunar_python 的历表外并崩栈, stdout 无 JSON,
        # stderr 是带绝对路径的 traceback —— 调用方读不出发生了什么。
        err = validate_birth_input(args.year)
        if err:
            json_print(error_envelope("zodiac", "invalid_input", err, input=vars(args)))
            return 1
        result = (zodiac_of_year if args.cmd == "year" else taisui_zodiacs)(args.year)
    else:
        json_print(error_envelope('zodiac', "unknown_cmd", '输入无效'))
        return 2

    if "error" in result:
        # 从前这里直接 json_print 一个裸 dict, 既没有 ok:false 也没有 tool/version,
        # 调用方要靠 "有没有 error 键" 特判本引擎。
        msg = result.pop("message", None) or result.pop("summary", None) or             f"无效输入: {result.get('input_a', '') or result.get('input', '')}"
        json_print(error_envelope("zodiac", result.pop("error"), msg, **result))
        return 1
    json_print(ok_envelope("zodiac", result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
