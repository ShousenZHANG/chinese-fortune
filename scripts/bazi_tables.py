"""八字: 干支 interaction reference tables + 旬空."""
from __future__ import annotations

from utils import xun_kong

# 干支 互动 reference tables (classical: 五合, 六合, 三合, 三会, 六冲, 六害, 三刑)
# --------------------------------------------------------------------------- #

# 天干五合 — 化气
TIANGAN_HE: dict[frozenset[str], str] = {
    frozenset(["甲", "己"]): "土",
    frozenset(["乙", "庚"]): "金",
    frozenset(["丙", "辛"]): "水",
    frozenset(["丁", "壬"]): "木",
    frozenset(["戊", "癸"]): "火",
}

# 地支六合
DIZHI_LIU_HE: dict[frozenset[str], str] = {
    frozenset(["子", "丑"]): "土",
    frozenset(["寅", "亥"]): "木",
    frozenset(["卯", "戌"]): "火",
    frozenset(["辰", "酉"]): "金",
    frozenset(["巳", "申"]): "水",
    frozenset(["午", "未"]): "土",
}

# 地支三合局 (申子辰/亥卯未/寅午戌/巳酉丑 → 五行)
SAN_HE_GROUPS: list[tuple[tuple[str, str, str], str]] = [
    (("申", "子", "辰"), "水"),
    (("亥", "卯", "未"), "木"),
    (("寅", "午", "戌"), "火"),
    (("巳", "酉", "丑"), "金"),
]

# 地支三会方 (寅卯辰/巳午未/申酉戌/亥子丑 → 五行)
SAN_HUI_GROUPS: list[tuple[tuple[str, str, str], str]] = [
    (("寅", "卯", "辰"), "木"),
    (("巳", "午", "未"), "火"),
    (("申", "酉", "戌"), "金"),
    (("亥", "子", "丑"), "水"),
]

# 地支六冲 (相对位)
DIZHI_CHONG: list[frozenset[str]] = [
    frozenset(["子", "午"]),
    frozenset(["丑", "未"]),
    frozenset(["寅", "申"]),
    frozenset(["卯", "酉"]),
    frozenset(["辰", "戌"]),
    frozenset(["巳", "亥"]),
]

# 地支六害
DIZHI_HAI: list[frozenset[str]] = [
    frozenset(["子", "未"]),
    frozenset(["丑", "午"]),
    frozenset(["寅", "巳"]),
    frozenset(["卯", "辰"]),
    frozenset(["申", "亥"]),
    frozenset(["酉", "戌"]),
]

# 三刑 — 寅巳申、丑戌未为三刑; 子卯相刑; 辰午酉亥自刑
SAN_XING_TRIPLES: list[tuple[str, str, str]] = [
    ("寅", "巳", "申"),
    ("丑", "戌", "未"),
]
SAN_XING_PAIRS: list[frozenset[str]] = [
    frozenset(["子", "卯"]),  # 无礼之刑
]
SAN_XING_SELF: list[str] = ["辰", "午", "酉", "亥"]  # 自刑

PILLAR_LABELS_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}


# --------------------------------------------------------------------------- #
# 空亡 (旬空)
# --------------------------------------------------------------------------- #

def xun_kong_of_day(day_stem: str, day_branch: str) -> list[str]:
    """Return the two 地支 in 旬空 for the given day pillar."""
    return xun_kong(day_stem, day_branch)


# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# 人元司令分野 — 月支 -> [(藏干, 司令日数), ...] 按 余气 / 中气 / 本气 顺序
# --------------------------------------------------------------------------- #
#
# references/00-intake.md:47 把「月支司令」列为每次八字批断 always surface 的字段,
# 01-bazi.md:74 与 01-bazi-paipan.md:3 都断言「scripts/bazi_calc.py 已自动完成」——
# 而实测输出里「司令」二字一次都不出现, 全库也没有任何一份分野表。也就是说一个被
# 两处文档声称「脚本已算好」的必出字段, 既没有数据也没有查表依据, Claude 只能漏报
# 或凭空编。
#
# 分野日数取通行本 (《渊海子平》系, 与《三命通会·论人元司事》一致), 四仲月两分、
# 四孟四季月三分, 每月合计 30 日。
REN_YUAN_SI_LING: dict[str, list[tuple[str, int]]] = {
    "寅": [("戊", 7), ("丙", 7), ("甲", 16)],
    "卯": [("甲", 10), ("乙", 20)],
    "辰": [("乙", 9), ("癸", 3), ("戊", 18)],
    "巳": [("戊", 7), ("庚", 7), ("丙", 16)],
    "午": [("丙", 10), ("己", 9), ("丁", 11)],
    "未": [("丁", 9), ("乙", 3), ("己", 18)],
    "申": [("戊", 7), ("壬", 7), ("庚", 16)],
    "酉": [("庚", 10), ("辛", 20)],
    "戌": [("辛", 9), ("丁", 3), ("戊", 18)],
    "亥": [("戊", 7), ("甲", 7), ("壬", 16)],
    "子": [("壬", 10), ("癸", 20)],
    "丑": [("癸", 9), ("辛", 3), ("己", 18)],
}

SI_LING_ROLE = ("余气", "中气", "本气")


def si_ling(month_branch: str, days_since_jie: int) -> dict | None:
    """哪一个藏干当令。``days_since_jie`` 为距本月「节」的整日数 (交节当日为 0)。

    返回 {stem, role, day_in_month, span, table}; 月支不识则返回 None。
    """
    fenye = REN_YUAN_SI_LING.get(month_branch)
    if not fenye:
        return None
    day = max(0, days_since_jie) + 1          # 交节当日算第 1 日
    total = sum(n for _, n in fenye)
    day = min(day, total)
    cursor = 0
    for i, (stem, span) in enumerate(fenye):
        cursor += span
        if day <= cursor:
            # 两分的月份没有中气, 末位仍是本气
            role = SI_LING_ROLE[i] if len(fenye) == 3 else                 ("余气" if i == 0 else "本气")
            return {
                "stem": stem,
                "role": role,
                "day_in_month": day,
                "span": span,
                "table": [{"stem": s, "days": n} for s, n in fenye],
            }
    return None
