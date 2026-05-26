"""Chinese name analysis (五格剖象 / 81 数理).

Computes 天格, 人格, 地格, 外格, 总格 from 康熙笔画 of each character,
plus 三才配置 (天人地 五行 sequence) and 吉凶 per the standard 81 数理表.

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
from typing import Optional

from utils import json_print, warn


# --------------------------------------------------------------------------- #
# 81 数理 table — number -> {"luck": "大吉/吉/中/凶/大凶", "comment": "..."}
# Source: 传统姓名学 81 数理通用表.
# --------------------------------------------------------------------------- #

SHULI_81: dict[int, dict] = {
    1:  {"luck": "大吉", "comment": "宇宙开泰之数, 万物开始, 唯一独尊, 头领之运。"},
    2:  {"luck": "凶",   "comment": "动摇变化, 分离破败, 一身孤立无援之运。"},
    3:  {"luck": "大吉", "comment": "进取如意, 名利双收, 表现智慧, 立身处世顺利。"},
    4:  {"luck": "凶",   "comment": "万事休止, 不平不满, 难遂愿, 短命厄运之兆。"},
    5:  {"luck": "大吉", "comment": "福禄寿长, 阴阳和合, 完璧之象, 富贵荣华之数。"},
    6:  {"luck": "大吉", "comment": "天德地祥俱备, 福庆有余, 安稳吉祥之运。"},
    7:  {"luck": "吉",   "comment": "刚毅果断, 勇往直前, 排除万难, 必获成功。"},
    8:  {"luck": "吉",   "comment": "意志刚健, 持守坚毅, 富进取气慨, 易达目的。"},
    9:  {"luck": "凶",   "comment": "虽抱奇才, 反遭劫难, 大都为零落败兵之命。"},
    10: {"luck": "凶",   "comment": "万事终局, 充满损耗数, 多病弱苦, 暗淡无光。"},
    11: {"luck": "大吉", "comment": "草木更新, 万象逢春, 稳健着实, 顺风扬帆。"},
    12: {"luck": "凶",   "comment": "无理伸张, 虚弱之运, 易陷孤独, 灾难逢身。"},
    13: {"luck": "大吉", "comment": "天赋吉运, 善用智慧, 学艺多能, 富贵显达。"},
    14: {"luck": "凶",   "comment": "沦落天涯, 失意烦闷, 因缘薄弱, 家庭难圆。"},
    15: {"luck": "大吉", "comment": "福寿圆满之大吉数, 慈祥有德, 富贵荣华。"},
    16: {"luck": "大吉", "comment": "厚重镇守, 转败为胜, 能成大业, 名利双收。"},
    17: {"luck": "吉",   "comment": "突破万难, 刚柔兼备, 必能贯彻志望, 功成名就。"},
    18: {"luck": "大吉", "comment": "铁石心肠, 富贵繁荣, 排除万难, 终成大业。"},
    19: {"luck": "凶",   "comment": "风云蔽月, 辛苦重来, 内外不和, 障害重重。"},
    20: {"luck": "凶",   "comment": "智高志大, 历尽艰难, 进退维谷, 难免厄运。"},
    21: {"luck": "大吉", "comment": "明月光照, 万物形成, 独立权威, 享尽富贵。"},
    22: {"luck": "凶",   "comment": "秋草逢霜, 困苦愁闷, 中途易遭挫折, 不如意。"},
    23: {"luck": "大吉", "comment": "旭日东升, 旺盛, 发育, 隆昌, 名扬四海。"},
    24: {"luck": "大吉", "comment": "锦绣前程, 须靠自力, 多用智谋, 能奏大功。"},
    25: {"luck": "吉",   "comment": "天时地利, 仅欠人和, 待人接物, 须忍辱内省。"},
    26: {"luck": "凶带吉", "comment": "波澜起伏, 千变万化, 凌驾万难, 必可成功。"},
    27: {"luck": "凶带吉", "comment": "一成一败, 一盛一衰, 须防中途突变。"},
    28: {"luck": "凶",   "comment": "鱼临旱地, 难逃噩运, 此数大凶, 不如更名。"},
    29: {"luck": "吉",   "comment": "智谋兼备, 名利双收, 大业成就, 漫长气运。"},
    30: {"luck": "凶带吉", "comment": "吉凶参半, 得失相伴, 投机取巧, 须防失误。"},
    31: {"luck": "大吉", "comment": "智勇得志, 千挑百战, 自力更生, 大功大业。"},
    32: {"luck": "大吉", "comment": "池中之龙, 风云际会, 一跃上天, 成功可望。"},
    33: {"luck": "大吉", "comment": "意气用事, 人和必失, 善用智慧, 必可昌隆。"},
    34: {"luck": "大凶", "comment": "灾难不绝, 难望成功, 此数大凶, 不可使用。"},
    35: {"luck": "吉",   "comment": "中吉之数, 进退保守, 生意安稳, 须靠保守。"},
    36: {"luck": "凶带吉", "comment": "波澜重叠, 常陷穷困, 动不如静, 有才有德。"},
    37: {"luck": "大吉", "comment": "逢凶化吉, 吉人天相, 风调雨顺, 福之大者。"},
    38: {"luck": "凶带吉", "comment": "名虽可得, 利则难获, 艺界发展, 可望成功。"},
    39: {"luck": "大吉", "comment": "云开见月, 虽有劳碌, 光明坦途, 指日可待。"},
    40: {"luck": "凶带吉", "comment": "一胜一败, 沉浮不定, 知难而退, 自获天佑。"},
    41: {"luck": "大吉", "comment": "天赋吉运, 德望兼备, 继续努力, 前途无限。"},
    42: {"luck": "凶带吉", "comment": "事业不专, 十九不成, 专心一意, 始可成功。"},
    43: {"luck": "凶带吉", "comment": "雨夜之花, 外祥内苦, 忍耐自重, 始保平安。"},
    44: {"luck": "大凶", "comment": "虽用心计, 事难遂愿, 贪功好进, 必招失败。"},
    45: {"luck": "大吉", "comment": "杨柳遇春, 绿叶发枝, 冲破难关, 一举成名。"},
    46: {"luck": "凶",   "comment": "坎坷不平, 艰难重重, 若无耐心, 难定大业。"},
    47: {"luck": "大吉", "comment": "有贵人助, 可成大业, 虽遇不幸, 浮沉不定。"},
    48: {"luck": "大吉", "comment": "美化之数, 鹤鸣九皋, 可为顾问, 谋事有成。"},
    49: {"luck": "凶",   "comment": "遇吉则吉, 遇凶则凶, 惟靠谨慎, 逢凶化吉。"},
    50: {"luck": "凶带吉", "comment": "吉凶互见, 一成一败, 凶中有吉, 吉中有凶。"},
    51: {"luck": "凶带吉", "comment": "一盛一衰, 浮沉不常, 自重自处, 可保平安。"},
    52: {"luck": "大吉", "comment": "草木逢春, 雨过天晴, 渡过难关, 即获成功。"},
    53: {"luck": "凶",   "comment": "盛衰参半, 外祥内苦, 先吉后凶, 先凶后吉。"},
    54: {"luck": "大凶", "comment": "虽倾全力, 难望成功, 此数大凶, 最好改名。"},
    55: {"luck": "凶带吉", "comment": "外观隆昌, 内隐祸患, 克服难关, 始可成功。"},
    56: {"luck": "凶",   "comment": "事与愿违, 终难成功, 欲速不达, 有始无终。"},
    57: {"luck": "吉",   "comment": "虽有困难, 时来运转, 曰后发达, 可享盛名。"},
    58: {"luck": "凶带吉", "comment": "半凶半吉, 浮沉多端, 始遭灾难, 后得幸福。"},
    59: {"luck": "凶",   "comment": "遇事犹疑, 难望成事, 大刀阔斧, 始可有成。"},
    60: {"luck": "大凶", "comment": "黑暗无光, 心迷意乱, 出尔反尔, 难定方针。"},
    61: {"luck": "大吉", "comment": "云遮半月, 内隐风波, 应自重慎始, 必可成功。"},
    62: {"luck": "凶",   "comment": "烦闷懊恼, 事业不振, 信用渐失, 不致失败。"},
    63: {"luck": "大吉", "comment": "万物化育, 繁荣之象, 专心一意, 始能成事。"},
    64: {"luck": "大凶", "comment": "见异思迁, 十九不成, 徒劳无功, 不如更名。"},
    65: {"luck": "大吉", "comment": "吉运自来, 能享盛名, 把握机会, 必获成功。"},
    66: {"luck": "凶",   "comment": "黑夜漫长, 进退维谷, 内外不和, 信用缺乏。"},
    67: {"luck": "大吉", "comment": "独营事业, 事事如意, 功成名就, 富贵自来。"},
    68: {"luck": "大吉", "comment": "思虑周详, 计划力行, 不失先机, 可望成功。"},
    69: {"luck": "大凶", "comment": "动摇不安, 常陷逆境, 不得时运, 难得利达。"},
    70: {"luck": "大凶", "comment": "惨淡经营, 难免贫困, 此数大凶, 不可用之。"},
    71: {"luck": "凶带吉", "comment": "吉凶参半, 惟赖勇气, 贯彻力行, 可得成功。"},
    72: {"luck": "凶",   "comment": "利害混集, 凶多于吉, 得而复失, 难以安顺。"},
    73: {"luck": "吉",   "comment": "安稳之中, 享自然之福, 力行不懈, 终必成功。"},
    74: {"luck": "大凶", "comment": "利不及费, 坐食山空, 如无智谋, 难望成事。"},
    75: {"luck": "凶带吉", "comment": "吉中带凶, 欲速不达, 进不如守, 可保安祥。"},
    76: {"luck": "大凶", "comment": "此数大凶, 破产之象, 宜速改名, 以避厄运。"},
    77: {"luck": "凶带吉", "comment": "先苦后甘, 先甘后苦, 如能守成, 可保安稳。"},
    78: {"luck": "凶带吉", "comment": "有得有失, 华而不实, 须防劫财, 始保平安。"},
    79: {"luck": "凶",   "comment": "如走夜路, 前途无光, 希望不大, 劳而无功。"},
    80: {"luck": "大凶", "comment": "辛苦无功, 事与愿违, 若能避世, 可享余生。"},
    81: {"luck": "大吉", "comment": "万物回春, 还本归元, 能得繁荣, 发达成功。"},
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
    return SHULI_81.get(n, {"luck": "未知", "comment": ""})


def wuxing_for(n: int) -> str:
    return LAST_DIGIT_WUXING[n % 10]


# --------------------------------------------------------------------------- #
# 三才吉凶 — based on the 五行 combination of 天 / 人 / 地.
# Simplified version: scoring by 相生/相克 relationships.
# --------------------------------------------------------------------------- #

from utils import WUXING_GEN, WUXING_KE


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
    "康": 11, "宁": 14, "福": 14, "寿": 14, "禄": 13, "财": 11, "兴": 16,
    "旺": 8, "成": 7, "功": 5, "立": 5, "建": 9, "国": 11, "家": 10,
    "兵": 7, "军": 9, "民": 5, "新": 13, "永": 5, "良": 7, "学": 16,
    "诗": 13, "婷": 12, "宇": 6, "晓": 16, "丽": 19, "倩": 10, "颖": 16,
    "妍": 7, "悦": 11, "瑶": 15, "雅": 12, "薇": 19, "婕": 11, "婉": 11,
    "嘉": 14, "怡": 9, "妙": 7, "佳": 8, "嫣": 14, "宁": 14, "甜": 11,
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


def stroke_count(ch: str, table: dict[str, int]) -> Optional[int]:
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

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="姓名五格剖象 (康熙笔画 + 81 数理)")
    p.add_argument("--name", type=str, required=True,
                   help="完整中文姓名, 如 王小明 / 欧阳子轩")
    p.add_argument("--compound-surname", action="store_true",
                   help="若姓为复姓, 加上此标志")
    p.add_argument("--strict", action="store_true",
                   help="严格模式: 任一字缺笔画即报错退出, 不用默认值蒙混")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    name = args.name.strip()
    if not name or len(name) < 2:
        json_print({"error": "invalid_name", "input": name,
                    "message": "姓名至少两个字"})
        return 1

    table = load_bihua_table()

    # Split: assume 1-char surname unless --compound-surname
    if args.compound_surname:
        if len(name) < 3:
            json_print({"error": "compound_surname_needs_3plus"})
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
        json_print({
            "ok": False,
            "error": "missing_strokes",
            "message": f"以下字不在康熙笔画表中, 严格模式拒绝估算: {missing}",
            "missing_in_table": missing,
            "input": vars(args),
        })
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

    summary_parts = [
        f"姓名 {name}",
        f"天格 {grids['tian_ge']['number']}({grids['tian_ge']['luck']})",
        f"人格 {grids['ren_ge']['number']}({grids['ren_ge']['luck']})",
        f"地格 {grids['di_ge']['number']}({grids['di_ge']['luck']})",
        f"外格 {grids['wai_ge']['number']}({grids['wai_ge']['luck']})",
        f"总格 {grids['zong_ge']['number']}({grids['zong_ge']['luck']})",
        f"三才 {sancai['combo']} → {sancai['luck']}",
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
        "summary": "; ".join(summary_parts),
    }
    if missing:
        out["warning"] = (
            f"以下字未在康熙笔画表中, 用默认值 8 估算, 五格吉凶不可靠: {missing}。"
            f"请补 assets/name_bihua.json 或用 --strict 拒绝估算。"
        )

    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
