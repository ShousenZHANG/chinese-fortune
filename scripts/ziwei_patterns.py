"""紫微斗数 格局 (pattern) detection.

Given a chart dict produced by ``ziwei_calc.py`` (or a richer enriched chart),
detect classical 格局 across four tiers:

  - 上格 (top-tier): the canonical noble-fate patterns
  - 中格 (middle-tier): well-known structural patterns
  - 副格 (lucky-helper): helper-star patterns that boost the chart
  - 凶格 (bad-tier): adverse patterns

The detector is purely declarative — each pattern is a rule expressed as data
plus a tiny check function. The library is import-safe (no side effects),
depends only on the standard library, and tolerates partial charts: when a
palace does not carry auxiliary-star fields (e.g. only the 14 main stars are
present), patterns that require those fields are simply skipped rather than
raising.

Public API:
    detect_patterns(chart) -> list[dict]

Each chart palace is expected to be a dict resembling::

    {
        "index": int,                 # 0..11 with 0 == 命宫
        "name": str,                  # 命宫 / 兄弟宫 / ...
        "branch": str,                # 子..亥
        "main_stars": list[str],      # 14 主星 in this palace
        "lucky_stars": list[str],     # 左辅 / 右弼 / 文昌 / 文曲 / 天魁 / 天钺 / 禄存 / 天马 ...
        "malefic_stars": list[str],   # 擎羊 / 陀罗 / 火星 / 铃星 / 地空 / 地劫 ...
        "sihua_native": list[str],    # ["禄", "权", ...] — 年干四化 reaching this palace
    }

Top-level keys also consulted::

    chart["four_transformations"] = {"禄": "...", "权": "...", "科": "...", "忌": "..."}
    chart["twelve_palaces"]: list[palace_dict]

Patterns operate on either the palace itself, the sandwich (前后两宫), or the
三方四正 (本宫 + 对宫 + 三合左右).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


# --------------------------------------------------------------------------- #
# Constants — names of stars referenced by patterns
# --------------------------------------------------------------------------- #

MAIN_STARS: tuple[str, ...] = (
    "紫微", "天机", "太阳", "武曲", "天同", "廉贞",
    "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军",
)

LUCKY_STARS: tuple[str, ...] = (
    "左辅", "右弼", "文昌", "文曲", "天魁", "天钺", "禄存", "天马",
)

MALEFIC_STARS: tuple[str, ...] = (
    "擎羊", "陀罗", "火星", "铃星", "地空", "地劫",
)

SIHUA_TYPES: tuple[str, ...] = ("禄", "权", "科", "忌")


# --------------------------------------------------------------------------- #
# Tier labels
# --------------------------------------------------------------------------- #

TIER_TOP = "上格"
TIER_MID = "中格"
TIER_FU = "副格"
TIER_BAD = "凶格"


# --------------------------------------------------------------------------- #
# Helpers — chart navigation
# --------------------------------------------------------------------------- #


def _palaces(chart: dict) -> list[dict]:
    """Return the 12 palaces, normalised to a stable shape."""
    raw = chart.get("twelve_palaces") or chart.get("palaces") or []
    normalised: list[dict] = []
    for p in raw:
        normalised.append(
            {
                "index": p.get("index"),
                "name": p.get("name", ""),
                "branch": p.get("branch", ""),
                "stem": p.get("stem", ""),
                "main_stars": list(p.get("main_stars") or []),
                "lucky_stars": list(p.get("lucky_stars") or []),
                "malefic_stars": list(p.get("malefic_stars") or []),
                "sihua_native": _sihua_names(p),
                "raw": p,
            }
        )
    return normalised


def _sihua_names(palace: dict) -> list[str]:
    """Extract just the 四化 types ("禄"/"权"/"科"/"忌") for a palace."""
    sihua = palace.get("sihua_native") or palace.get("si_hua") or []
    out: list[str] = []
    for item in sihua:
        if isinstance(item, str) and item in SIHUA_TYPES:
            out.append(item)
        elif isinstance(item, dict):
            t = item.get("type")
            if t in SIHUA_TYPES:
                out.append(t)
    return out


def _all_stars(palace: dict) -> list[str]:
    return (
        palace.get("main_stars", [])
        + palace.get("lucky_stars", [])
        + palace.get("malefic_stars", [])
    )


def _find_ming_index(palaces: list[dict]) -> int:
    """Find the 命宫 index in the palaces list (defaults to 0)."""
    for i, p in enumerate(palaces):
        if p["name"] == "命宫" or p.get("raw", {}).get("is_ming_gong"):
            return i
    return 0


def _san_fang_si_zheng_indices(idx: int) -> list[int]:
    """Return four indices: 本宫, 对宫(+6), 三合(+4), 三合(-4)."""
    return [
        idx % 12,
        (idx + 6) % 12,
        (idx + 4) % 12,
        (idx - 4) % 12,
    ]


def _sandwich_indices(idx: int) -> tuple[int, int]:
    """Return (idx-1, idx+1) modulo 12 — the two flanking palaces."""
    return (idx - 1) % 12, (idx + 1) % 12


def _stars_in(palaces: list[dict], indices: Iterable[int]) -> set[str]:
    pool: set[str] = set()
    for i in indices:
        pool.update(_all_stars(palaces[i]))
    return pool


def _sfsz_stars(palaces: list[dict], idx: int) -> set[str]:
    return _stars_in(palaces, _san_fang_si_zheng_indices(idx))


# --------------------------------------------------------------------------- #
# Pattern hit dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PatternHit:
    name: str
    type: str
    palace: str
    palace_index: int
    evidence: str
    source: str
    interpretation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "palace": self.palace,
            "palace_index": self.palace_index,
            "evidence": self.evidence,
            "source": self.source,
            "interpretation": self.interpretation,
        }


def _hit(
    name: str,
    type: str,
    palace: dict,
    evidence: str,
    source: str,
    interpretation: str,
) -> PatternHit:
    return PatternHit(
        name=name,
        type=type,
        palace=palace.get("name", "命宫"),
        palace_index=int(palace.get("index", 0) or 0),
        evidence=evidence,
        source=source,
        interpretation=interpretation,
    )


# --------------------------------------------------------------------------- #
# Pattern check functions
#
# Each receives (palaces, ming_idx, sihua_global) and returns a list of hits.
# --------------------------------------------------------------------------- #


def _chk_junchen_qinghui(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """1. 君臣庆会: 紫微 + 左辅/右弼 同宫 (or 紫微 在 命/官 + 左右辅弼夹)."""
    hits: list[PatternHit] = []
    name, src = "君臣庆会", "《紫微斗数全书·骨髓赋》"
    interp = "紫微得辅弼相佐, 一呼百诺, 主大贵, 宜居高位, 多有领袖之才."
    for p in palaces:
        if "紫微" in p["main_stars"]:
            same_palace = ("左辅" in p["lucky_stars"]) or ("右弼" in p["lucky_stars"])
            if same_palace and p["name"] in ("命宫", "官禄宫"):
                hits.append(
                    _hit(
                        name,
                        TIER_TOP,
                        p,
                        f"紫微 与 {'左辅' if '左辅' in p['lucky_stars'] else ''}"
                        f"{'右弼' if '右弼' in p['lucky_stars'] else ''} 同宫 于 {p['name']}{p['branch']}宫",
                        src,
                        interp,
                    )
                )
                continue
            # 夹宫: 紫微 居 命/官, 左辅 + 右弼 分别在前后两宫
            if p["name"] in ("命宫", "官禄宫"):
                prev_i, next_i = _sandwich_indices(int(p["index"]))
                stars_neighbour = _all_stars(palaces[prev_i]) + _all_stars(
                    palaces[next_i]
                )
                if "左辅" in stars_neighbour and "右弼" in stars_neighbour:
                    hits.append(
                        _hit(
                            name,
                            TIER_TOP,
                            p,
                            f"紫微 居 {p['name']}, 左辅 + 右弼 前后两宫夹照",
                            src,
                            interp,
                        )
                    )
    return hits


def _chk_zifu_tonggong(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """2. 紫府同宫: 紫微 + 天府 在 命宫 (限 寅 / 申宫)."""
    p = palaces[mi]
    if (
        "紫微" in p["main_stars"]
        and "天府" in p["main_stars"]
        and p["branch"] in ("寅", "申")
    ):
        return [
            _hit(
                "紫府同宫",
                TIER_TOP,
                p,
                f"紫微 + 天府 同坐 {p['branch']}宫命宫 (帝座与库星同会)",
                "《紫微斗数全书·诸星问答》",
                "君臣相会, 一生贵显, 主有领袖才能, 中年发达, 富贵双全.",
            )
        ]
    return []


def _chk_fu_xiang_chao_yuan(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """3. 府相朝垣: 命宫无紫府, 三方四正 见 天府 + 天相."""
    p = palaces[mi]
    if "紫微" in p["main_stars"] or "天府" in p["main_stars"]:
        return []
    sfsz = _sfsz_stars(palaces, mi)
    if "天府" in sfsz and "天相" in sfsz:
        return [
            _hit(
                "府相朝垣",
                TIER_TOP,
                p,
                "命宫无紫府, 三方四正 见 天府 + 天相 朝照",
                "《紫微斗数全书》",
                "府相会命, 衣食丰足, 平生有禄, 主稳健富贵, 利于公职与管理.",
            )
        ]
    return []


def _chk_yang_liang_chang_lu(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """4. 阳梁昌禄: 命宫 三方四正 同时见 太阳, 天梁, 文昌, 禄存."""
    p = palaces[mi]
    sfsz = _sfsz_stars(palaces, mi)
    needed = {"太阳", "天梁", "文昌", "禄存"}
    if needed.issubset(sfsz):
        return [
            _hit(
                "阳梁昌禄",
                TIER_TOP,
                p,
                "命宫三方四正同会 太阳 + 天梁 + 文昌 + 禄存 (大贵格)",
                "《紫微斗数全书》",
                "阳梁昌禄, 文官之尊, 主学问通达、仕途显赫, 尤宜学者、公务员、专业人士.",
            )
        ]
    return []


def _chk_mingzhu_chuhai(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """5. 明珠出海: 命宫 在 未/丑 + 三方四正 见 太阳 太阴 + 文昌 文曲."""
    p = palaces[mi]
    if p["branch"] not in ("未", "丑"):
        return []
    sfsz = _sfsz_stars(palaces, mi)
    if {"太阳", "太阴", "文昌", "文曲"}.issubset(sfsz):
        return [
            _hit(
                "明珠出海",
                TIER_TOP,
                p,
                f"命宫在 {p['branch']} 宫, 三方四正同会 太阳 + 太阴 + 文昌 + 文曲",
                "《紫微斗数全书·诸星问答》",
                "明珠出海, 主才华富贵两全, 一生光显, 利文教与名望事业.",
            )
        ]
    return []


def _chk_qisha_chaodou(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """6. 七杀朝斗: 七杀 在 命 + 紫微 在 福德 三方."""
    p = palaces[mi]
    if "七杀" not in p["main_stars"]:
        return []
    # 福德宫位置: 命宫 + 10 (按命兄夫子财疾迁奴官田福父的逆排, index 10)
    fu_idx = (mi + 10) % 12
    fu_sfsz = _sfsz_stars(palaces, fu_idx)
    if "紫微" in fu_sfsz:
        return [
            _hit(
                "七杀朝斗",
                TIER_TOP,
                p,
                f"七杀 坐 命宫({p['branch']}宫), 紫微 在 福德宫三方照",
                "《紫微斗数全书·骨髓赋》",
                "七杀朝斗, 爵禄荣昌, 主武贵或开创之才, 中年以后多有大成.",
            )
        ]
    return []


def _chk_jiyuetongliang(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """7. 机月同梁格: 三方四正 见 天机 + 太阴 + 天同 + 天梁 (任三即可, 全见为上)."""
    sfsz = _sfsz_stars(palaces, mi)
    needed = {"天机", "太阴", "天同", "天梁"}
    present = needed & sfsz
    if len(present) >= 3:
        full = len(present) == 4
        return [
            _hit(
                "机月同梁格",
                TIER_MID,
                palaces[mi],
                f"三方四正见 {'/'.join(sorted(present))}"
                + (" (四星全见)" if full else " (三星会照)"),
                "《紫微斗数全书》",
                "机月同梁, 作吏人, 主公门稳健、文职清贵, 宜任职受薪, 不宜创业冒险.",
            )
        ]
    return []


def _chk_shapolang(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """8. 杀破狼格: 三方四正 见 七杀 + 破军 + 贪狼."""
    sfsz = _sfsz_stars(palaces, mi)
    if {"七杀", "破军", "贪狼"}.issubset(sfsz):
        return [
            _hit(
                "杀破狼格",
                TIER_MID,
                palaces[mi],
                "三方四正同会 七杀 + 破军 + 贪狼",
                "《紫微斗数全书》",
                "杀破狼会, 主一生剧变开创, 起伏极大, 有大成也有大败, 宜创业与变革之业.",
            )
        ]
    return []


def _chk_huotan(palaces: list[dict], mi: int, sihua: dict) -> list[PatternHit]:
    """9. 火贪格: 贪狼 + 火星 同宫."""
    hits: list[PatternHit] = []
    for p in palaces:
        if "贪狼" in p["main_stars"] and "火星" in p["malefic_stars"]:
            hits.append(
                _hit(
                    "火贪格",
                    TIER_MID,
                    p,
                    f"贪狼 + 火星 同坐 {p['name']}{p['branch']}宫",
                    "《紫微斗数全书》",
                    "贪狼遇火, 武职峥嵘, 主暴发横财, 宜把握时机, 但忌反复浮沉.",
                )
            )
    return hits


def _chk_lingtan(palaces: list[dict], mi: int, sihua: dict) -> list[PatternHit]:
    """10. 铃贪格: 贪狼 + 铃星 同宫."""
    hits: list[PatternHit] = []
    for p in palaces:
        if "贪狼" in p["main_stars"] and "铃星" in p["malefic_stars"]:
            hits.append(
                _hit(
                    "铃贪格",
                    TIER_MID,
                    p,
                    f"贪狼 + 铃星 同坐 {p['name']}{p['branch']}宫",
                    "《紫微斗数全书》",
                    "贪狼遇铃, 同主暴发, 利于偏门与突发机遇, 但常起得快败得也快.",
                )
            )
    return hits


def _chk_wutan(palaces: list[dict], mi: int, sihua: dict) -> list[PatternHit]:
    """11. 武贪格: 武曲 + 贪狼 同宫."""
    hits: list[PatternHit] = []
    for p in palaces:
        if "武曲" in p["main_stars"] and "贪狼" in p["main_stars"]:
            hits.append(
                _hit(
                    "武贪格",
                    TIER_MID,
                    p,
                    f"武曲 + 贪狼 同坐 {p['name']}{p['branch']}宫",
                    "《紫微斗数全书》",
                    "武贪同宫, 三十而发, 主中年以后财官两旺, 利商利武, 早年宜静守.",
                )
            )
    return hits


def _chk_riyue_tonggong(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """12. 日月同宫: 太阳 + 太阴 同宫 (限 丑 or 未宫)."""
    hits: list[PatternHit] = []
    for p in palaces:
        if (
            "太阳" in p["main_stars"]
            and "太阴" in p["main_stars"]
            and p["branch"] in ("丑", "未")
        ):
            hits.append(
                _hit(
                    "日月同宫",
                    TIER_MID,
                    p,
                    f"太阳 + 太阴 同坐 {p['branch']}宫",
                    "《紫微斗数全书》",
                    "日月并明, 主才华横溢、刚柔并济, 富贵双全, 唯易心思矛盾.",
                )
            )
    return hits


def _chk_shi_zhong_yin_yu(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """13. 石中隐玉: 巨门 在 子 / 午 + 化禄/权/科."""
    hits: list[PatternHit] = []
    for p in palaces:
        if (
            "巨门" in p["main_stars"]
            and p["branch"] in ("子", "午")
            and any(t in p["sihua_native"] for t in ("禄", "权", "科"))
        ):
            hits.append(
                _hit(
                    "石中隐玉",
                    TIER_MID,
                    p,
                    f"巨门 居 {p['branch']}宫 加 化{'/'.join(p['sihua_native'])}",
                    "《紫微斗数全书》",
                    "石中隐玉, 主大器晚成, 内秀含华, 中年以后渐显富贵, 利文教口才之业.",
                )
            )
    return hits


def _chk_fubi_jiaming(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """14. 辅弼夹命: 左辅 + 右弼 在 命宫 前后两宫."""
    prev_i, next_i = _sandwich_indices(mi)
    prev_stars = _all_stars(palaces[prev_i])
    next_stars = _all_stars(palaces[next_i])
    if ("左辅" in prev_stars and "右弼" in next_stars) or (
        "右弼" in prev_stars and "左辅" in next_stars
    ):
        return [
            _hit(
                "辅弼夹命",
                TIER_MID,
                palaces[mi],
                f"左辅 + 右弼 分坐命宫前后两宫 ({palaces[prev_i]['branch']}/{palaces[next_i]['branch']})",
                "《紫微斗数全书》",
                "辅弼夹命, 得贵人提携, 一生多助力, 宜与人合作, 不宜独行.",
            )
        ]
    return []


def _chk_changqu_jiaming(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """15. 昌曲夹命: 文昌 + 文曲 在 命宫 前后两宫."""
    prev_i, next_i = _sandwich_indices(mi)
    prev_stars = _all_stars(palaces[prev_i])
    next_stars = _all_stars(palaces[next_i])
    if ("文昌" in prev_stars and "文曲" in next_stars) or (
        "文曲" in prev_stars and "文昌" in next_stars
    ):
        return [
            _hit(
                "昌曲夹命",
                TIER_FU,
                palaces[mi],
                f"文昌 + 文曲 分坐命宫前后两宫 ({palaces[prev_i]['branch']}/{palaces[next_i]['branch']})",
                "《紫微斗数全书》",
                "昌曲夹命, 主聪明俊秀, 文章秀发, 利考试功名与文化事业.",
            )
        ]
    return []


def _chk_kuiyue_jiaming(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """16. 魁钺夹命: 天魁 + 天钺 在 命宫 前后两宫."""
    prev_i, next_i = _sandwich_indices(mi)
    prev_stars = _all_stars(palaces[prev_i])
    next_stars = _all_stars(palaces[next_i])
    if ("天魁" in prev_stars and "天钺" in next_stars) or (
        "天钺" in prev_stars and "天魁" in next_stars
    ):
        return [
            _hit(
                "魁钺夹命",
                TIER_FU,
                palaces[mi],
                f"天魁 + 天钺 分坐命宫前后两宫 ({palaces[prev_i]['branch']}/{palaces[next_i]['branch']})",
                "《紫微斗数全书》",
                "魁钺夹命, 天乙贵人临身, 主一生多贵人提携, 逢凶化吉.",
            )
        ]
    return []


def _chk_shuanglu_chaoyuan(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """17. 双禄朝垣: 命宫 见 化禄 + 禄存."""
    sfsz = _sfsz_stars(palaces, mi)
    has_lu_cun = "禄存" in sfsz
    has_hua_lu = "禄" in palaces[mi]["sihua_native"] or _hualu_in_sfsz(palaces, mi, sihua)
    if has_lu_cun and has_hua_lu:
        return [
            _hit(
                "双禄朝垣",
                TIER_FU,
                palaces[mi],
                "命宫三方四正同会 化禄 + 禄存 (双禄交流)",
                "《紫微斗数全书》",
                "双禄朝垣, 财源滚滚, 主富足安康, 利财利商, 一生衣禄无忧.",
            )
        ]
    return []


def _hualu_in_sfsz(palaces: list[dict], mi: int, sihua: dict) -> bool:
    """Check if the year-stem 化禄 star is anywhere in 三方四正."""
    hua_lu_star = sihua.get("禄")
    if not hua_lu_star:
        return False
    return hua_lu_star in _sfsz_stars(palaces, mi)


def _chk_sanqi_jiahui(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """18. 三奇加会: 化禄 化权 化科 三化 同时 落 三方四正."""
    sfsz_indices = _san_fang_si_zheng_indices(mi)
    found: set[str] = set()
    for i in sfsz_indices:
        for t in palaces[i]["sihua_native"]:
            if t in ("禄", "权", "科"):
                found.add(t)
    if found == {"禄", "权", "科"}:
        return [
            _hit(
                "三奇加会",
                TIER_FU,
                palaces[mi],
                "命宫三方四正同会 化禄 + 化权 + 化科 三奇",
                "《紫微斗数全书》",
                "三奇加会, 富贵双全, 主才华、权位、名声三者俱备, 大格也.",
            )
        ]
    return []


def _chk_huaji_ruming(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """19. 化忌入命: 化忌 落 命宫."""
    if "忌" in palaces[mi]["sihua_native"]:
        return [
            _hit(
                "化忌入命",
                TIER_BAD,
                palaces[mi],
                f"年干化忌 ({sihua.get('忌', '?')}) 坐 命宫",
                "《紫微斗数全书》",
                "化忌入命, 主一生多波折阻碍, 性格易钻牛角尖, 需修心养性以化解.",
            )
        ]
    return []


def _chk_yangtuo_jiaji(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """20. 羊陀夹忌: 擎羊 + 陀罗 夹 (化忌所在的) 宫."""
    hits: list[PatternHit] = []
    hua_ji_star = sihua.get("忌")
    if not hua_ji_star:
        return hits
    for p in palaces:
        if "忌" in p["sihua_native"] or hua_ji_star in _all_stars(p):
            prev_i, next_i = _sandwich_indices(int(p["index"]))
            prev_m = palaces[prev_i]["malefic_stars"]
            next_m = palaces[next_i]["malefic_stars"]
            if (
                ("擎羊" in prev_m and "陀罗" in next_m)
                or ("陀罗" in prev_m and "擎羊" in next_m)
            ):
                hits.append(
                    _hit(
                        "羊陀夹忌",
                        TIER_BAD,
                        p,
                        f"擎羊 + 陀罗 夹 化忌所居 {p['name']}{p['branch']}宫",
                        "《紫微斗数全书》",
                        "羊陀夹忌, 凶煞交攻, 主该宫所主之事多挫折, 宜避险防小人.",
                    )
                )
    return hits


def _chk_yangtuo_jiaming(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """21. 羊陀夹命: 擎羊 + 陀罗 在 命宫 前后两宫."""
    prev_i, next_i = _sandwich_indices(mi)
    prev_m = palaces[prev_i]["malefic_stars"]
    next_m = palaces[next_i]["malefic_stars"]
    if ("擎羊" in prev_m and "陀罗" in next_m) or (
        "陀罗" in prev_m and "擎羊" in next_m
    ):
        return [
            _hit(
                "羊陀夹命",
                TIER_BAD,
                palaces[mi],
                f"擎羊 + 陀罗 分坐命宫前后两宫 ({palaces[prev_i]['branch']}/{palaces[next_i]['branch']})",
                "《紫微斗数全书》",
                "羊陀夹命, 主一生奔波劳碌, 易招小人或意外, 性格刚烈需自我修养.",
            )
        ]
    return []


def _chk_kongjie_jiaming(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """22. 空劫夹命: 地空 + 地劫 在 命宫 前后两宫."""
    prev_i, next_i = _sandwich_indices(mi)
    prev_m = palaces[prev_i]["malefic_stars"]
    next_m = palaces[next_i]["malefic_stars"]
    if ("地空" in prev_m and "地劫" in next_m) or (
        "地劫" in prev_m and "地空" in next_m
    ):
        return [
            _hit(
                "空劫夹命",
                TIER_BAD,
                palaces[mi],
                f"地空 + 地劫 分坐命宫前后两宫 ({palaces[prev_i]['branch']}/{palaces[next_i]['branch']})",
                "《紫微斗数全书》",
                "空劫夹命, 主财来财去, 一生易遭破耗, 宜清心寡欲, 不宜投机.",
            )
        ]
    return []


def _chk_matou_daijian(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """23. 马头带箭: 天马 + 擎羊 同宫."""
    hits: list[PatternHit] = []
    for p in palaces:
        if "天马" in p["lucky_stars"] and "擎羊" in p["malefic_stars"]:
            hits.append(
                _hit(
                    "马头带箭",
                    TIER_BAD,
                    p,
                    f"天马 + 擎羊 同坐 {p['name']}{p['branch']}宫",
                    "《紫微斗数全书》",
                    "马头带箭, 边疆立功之命, 主一生奔波动荡, 有威武之象, 但也易招伤损.",
                )
            )
    return hits


def _chk_lingchang_tuowu(
    palaces: list[dict], mi: int, sihua: dict
) -> list[PatternHit]:
    """24. 铃昌陀武: 铃星 + 文昌 + 陀罗 + 武曲 同宫 or 三方."""
    hits: list[PatternHit] = []
    needed = {"铃星", "文昌", "陀罗", "武曲"}
    # 同宫
    for p in palaces:
        pool = set(_all_stars(p))
        if needed.issubset(pool):
            hits.append(
                _hit(
                    "铃昌陀武",
                    TIER_BAD,
                    p,
                    f"铃星 + 文昌 + 陀罗 + 武曲 四星同会 {p['name']}{p['branch']}宫",
                    "《紫微斗数全书·骨髓赋》",
                    "铃昌陀武, 限至投河, 凶煞交并, 主重大灾厄, 宜远行避凶或修身积德.",
                )
            )
            return hits  # 同宫已极凶 — 不再寻三方
    # 三方
    for i, p in enumerate(palaces):
        sfsz = _sfsz_stars(palaces, i)
        if needed.issubset(sfsz):
            hits.append(
                _hit(
                    "铃昌陀武",
                    TIER_BAD,
                    p,
                    f"{p['name']}{p['branch']}宫 三方四正 同会 铃星 + 文昌 + 陀罗 + 武曲",
                    "《紫微斗数全书·骨髓赋》",
                    "铃昌陀武, 三方会照, 主限运坎坷, 需小心防范意外与官非.",
                )
            )
            break
    return hits


# --------------------------------------------------------------------------- #
# Pattern registry — rules as data
# --------------------------------------------------------------------------- #


PATTERN_REGISTRY: list[
    tuple[str, Callable[[list[dict], int, dict], list[PatternHit]]]
] = [
    # 上格
    ("君臣庆会", _chk_junchen_qinghui),
    ("紫府同宫", _chk_zifu_tonggong),
    ("府相朝垣", _chk_fu_xiang_chao_yuan),
    ("阳梁昌禄", _chk_yang_liang_chang_lu),
    ("明珠出海", _chk_mingzhu_chuhai),
    ("七杀朝斗", _chk_qisha_chaodou),
    # 中格
    ("机月同梁格", _chk_jiyuetongliang),
    ("杀破狼格", _chk_shapolang),
    ("火贪格", _chk_huotan),
    ("铃贪格", _chk_lingtan),
    ("武贪格", _chk_wutan),
    ("日月同宫", _chk_riyue_tonggong),
    ("石中隐玉", _chk_shi_zhong_yin_yu),
    ("辅弼夹命", _chk_fubi_jiaming),
    # 副格
    ("昌曲夹命", _chk_changqu_jiaming),
    ("魁钺夹命", _chk_kuiyue_jiaming),
    ("双禄朝垣", _chk_shuanglu_chaoyuan),
    ("三奇加会", _chk_sanqi_jiahui),
    # 凶格
    ("化忌入命", _chk_huaji_ruming),
    ("羊陀夹忌", _chk_yangtuo_jiaji),
    ("羊陀夹命", _chk_yangtuo_jiaming),
    ("空劫夹命", _chk_kongjie_jiaming),
    ("马头带箭", _chk_matou_daijian),
    ("铃昌陀武", _chk_lingchang_tuowu),
]


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def detect_patterns(chart: dict) -> list[dict]:
    """Detect 紫微 格局 in the given chart.

    Args:
        chart: A 紫微 chart dict as produced by ``ziwei_calc.py``.

    Returns:
        A list of pattern hit dicts (see ``PatternHit.to_dict``). Empty list
        if the chart is incomplete or no patterns match.
    """
    palaces = _palaces(chart)
    if len(palaces) != 12:
        return []
    mi = _find_ming_index(palaces)
    sihua = dict(chart.get("four_transformations") or {})

    all_hits: list[PatternHit] = []
    seen: set[str] = set()
    for _name, check in PATTERN_REGISTRY:
        try:
            for hit in check(palaces, mi, sihua):
                key = f"{hit.name}@{hit.palace_index}"
                if key in seen:
                    continue
                seen.add(key)
                all_hits.append(hit)
        except Exception:
            # Defensive: a malformed palace should not break the whole scan.
            continue

    return [h.to_dict() for h in all_hits]


# --------------------------------------------------------------------------- #
# Inline self-test
# --------------------------------------------------------------------------- #


def _sample_chart() -> dict:
    """Sample 紫府同宫 + 君臣庆会 + 化忌入命 chart at 申宫命宫."""
    branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    # 命宫 在 申 (index 8 in chart's own palace list); use the layout from
    # ziwei_calc.assign_palaces: name[i] at branch (mg_idx - i) % 12.
    # We'll build palaces so palace[0] (命宫) is 申, palace[1] is 未, etc.
    template = [
        # (name, branch, main, lucky, malefic, sihua_types)
        ("命宫", "申", ["紫微", "天府"], ["左辅", "右弼"], [], ["科"]),
        ("兄弟宫", "未", ["太阴"], [], [], []),
        ("夫妻宫", "午", ["贪狼"], ["文昌"], ["火星"], []),
        ("子女宫", "巳", ["天同"], [], [], []),
        ("财帛宫", "辰", ["武曲", "天相"], ["文曲"], [], []),
        ("疾厄宫", "卯", ["太阳"], [], [], []),
        ("迁移宫", "寅", [], [], [], []),
        ("奴仆宫", "丑", ["巨门"], [], [], []),
        ("官禄宫", "子", ["廉贞", "破军"], [], ["擎羊"], ["忌"]),
        ("田宅宫", "亥", ["七杀"], [], ["陀罗"], []),
        ("福德宫", "戌", ["天梁"], ["禄存"], [], []),
        ("父母宫", "酉", ["天机"], [], [], []),
    ]
    palaces = []
    for i, (name, br, main, lucky, malefic, sihua) in enumerate(template):
        palaces.append(
            {
                "index": i,
                "name": name,
                "branch": br,
                "main_stars": main,
                "lucky_stars": lucky,
                "malefic_stars": malefic,
                "sihua_native": sihua,
                "is_ming_gong": i == 0,
            }
        )
    return {
        "twelve_palaces": palaces,
        "four_transformations": {
            "禄": "天同",
            "权": "天机",
            "科": "文昌",
            "忌": "廉贞",
        },
    }


if __name__ == "__main__":
    sample = _sample_chart()
    hits = detect_patterns(sample)
    print(json.dumps(hits, ensure_ascii=False, indent=2))
    print(f"\n[self-test] {len(hits)} patterns detected.")
