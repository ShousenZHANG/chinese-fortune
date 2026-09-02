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
