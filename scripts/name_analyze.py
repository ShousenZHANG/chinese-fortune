"""Chinese name analysis (五格剖象 / 81 数理).

Computes 天格, 人格, 地格, 外格, 总格 from 康熙笔画 of each character,
plus 三才配置 (天人地 五行 sequence). Legacy numerology labels are marked
as unverified diagnostic categories; no event predictions or naming advice.

Usage:
    python name_analyze.py --name 王小明

笔画 lookup: uses ``assets/name_bihua.json`` if present; otherwise falls back
to a small built-in stroke table (with a stderr warning).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from utils import (
    WUXING_GEN,
    WUXING_KE,
    ensure_utf8_stdio,
    error_envelope,
    json_print,
    ok_envelope,
    warn,
)

# --------------------------------------------------------------------------- #
# 81 数理 compatibility labels; no verified edition/source for this table.
# These categories are not personal judgments or classical evidence.
# --------------------------------------------------------------------------- #

SHULI_81: dict[int, dict] = {
    1:  {"luck": "大吉"},
    2:  {"luck": "凶"},
    3:  {"luck": "大吉"},
    4:  {"luck": "凶"},
    5:  {"luck": "大吉"},
    6:  {"luck": "大吉"},
    7:  {"luck": "吉"},
    8:  {"luck": "吉"},
    9:  {"luck": "凶"},
    10: {"luck": "凶"},
    11: {"luck": "大吉"},
    12: {"luck": "凶"},
    13: {"luck": "大吉"},
    14: {"luck": "凶"},
    15: {"luck": "大吉"},
    16: {"luck": "大吉"},
    17: {"luck": "吉"},
    18: {"luck": "大吉"},
    19: {"luck": "凶"},
    20: {"luck": "凶"},
    21: {"luck": "大吉"},
    22: {"luck": "凶"},
    23: {"luck": "大吉"},
    24: {"luck": "大吉"},
    25: {"luck": "吉"},
    26: {"luck": "凶带吉"},
    27: {"luck": "凶带吉"},
    28: {"luck": "凶"},
    29: {"luck": "吉"},
    30: {"luck": "凶带吉"},
    31: {"luck": "大吉"},
    32: {"luck": "大吉"},
    33: {"luck": "大吉"},
    34: {"luck": "大凶"},
    35: {"luck": "吉"},
    36: {"luck": "凶带吉"},
    37: {"luck": "大吉"},
    38: {"luck": "凶带吉"},
    39: {"luck": "大吉"},
    40: {"luck": "凶带吉"},
    41: {"luck": "大吉"},
    42: {"luck": "凶带吉"},
    43: {"luck": "凶带吉"},
    44: {"luck": "大凶"},
    45: {"luck": "大吉"},
    46: {"luck": "凶"},
    47: {"luck": "大吉"},
    48: {"luck": "大吉"},
    49: {"luck": "凶"},
    50: {"luck": "凶带吉"},
    51: {"luck": "凶带吉"},
    52: {"luck": "大吉"},
    53: {"luck": "凶"},
    54: {"luck": "大凶"},
    55: {"luck": "凶带吉"},
    56: {"luck": "凶"},
    57: {"luck": "吉"},
    58: {"luck": "凶带吉"},
    59: {"luck": "凶"},
    60: {"luck": "大凶"},
    61: {"luck": "大吉"},
    62: {"luck": "凶"},
    63: {"luck": "大吉"},
    64: {"luck": "大凶"},
    65: {"luck": "大吉"},
    66: {"luck": "凶"},
    67: {"luck": "大吉"},
    68: {"luck": "大吉"},
    69: {"luck": "大凶"},
    70: {"luck": "大凶"},
    71: {"luck": "凶带吉"},
    72: {"luck": "凶"},
    73: {"luck": "吉"},
    74: {"luck": "大凶"},
    75: {"luck": "凶带吉"},
    76: {"luck": "大凶"},
    77: {"luck": "凶带吉"},
    78: {"luck": "凶带吉"},
    79: {"luck": "凶"},
    80: {"luck": "大凶"},
    81: {"luck": "大吉"},
}


# --------------------------------------------------------------------------- #
# 三才 五行 mapping — last digit of each 格 -> 五行
# 1,2 木; 3,4 火; 5,6 土; 7,8 金; 9,0 水
# --------------------------------------------------------------------------- #

LAST_DIGIT_WUXING: dict[int, str] = {
    1: "木", 2: "木", 3: "火", 4: "火",
    5: "土", 6: "土", 7: "金", 8: "金",
    9: "水", 0: "水",
}


def shuli_lookup(n: int) -> dict:
    n = ((n - 1) % 81) + 1 if n > 0 else 1
    return {
        **SHULI_81.get(n, {"luck": "未知"}),
        "label_kind": "legacy_numerology_category",
        "source_status": "unverified",
        "personal_verdict": None,
    }


def wuxing_for(n: int) -> str:
    return LAST_DIGIT_WUXING[n % 10]


# --------------------------------------------------------------------------- #
# 三才吉凶 — based on the 五行 combination of 天 / 人 / 地.
# Simplified version: scoring by 相生/相克 relationships.
# --------------------------------------------------------------------------- #


def sancai_luck(tian_wx: str, ren_wx: str, di_wx: str) -> str:
    score = 0
    # 天 -> 人
    if tian_wx == ren_wx:
        score += 1
    elif WUXING_GEN.get(tian_wx) == ren_wx:
        score += 2
    elif WUXING_KE.get(tian_wx) == ren_wx:
        score -= 2
    # 人 -> 地
    if ren_wx == di_wx:
        score += 1
    elif WUXING_GEN.get(ren_wx) == di_wx:
        score += 2
    elif WUXING_KE.get(ren_wx) == di_wx:
        score -= 2
    # 天 -> 地 (次要)
    if WUXING_KE.get(tian_wx) == di_wx:
        score -= 1
    elif WUXING_GEN.get(tian_wx) == di_wx:
        score += 1

    if score >= 3:
        return "大吉"
    if score >= 1:
        return "吉"
    if score == 0:
        return "中"
    if score >= -2:
        return "凶"
    return "大凶"


# --------------------------------------------------------------------------- #
# 笔画 lookup
# --------------------------------------------------------------------------- #

# Built-in fallback (common chars only). Production should load assets file.
FALLBACK_BIHUA: dict[str, int] = {
    "王": 4, "李": 7, "张": 11, "刘": 15, "陈": 16, "杨": 13, "黄": 12,
    "赵": 14, "周": 8, "吴": 7, "徐": 10, "孙": 10, "胡": 11, "朱": 6,
    "高": 10, "林": 8, "何": 7, "郭": 15, "马": 10, "罗": 20, "梁": 11,
    "宋": 7, "郑": 19, "谢": 17, "韩": 17, "唐": 10, "冯": 12, "于": 3,
    "董": 15, "萧": 18, "程": 12, "曹": 11, "袁": 10, "邓": 19, "许": 11,
    "傅": 12, "沈": 8, "曾": 12, "彭": 12, "吕": 7, "苏": 22, "卢": 16,
    "蒋": 17, "蔡": 17, "贾": 13, "丁": 2, "魏": 18, "薛": 19, "叶": 15,
    "阎": 16, "余": 7, "潘": 16, "杜": 7, "戴": 18, "夏": 10, "钟": 17,
    "汪": 8, "田": 5, "任": 6, "姜": 9, "范": 11, "方": 4, "石": 5,
    "姚": 9, "谭": 19, "廖": 14, "邹": 13, "熊": 14, "金": 8, "陆": 16,
    "郝": 14, "孔": 4, "白": 5, "崔": 11, "康": 11, "毛": 4, "邱": 12,
    "秦": 10, "江": 7, "史": 5, "顾": 21, "侯": 9, "邵": 12, "孟": 8,
    "龙": 16, "万": 15, "段": 9, "雷": 13, "钱": 16, "汤": 13, "尹": 4,
    "黎": 15, "易": 8, "常": 11, "武": 8, "乔": 12, "贺": 12, "赖": 16,
    "龚": 22, "文": 4,
    "小": 3, "明": 8, "华": 14, "强": 12, "丽": 19, "刚": 10, "敏": 11,
    "静": 16, "勇": 9, "艳": 24, "杰": 12, "娟": 10, "涛": 18, "超": 12,
    "霞": 17, "丹": 4, "雨": 8, "晨": 11, "宇": 6, "轩": 10, "梓": 11,
    "涵": 12, "浩": 11, "然": 12, "瑞": 14, "鑫": 24, "雪": 11, "蕾": 19,
    "莹": 15, "燕": 16, "梅": 11, "兰": 23, "竹": 6, "菊": 14, "松": 18,
    "柏": 9, "鹏": 19, "云": 12, "凯": 12, "辉": 15, "海": 11, "山": 3,
    "川": 3, "河": 9, "天": 4, "地": 6, "和": 8, "平": 5, "安": 6,
    "宁": 14, "福": 14, "寿": 14, "禄": 13, "财": 11, "兴": 16,
    "旺": 8, "成": 7, "功": 5, "立": 5, "建": 9, "国": 11, "家": 10,
    "兵": 7, "军": 9, "民": 5, "新": 13, "永": 5, "良": 7, "学": 16,
    "诗": 13, "婷": 12, "晓": 16, "倩": 10, "颖": 16,
    "妍": 7, "悦": 11, "瑶": 15, "雅": 12, "薇": 19, "婕": 11, "婉": 11,
    "嘉": 14, "怡": 9, "妙": 7, "佳": 8, "嫣": 14, "甜": 11,
}


def load_bihua_table() -> dict[str, int]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "assets", "name_bihua.json"),
        os.path.join(here, "assets", "name_bihua.json"),
    ]
    # Fallback is the base layer (common given-name chars); the asset overrides
    # and extends it. Merging — not replacing — guarantees high-frequency chars
    # like 涵/浩/然 stay covered even if the asset omits them.
    table: dict[str, int] = dict(FALLBACK_BIHUA)
    asset = next((p for p in candidates if os.path.exists(p)), None)
    if asset:
        try:
            with open(asset, "r", encoding="utf-8") as f:
                data = json.load(f)
            chars = data.get("chars", data) if isinstance(data, dict) else data
            if isinstance(chars, dict):
                table.update({k: int(v) for k, v in chars.items() if len(k) == 1})
                return table
        except Exception as e:
            warn(f"failed to load name_bihua.json: {e}")
    warn("使用内置简表笔画 (覆盖有限); 可补 assets/name_bihua.json 完整康熙笔画表")
    return table


def stroke_count(ch: str, table: dict[str, int]) -> int | None:
    return table.get(ch)


# --------------------------------------------------------------------------- #
# 五格 calculations
# --------------------------------------------------------------------------- #

def five_grids(surname_strokes: list[int], given_strokes: list[int]) -> dict:
    """Standard rules (compound surname / single given supported)::

        天格 = 复姓: sum(surname) ; 单姓: surname + 1
        人格 = 姓最后一字 + 名第一字
        地格 = 单名: 名 + 1 ; 双名: sum(given)
        外格 = (总格 - 人格) + 1  if not 单姓单名 else 单姓单名特殊外格 = 2 (即 1+1)
        总格 = sum(all)
    """
    is_compound_surname = len(surname_strokes) >= 2
    is_single_given = len(given_strokes) == 1

    if is_compound_surname:
        tian = sum(surname_strokes)
    else:
        tian = surname_strokes[0] + 1

    ren = surname_strokes[-1] + given_strokes[0]

    if is_single_given:
        di = given_strokes[0] + 1
    else:
        di = sum(given_strokes)

    total = sum(surname_strokes) + sum(given_strokes)

    if not is_compound_surname and is_single_given:
        wai = 2  # 单姓单名 -> 外格固定 2
    else:
        wai = (total - ren) + 1

    def grid_info(n: int) -> dict:
        return {
            "number": n,
            "modulo_81": ((n - 1) % 81) + 1 if n > 0 else 1,
            "wuxing": wuxing_for(n),
            **shuli_lookup(n),
        }

    return {
        "tian_ge": grid_info(tian),
        "ren_ge": grid_info(ren),
        "di_ge": grid_info(di),
        "wai_ge": grid_info(wai),
        "zong_ge": grid_info(total),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok input name characters missing_in_table reliable five_grids
  san_cai summary

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="姓名五格剖象 (康熙笔画 + 81 数理)",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--name", type=str, required=True,
                   help="完整中文姓名, 如 王小明 / 欧阳子轩")
    p.add_argument("--compound-surname", action="store_true",
                   help="若姓为复姓, 加上此标志")
    p.add_argument("--strict", action="store_true",
                   help="严格模式: 任一字缺笔画即报错退出, 不用默认值蒙混")
    return p


def _is_han(ch: str) -> bool:
    """CJK 统一表意文字 (含扩展 A/B 与兼容区)。间隔号、拉丁字母、空格皆非汉字。"""
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF      # 基本区
        or 0x3400 <= cp <= 0x4DBF   # 扩展 A
        or 0x20000 <= cp <= 0x2A6DF  # 扩展 B
        or 0xF900 <= cp <= 0xFAFF   # 兼容表意文字
    )


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    name = args.name.strip()
    if not name or len(name) < 2:
        json_print(error_envelope("name", "invalid_name", "姓名至少两个字",
                                  input=name))
        return 1

    # 五格数理只对汉字成立: 它数的是康熙笔画。从前 --name "John Smith" 返回
    # ok:true, 把 10 个拉丁字母**连同那个空格**逐个按默认 8 画计, 输出
    # 总格 80(大凶)「辛苦无功, 事与愿违」—— 一个凭空生成的凶断。
    # 这不只是英文用户的问题: "阿依古丽·买买提" 里的间隔号同样被当成 8 画字
    # 计进 地格/外格/总格。SKILL.md 的 description 把 naming 列为英文触发词。
    non_han = [c for c in name if not _is_han(c)]
    if non_han:
        json_print(error_envelope(
            "name", "non_han_characters",
            "五格数理按康熙笔画计, 只适用于汉字姓名; "
            f"以下字符无法计笔画: {''.join(dict.fromkeys(non_han))}",
            input=name,
            non_han_characters=sorted(set(non_han)),
            hint="非汉字姓名请改用汉字译名, 或改用其他方法 (如生肖/星座)。",
        ))
        return 1

    table = load_bihua_table()

    # Split: assume 1-char surname unless --compound-surname
    if args.compound_surname:
        if len(name) < 3:
            json_print(error_envelope('name', "compound_surname_needs_3plus", '输入无效'))
            return 1
        surname_chars = list(name[:2])
        given_chars = list(name[2:])
    else:
        surname_chars = [name[0]]
        given_chars = list(name[1:])

    chars_info: list[dict] = []
    surname_strokes: list[int] = []
    given_strokes: list[int] = []
    missing: list[str] = []

    for ch in surname_chars:
        s = stroke_count(ch, table)
        if s is None:
            missing.append(ch)
            s = 8  # safe default
        chars_info.append({"char": ch, "role": "surname", "strokes": s})
        surname_strokes.append(s)

    for ch in given_chars:
        s = stroke_count(ch, table)
        if s is None:
            missing.append(ch)
            s = 8
        chars_info.append({"char": ch, "role": "given", "strokes": s})
        given_strokes.append(s)

    if missing and getattr(args, "strict", False):
        json_print(error_envelope('name', "missing_strokes", f"以下字不在康熙笔画表中, 严格模式拒绝估算: {missing}", missing_in_table=missing, input=vars(args)))
        return 1

    grids = five_grids(surname_strokes, given_strokes)

    sancai = {
        "tian_wuxing": grids["tian_ge"]["wuxing"],
        "ren_wuxing": grids["ren_ge"]["wuxing"],
        "di_wuxing": grids["di_ge"]["wuxing"],
    }
    sancai["combo"] = f'{sancai["tian_wuxing"]}-{sancai["ren_wuxing"]}-{sancai["di_wuxing"]}'
    sancai["luck"] = sancai_luck(
        sancai["tian_wuxing"], sancai["ren_wuxing"], sancai["di_wuxing"],
    )
    sancai["label_kind"] = "heuristic_relation_category"
    sancai["source_status"] = "unverified"

    summary_parts = [
        f"姓名 {name}",
        f"天格 {grids['tian_ge']['number']}",
        f"人格 {grids['ren_ge']['number']}",
        f"地格 {grids['di_ge']['number']}",
        f"外格 {grids['wai_ge']['number']}",
        f"总格 {grids['zong_ge']['number']}",
        f"三才 {sancai['combo']}",
    ]

    out = {
        "ok": True,
        "input": vars(args),
        "name": name,
        "characters": chars_info,
        "missing_in_table": missing,
        "reliable": not missing,
        "five_grids": grids,
        "san_cai": sancai,
        "source": {
            "system": "五格剖象法 (熊崎式)",
            "origin": "近代日本 熊崎健翁 所创, 20 世纪传入华人地区",
            "classical_basis": "无 —— 非中土古法, 《三命通会》等古籍均无此说",
            "disputed": True,
            "caveat": ("81 数理标签仅保留为旧表分类, 本表出处尚未核验, 不可作命定之论; "
                       "已移除事件断语, 不据此建议取名或改名。"),
        },
        "boundary": ("本工具只算五格数字与三才配置; 音韵、字义、与生辰八字的补益 "
                     "皆不在内。取名请综合考量, 勿单凭数理。"),
        "summary": "; ".join(summary_parts),
    }
    if missing:
        out["warning"] = (
            f"以下字未在康熙笔画表中, 用默认值 8 估算, 五格数字待核: {missing}。"
            f"请补 assets/name_bihua.json 或用 --strict 拒绝估算。"
        )

    json_print(ok_envelope("name", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
