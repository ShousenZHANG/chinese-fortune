"""塔罗输出的字段语义.

18-tarot.md §4 assigns the four elements (火/水/风/土) to the four MINOR suits.
The majors have no element in the reference — what assets/tarot78.json ships
for them is astrological (12 zodiac signs + 9 planets, 21 of 22 entries), which
is legitimate tarot doctrine but is not an element and must not be published
under that name.
"""
import json
from pathlib import Path

import pytest
from conftest import run_cli

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("json")


def _cards(seed):
    return run_cli("tarot_draw.py", "three", "--seed", seed)["cards"]


def test_major_arcana_report_astro_not_element():
    """A zodiac sign is not an element; publishing 巨蟹座 in a field named
    `element` invites a reader to treat it as 风/火/水/土."""
    elements = {"火", "水", "风", "土"}
    seen_major = False
    for seed in range(1, 30):
        for c in _cards(seed):
            if c.get("arcana") == "major" or c.get("number_roman"):
                seen_major = True
                assert c.get("element") in (None, *elements), c
                if c.get("element") is not None:
                    assert c["element"] in elements, c
    assert seen_major, "no major arcana drawn across 29 seeds"


def test_asset_majors_are_astrological_not_elemental():
    d = json.loads((ROOT / "assets" / "tarot78.json").read_text(encoding="utf-8"))
    majors = d.get("major_arcana") or []
    assert len(majors) == 22
    elements = {"火", "水", "风", "土"}
    astro = [c for c in majors if c.get("element") and c["element"] not in elements]
    assert len(astro) >= 20, (
        f"only {len(astro)} majors carry astrology; the mis-naming premise "
        f"no longer holds — re-check before changing the field")


def test_minor_arcana_keep_their_element():
    """The reference DOES assign elements to the four suits, so minors must
    still carry one."""
    elements = {"火", "水", "风", "土"}
    for seed in range(1, 30):
        for c in _cards(seed):
            if c.get("suit"):
                assert c.get("element") in elements, c


# --------------------------------------------------------------------------- #
# 资产缺失时的降级必须可见 — 占位文本不得冒充牌义
# --------------------------------------------------------------------------- #

def test_output_names_its_deck_source():
    """With the asset present the reading is built from real card text."""
    d = run_cli("tarot_draw.py", "three", "--seed", 1)
    assert d["deck_source"] == "asset"
    assert not d.get("deck_warning")


def test_embedded_fallback_marks_itself_as_placeholder():
    """CONTRIBUTING requires graceful degradation when an asset is missing, but
    graceful is not the same as silent. The embedded minor arcana carry filler
    like '情感/关系/直觉 第1阶: 见详细解读' — text shaped like a meaning. It
    warns on stderr, which the JSON consumer never sees, so a degraded reading
    was indistinguishable from a real one and 解读纪律 (凡古籍无据者不妄断) would
    be violated by narrating the filler as the card's meaning.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import tarot_draw

    deck = tarot_draw.build_full_deck()
    assert len(deck) == 78
    minors = [c for c in deck if c["arcana"] == "minor"]
    assert minors and all(c.get("filler") is True for c in minors), (
        "embedded minor arcana must declare themselves filler")
    majors = [c for c in deck if c["arcana"] == "major"]
    assert all(not c.get("filler") for c in majors), (
        "the embedded majors carry real keywords and are not filler")


def test_asset_cards_are_not_flagged_placeholder():
    d = run_cli("tarot_draw.py", "three", "--seed", 2)
    assert all(not c.get("filler") for c in d["cards"])
