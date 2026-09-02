"""紫微: 格局判定."""
from __future__ import annotations

from ziwei_palaces import san_fang_si_zheng
from ziwei_tables import _branch_offset

# Section 16 — 格局 (pattern detection)
# --------------------------------------------------------------------------- #


def _gather_sfsz_stars(
    branch: str,
    branch_to_all_stars: dict[str, list[str]],
) -> set[str]:
    """Return the union of main+aux stars over the 4 palaces of 三方四正."""
    sfsz = san_fang_si_zheng(branch)
    branches = [sfsz["本宫"], sfsz["对宫"], *sfsz["三合"]]
    out: set[str] = set()
    for b in branches:
        out.update(branch_to_all_stars.get(b, []))
    return out


def detect_patterns(
    ming_branch: str,
    branch_to_main_stars: dict[str, list[str]],
    branch_to_all_stars: dict[str, list[str]],
    palaces: list[dict],
    sihua: dict[str, str],
) -> list[dict]:
    out: list[dict] = []
    mg_stars_main = branch_to_main_stars.get(ming_branch, [])
    mg_stars_all = branch_to_all_stars.get(ming_branch, [])
    sfsz_set = _gather_sfsz_stars(ming_branch, branch_to_all_stars)

    # 1. 紫府同宫 — 紫微+天府同宫 (只可能在寅或申).
    for branch, stars in branch_to_main_stars.items():
        if "紫微" in stars and "天府" in stars:
            out.append({
                "name": "紫府同宫",
                "type": "上格",
                "evidence": f"紫微+天府同坐{branch}宫",
            })
            break

    # 2. 府相朝垣 — 命无紫府, 但三方四正见天府+天相.
    if (
        "紫微" not in mg_stars_main
        and "天府" not in mg_stars_main
        and "天府" in sfsz_set
        and "天相" in sfsz_set
    ):
        out.append({
            "name": "府相朝垣",
            "type": "上格",
            "evidence": "命宫无紫府, 三方四正见天府+天相",
        })

    # 3. 阳梁昌禄 — 三方四正 includes 太阳+天梁+文昌+(禄存或化禄星).
    sihua_lu_star = sihua.get("禄")
    has_lu_source = "禄存" in sfsz_set or (sihua_lu_star and sihua_lu_star in sfsz_set)
    if (
        "太阳" in sfsz_set
        and "天梁" in sfsz_set
        and "文昌" in sfsz_set
        and has_lu_source
    ):
        out.append({
            "name": "阳梁昌禄",
            "type": "上格",
            "evidence": "三方四正集齐太阳+天梁+文昌+(禄存或化禄)",
        })

    # 4. 机月同梁 — 三方四正含 天机/太阴/天同/天梁 任意 3+.
    jiyutong_set = {"天机", "太阴", "天同", "天梁"}
    hit = jiyutong_set & sfsz_set
    if len(hit) >= 3:
        out.append({
            "name": "机月同梁",
            "type": "中上格",
            "evidence": f"三方四正含机月同梁组合 {len(hit)}/4: {','.join(sorted(hit))}",
        })

    # 5. 杀破狼 — 三方四正含七杀+破军+贪狼.
    spl_set = {"七杀", "破军", "贪狼"}
    if spl_set.issubset(sfsz_set):
        out.append({
            "name": "杀破狼",
            "type": "变格",
            "evidence": "三方四正同时见七杀+破军+贪狼",
        })

    # 6/7/8. 火/铃/武贪 — 同宫.
    for branch, stars in branch_to_all_stars.items():
        if "贪狼" in stars:
            if "火星" in stars:
                out.append({
                    "name": "火贪格",
                    "type": "上格",
                    "evidence": f"火星+贪狼同坐{branch}宫(横发)",
                })
            if "铃星" in stars:
                out.append({
                    "name": "铃贪格",
                    "type": "上格",
                    "evidence": f"铃星+贪狼同坐{branch}宫(横发)",
                })
            if "武曲" in stars:
                out.append({
                    "name": "武贪格",
                    "type": "上格",
                    "evidence": f"武曲+贪狼同坐{branch}宫(财富格)",
                })

    # 9. 日月同宫 — 太阳+太阴同宫, 限丑/未.
    for branch, stars in branch_to_main_stars.items():
        if "太阳" in stars and "太阴" in stars and branch in {"丑", "未"}:
            out.append({
                "name": "日月同宫",
                "type": "上格",
                "evidence": f"太阳+太阴同坐{branch}宫(日月同辉)",
            })

    # 10. 明珠出海 — 命宫在未 + 三方四正见太阳/太阴/文昌/文曲.
    if ming_branch == "未" and {"太阳", "太阴", "文昌", "文曲"}.issubset(sfsz_set):
        out.append({
            "name": "明珠出海",
            "type": "上格",
            "evidence": "命宫在未, 三方四正聚太阳/太阴/文昌/文曲",
        })

    # 11. 辅弼夹命 — 命宫前后宫各有 左辅/右弼.
    prev_b = _branch_offset(ming_branch, -1)
    next_b = _branch_offset(ming_branch, 1)
    prev_stars = branch_to_all_stars.get(prev_b, [])
    next_stars = branch_to_all_stars.get(next_b, [])
    if (
        ("左辅" in prev_stars and "右弼" in next_stars)
        or ("右弼" in prev_stars and "左辅" in next_stars)
    ):
        out.append({
            "name": "辅弼夹命",
            "type": "上格",
            "evidence": f"左辅/右弼分坐命宫前后({prev_b}/{next_b})",
        })

    # 12. 昌曲夹命 — 文昌+文曲 夹.
    if (
        ("文昌" in prev_stars and "文曲" in next_stars)
        or ("文曲" in prev_stars and "文昌" in next_stars)
    ):
        out.append({
            "name": "昌曲夹命",
            "type": "上格",
            "evidence": f"文昌/文曲分坐命宫前后({prev_b}/{next_b})",
        })

    # 13. 羊陀夹忌 — 命宫坐 化忌星, 前后各有 擎羊/陀罗.
    ji_star = sihua.get("忌")
    if ji_star and ji_star in mg_stars_all:
        if (
            ("擎羊" in prev_stars and "陀罗" in next_stars)
            or ("陀罗" in prev_stars and "擎羊" in next_stars)
        ):
            out.append({
                "name": "羊陀夹忌",
                "type": "凶格",
                "evidence": f"化忌({ji_star})坐命, 擎羊陀罗夹之",
            })

    # 14. 空劫夹命 — 地空 + 地劫 夹命宫.
    if (
        ("地空" in prev_stars and "地劫" in next_stars)
        or ("地劫" in prev_stars and "地空" in next_stars)
    ):
        out.append({
            "name": "空劫夹命",
            "type": "凶格",
            "evidence": f"地空/地劫分坐命宫前后({prev_b}/{next_b})",
        })

    # 15. 马头带箭 — 天马 + 擎羊 同宫.
    for branch, stars in branch_to_all_stars.items():
        if "天马" in stars and "擎羊" in stars:
            out.append({
                "name": "马头带箭",
                "type": "变格",
                "evidence": f"天马+擎羊同坐{branch}宫(冲锋陷阵)",
            })

    return out


# --------------------------------------------------------------------------- #
