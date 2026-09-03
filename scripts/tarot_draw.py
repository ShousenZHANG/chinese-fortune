"""Tarot card drawing with multiple spreads.

Subcommands:
    one           — single card
    three         — past / present / future
    celtic        — 10-card Celtic Cross (凯尔特十字)
    relationship  — 5-card relationship spread (关系阵)
    daily         — daily card

Args:
    --seed N         (optional, reproducibility)
    --question "..." (optional, included in output)

Card data loaded from ``assets/tarot78.json`` when available; falls back to an
embedded summary table covering 22 大阿尔克那 + 56 小阿尔克那 by suit/number.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

import entropy
from utils import ensure_utf8_stdio, json_print, warn

# --------------------------------------------------------------------------- #
# Fallback minimal tarot deck (78 cards)
# --------------------------------------------------------------------------- #

MAJOR_ARCANA: list[dict] = [
    {"number": 0,  "en": "The Fool",          "zh": "愚者",       "keywords_up": "新开始, 冒险, 自由", "keywords_rev": "鲁莽, 犹豫, 风险"},
    {"number": 1,  "en": "The Magician",      "zh": "魔术师",     "keywords_up": "创造力, 意志, 行动", "keywords_rev": "欺骗, 三心二意"},
    {"number": 2,  "en": "The High Priestess","zh": "女祭司",     "keywords_up": "直觉, 神秘, 内省", "keywords_rev": "压抑, 表象"},
    {"number": 3,  "en": "The Empress",       "zh": "皇后",       "keywords_up": "丰盛, 母性, 创造", "keywords_rev": "依赖, 占有"},
    {"number": 4,  "en": "The Emperor",       "zh": "皇帝",       "keywords_up": "权威, 秩序, 父性", "keywords_rev": "专断, 僵硬"},
    {"number": 5,  "en": "The Hierophant",    "zh": "教皇",       "keywords_up": "传统, 教化, 信仰", "keywords_rev": "反叛, 教条"},
    {"number": 6,  "en": "The Lovers",        "zh": "恋人",       "keywords_up": "结合, 抉择, 爱", "keywords_rev": "失衡, 第三者"},
    {"number": 7,  "en": "The Chariot",       "zh": "战车",       "keywords_up": "意志胜利, 前进", "keywords_rev": "失控, 受阻"},
    {"number": 8,  "en": "Strength",          "zh": "力量",       "keywords_up": "勇气, 内力, 慈悲", "keywords_rev": "自疑, 软弱"},
    {"number": 9,  "en": "The Hermit",        "zh": "隐者",       "keywords_up": "内省, 寻索, 智慧", "keywords_rev": "孤立, 退缩"},
    {"number": 10, "en": "Wheel of Fortune",  "zh": "命运之轮",   "keywords_up": "转机, 命运转动", "keywords_rev": "厄运, 循环"},
    {"number": 11, "en": "Justice",           "zh": "正义",       "keywords_up": "公正, 平衡, 因果", "keywords_rev": "偏私, 不公"},
    {"number": 12, "en": "The Hanged Man",    "zh": "倒吊人",     "keywords_up": "牺牲, 暂停, 视角转换", "keywords_rev": "徒劳, 抗拒"},
    {"number": 13, "en": "Death",             "zh": "死神",       "keywords_up": "结束, 转化, 新生", "keywords_rev": "停滞, 拒绝改变"},
    {"number": 14, "en": "Temperance",        "zh": "节制",       "keywords_up": "中庸, 调和, 平衡", "keywords_rev": "极端, 失调"},
    {"number": 15, "en": "The Devil",         "zh": "恶魔",       "keywords_up": "诱惑, 束缚, 物欲", "keywords_rev": "解脱, 觉察"},
    {"number": 16, "en": "The Tower",         "zh": "塔",         "keywords_up": "突变, 崩塌, 启示", "keywords_rev": "避免灾难, 拖延"},
    {"number": 17, "en": "The Star",          "zh": "星星",       "keywords_up": "希望, 灵感, 治愈", "keywords_rev": "失望, 自疑"},
    {"number": 18, "en": "The Moon",          "zh": "月亮",       "keywords_up": "迷茫, 潜意识, 幻象", "keywords_rev": "澄清, 释放恐惧"},
    {"number": 19, "en": "The Sun",           "zh": "太阳",       "keywords_up": "成功, 喜悦, 显化", "keywords_rev": "暂时阴霾, 过度"},
    {"number": 20, "en": "Judgement",         "zh": "审判",       "keywords_up": "觉醒, 召唤, 重生", "keywords_rev": "犹豫, 自责"},
    {"number": 21, "en": "The World",         "zh": "世界",       "keywords_up": "完成, 圆满, 整合", "keywords_rev": "未竟, 拖延"},
]


SUITS = [
    {"en": "Wands",    "zh": "权杖", "element": "火", "domain": "热情/事业/行动"},
    {"en": "Cups",     "zh": "圣杯", "element": "水", "domain": "情感/关系/直觉"},
    {"en": "Swords",   "zh": "宝剑", "element": "风", "domain": "思想/冲突/沟通"},
    {"en": "Pentacles","zh": "钱币", "element": "土", "domain": "物质/工作/财富"},
]

COURT_RANKS = [
    {"rank": "Page",   "zh": "侍从", "number": 11},
    {"rank": "Knight", "zh": "骑士", "number": 12},
    {"rank": "Queen",  "zh": "皇后", "number": 13},
    {"rank": "King",   "zh": "国王", "number": 14},
]


def build_minor_arcana() -> list[dict]:
    out: list[dict] = []
    for suit in SUITS:
        for n in range(1, 11):
            out.append({
                "suit": suit["zh"], "suit_en": suit["en"],
                "element": suit["element"], "domain": suit["domain"],
                "number": n,
                "en": f"{['Ace','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten'][n-1]} of {suit['en']}",
                "zh": f"{suit['zh']}{['一','二','三','四','五','六','七','八','九','十'][n-1]}",
                "keywords_up": f"{suit['domain']} 第{n}阶: 见详细解读",
                "keywords_rev": f"{suit['domain']} 受阻或倒置",
                # Filler, not a card meaning: shaped like text but carrying no
                # tarot content. Flagged so a reading never narrates it as one.
                "filler": True,
            })
        for court in COURT_RANKS:
            out.append({
                "filler": True,
                "suit": suit["zh"], "suit_en": suit["en"],
                "element": suit["element"], "domain": suit["domain"],
                "number": court["number"],
                "en": f"{court['rank']} of {suit['en']}",
                "zh": f"{suit['zh']}{court['zh']}",
                "keywords_up": f"{suit['domain']} 的{court['zh']}形象, 代表相应人物或品质",
                "keywords_rev": f"{suit['domain']} 该角色的负面表现",
            })
    return out


def build_full_deck() -> list[dict]:
    deck: list[dict] = []
    for m in MAJOR_ARCANA:
        deck.append({
            "arcana": "major",
            "number": m["number"],
            "en": m["en"], "zh": m["zh"],
            "suit": None, "element": None,
            "keywords_up": m["keywords_up"],
            "keywords_rev": m["keywords_rev"],
        })
    minor = build_minor_arcana()
    for c in minor:
        deck.append({
            "arcana": "minor",
            "number": c["number"],
            "en": c["en"], "zh": c["zh"],
            "suit": c["suit"], "suit_en": c["suit_en"],
            "element": c["element"], "domain": c["domain"],
            "keywords_up": c["keywords_up"],
            "keywords_rev": c["keywords_rev"],
            "filler": c.get("filler", False),
        })
    return deck


# Suit metadata for flattening the {major_arcana, minor_arcana} asset shape.
_ASSET_SUITS: dict[str, dict[str, str]] = {
    "wands": {"zh": "权杖", "en": "Wands", "element": "火", "domain": "事业/行动"},
    "cups": {"zh": "圣杯", "en": "Cups", "element": "水", "domain": "情感/关系"},
    "swords": {"zh": "宝剑", "en": "Swords", "element": "风", "domain": "思想/冲突"},
    "pentacles": {"zh": "星币", "en": "Pentacles", "element": "土", "domain": "物质/财务"},
}
_RANK_NUM: dict[str, int] = {
    "Ace": 1, "Page": 11, "Knight": 12, "Queen": 13, "King": 14,
}


def _flatten_asset_deck(data: dict) -> list[dict]:
    """Convert the {major_arcana:[...], minor_arcana:{suit:[...]}} asset into
    the flat card schema used by draw_cards. Returns [] on shape mismatch so
    the caller can fall back to the embedded deck."""
    major = data.get("major_arcana")
    minor = data.get("minor_arcana")
    if not isinstance(major, list) or not isinstance(minor, dict):
        return []
    deck: list[dict] = []
    for m in major:
        deck.append({
            "arcana": "major",
            "number": m.get("number"),
            "en": m.get("name_en"), "zh": m.get("name_zh"),
            # 18-tarot.md §4 gives the four elements to the four MINOR suits;
            # the majors have none. What the asset stores under "element" for a
            # major is astrological (12 signs + 9 planets, 21 of 22 entries) —
            # real tarot doctrine, but not an element, so it gets its own key.
            # This also makes the asset path agree with the fallback deck,
            # which already sets element None for majors.
            "suit": None, "element": None, "astro": m.get("element"),
            "keywords_up": "、".join(m.get("keywords_upright", [])) or m.get("upright_meaning", ""),
            "keywords_rev": "、".join(m.get("keywords_reversed", [])) or m.get("reversed_meaning", ""),
        })
    for suit_key, cards in minor.items():
        meta = _ASSET_SUITS.get(suit_key, {"zh": suit_key, "en": suit_key,
                                           "element": None, "domain": ""})
        for c in cards:
            rank = str(c.get("rank", ""))
            deck.append({
                "arcana": "minor",
                "number": _RANK_NUM.get(rank, int(rank) if rank.isdigit() else 0),
                "en": f"{rank} of {meta['en']}",
                "zh": c.get("name_zh"),
                "suit": meta["zh"], "suit_en": meta["en"],
                "element": meta["element"], "domain": meta["domain"],
                "keywords_up": c.get("upright", ""),
                "keywords_rev": c.get("reversed", ""),
            })
    return deck


DECK_SOURCE = {"value": "asset", "warning": None}


def load_deck() -> list[dict]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "assets", "tarot78.json"),
        os.path.join(here, "assets", "tarot78.json"),
    ]
    asset = next((p for p in candidates if os.path.exists(p)), None)
    if asset:
        try:
            with open(asset, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Asset ships as {major_arcana, minor_arcana}; flatten it.
            if isinstance(raw, dict):
                deck = _flatten_asset_deck(raw)
            elif isinstance(raw, list):
                deck = raw
            else:
                deck = []
            if len(deck) >= 78:
                DECK_SOURCE["value"] = "asset"
                DECK_SOURCE["warning"] = None
                return deck
            warn(f"tarot78.json yielded {len(deck)} cards (<78); using embedded deck")
            reason = f"tarot78.json 仅 {len(deck)} 张 (<78)"
        except Exception as e:
            warn(f"failed to load tarot78.json: {e}")
            reason = f"读取 tarot78.json 失败: {e}"
    else:
        reason = "未找到 assets/tarot78.json"
    # The embedded deck keeps the tool runnable (CONTRIBUTING requires graceful
    # degradation) but its minor arcana are filler. Say so in the payload, not
    # only on stderr, or a consumer cannot tell a degraded reading from a real
    # one — and would narrate filler text as a card meaning.
    DECK_SOURCE["value"] = "embedded_fallback"
    DECK_SOURCE["warning"] = (
        f"{reason}; 已退回内置牌库。小阿卡纳仅有占位文本, 非真实牌义, "
        f"请勿据以解读; 大阿卡纳关键词可用。"
    )
    return build_full_deck()


# --------------------------------------------------------------------------- #
# Spreads
# --------------------------------------------------------------------------- #

# 18-tarot.md §5.2 documents five equally valid three-card readings; only the
# first was reachable, so a relationship or advice question had to be forced
# into a past/present/future frame.
THREE_LAYOUTS: dict[str, list[str]] = {
    "past-present-future": ["过去", "现在", "未来"],
    "situation-action-outcome": ["情况", "行动", "结果"],
    "you-other-relationship": ["你", "对方", "关系"],
    "body-mind-spirit": ["身", "心", "灵"],
    "strength-challenge-advice": ["优势", "挑战", "建议"],
}

SPREAD_DEFS: dict[str, list[str]] = {
    "one": ["当下指引"],
    "three": ["过去", "现在", "未来"],
    "celtic": [
        "现状 (核心)", "挑战 (对照)", "潜意识/根基", "近期过去",
        "可能的未来", "近期未来", "你的态度", "外在影响", "希望与恐惧",
        "最终结果",
    ],
    # 18-tarot.md §5.7 关系牌阵: 通常7张. The five-position version shipped here
    # matched no documented layout.
    "relationship": [
        "你的感受", "对方的感受", "关系基础", "当前状态",
        "障碍", "你能做的", "关系走向",
    ],
    "daily": ["今日提示"],
}


def draw_cards(rng: random.Random, n: int, deck: list[dict]) -> list[dict]:
    indices = list(range(len(deck)))
    rng.shuffle(indices)
    drawn = []
    for i in indices[:n]:
        card = dict(deck[i])
        orientation = "upright" if rng.random() < 0.5 else "reversed"
        card["orientation"] = orientation
        card["meaning_brief"] = (
            card.get("keywords_up") if orientation == "upright"
            else card.get("keywords_rev")
        )
        drawn.append(card)
    return drawn


def position_summary(positions: list[str], cards: list[dict]) -> str:
    parts = []
    for pos, c in zip(positions, cards, strict=False):
        orient_cn = "正位" if c["orientation"] == "upright" else "逆位"
        parts.append(f"【{pos}】{c['zh']}({orient_cn})")
    return " / ".join(parts)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  spread spread_name_cn layout deck_source deck_warning question seed entropy
  cards summary

deck_source is "asset" or "embedded_fallback"; in the latter case
  deck_warning is set and cards[].filler marks stand-in text that
  must not be read as a card meaning.

cards[].element is 火/水/风/土 for the four minor suits and null for
  the majors; cards[].astro carries the major-arcana 星座/行星.

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="塔罗抽牌 (one/three/celtic/relationship/daily)",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="spread", required=True)
    for s in ["one", "three", "celtic", "relationship", "daily"]:
        ps = sub.add_parser(s, help=f"{s} 牌阵")
        ps.add_argument("--seed", type=int, default=None)
        ps.add_argument("--question", type=str, default=None)
        ps.add_argument("--entropy", choices=["system", "quantum"], default="system",
                        help="熵源: system=OS CSPRNG (默认), quantum=ANU 量子真空真随机")
        if s == "three":
            ps.add_argument("--layout", type=str, default="past-present-future",
                            help="三牌阵取法 (18-tarot.md §5.2): past-present-future | "
                                 "situation-action-outcome | you-other-relationship | "
                                 "body-mind-spirit | strength-challenge-advice")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    deck = load_deck()
    deck_source = DECK_SOURCE["value"]
    deck_warning = DECK_SOURCE["warning"]

    positions = SPREAD_DEFS.get(args.spread)
    if positions is None:
        json_print({"error": "unknown_spread", "valid": list(SPREAD_DEFS.keys())})
        return 2
    layout = getattr(args, "layout", None)
    if args.spread == "three" and layout:
        if layout not in THREE_LAYOUTS:
            json_print({"error": "unknown_layout",
                        "valid": list(THREE_LAYOUTS.keys())})
            return 2
        positions = THREE_LAYOUTS[layout]

    rng = entropy.get_rng(args.seed, args.entropy)
    cards = draw_cards(rng, len(positions), deck)

    out_cards = []
    for pos, c in zip(positions, cards, strict=False):
        out_cards.append({
            "position_name": pos,
            "card_name_zh": c.get("zh"),
            "card_name_en": c.get("en"),
            "number": c.get("number"),
            "arcana": c.get("arcana"),
            "suit": c.get("suit"),
            "element": c.get("element"),
            "astro": c.get("astro"),
            "filler": c.get("filler", False),
            "orientation": c["orientation"],
            "orientation_cn": "正位" if c["orientation"] == "upright" else "逆位",
            "meaning_brief": c.get("meaning_brief"),
        })

    out = {
        "spread": args.spread,
        "layout": layout if args.spread == "three" else None,
        "deck_source": deck_source,
        "deck_warning": deck_warning,
        "spread_name_cn": {
            "one": "单牌指引", "three": "三牌阵",
            "celtic": "凯尔特十字 (10 牌)",
            "relationship": "关系阵 (5 牌)", "daily": "每日一牌",
        }.get(args.spread),
        "question": args.question,
        "seed": args.seed,
        "entropy": entropy.describe(rng, args.entropy, args.seed),
        "cards": out_cards,
        "summary": position_summary(positions, cards),
    }
    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
