"""Optional methods distinguish observed structures from personal verdicts."""
from conftest import run_cli
from tarot_draw import build_full_deck, load_deck
from ziwei_patterns import detect_patterns
from ziwei_stars import BRIGHTNESS_NOTE


def test_partial_jiyuetongliang_remains_a_visible_candidate():
    positions = {"子": ["天机", "太阴", "天同"]}
    patterns = detect_patterns("子", positions, positions, [], {})
    candidate = next(p for p in patterns if p["name"] == "机月同梁")
    assert "3/4" in candidate["evidence"]
    assert candidate["status"] == "candidate_only"
    assert candidate["source_status"] == "classical_conditions_not_verified"
    assert not {"type", "meaning", "score", "personal_verdict"} & candidate.keys()


def test_ziwei_candidates_report_actual_position_without_fortune_tier():
    result = run_cli("ziwei_calc.py", "--year", 1977, "--month", 11,
                     "--day", 2, "--hour", 22, "--gender", "male")
    assert result["patterns"]
    assert BRIGHTNESS_NOTE in result["notes"]
    assert all("形性赋" not in note for note in result["notes"])
    for pattern in result["patterns"]:
        assert pattern["evidence"]
        assert pattern["status"] == "candidate_only"
        assert pattern["recognition_basis"] == "project_star_combination"
        assert "type" not in pattern and "meaning" not in pattern


def test_asset_and_fallback_minor_names_agree_with_their_suits():
    expected = {"Wands": "权杖", "Cups": "圣杯", "Swords": "宝剑",
                "Pentacles": "钱币"}
    for deck in (load_deck(), build_full_deck()):
        minors = [c for c in deck if c["arcana"] == "minor"]
        assert len(minors) == 56
        for card in minors:
            assert card["suit"] == expected[card["suit_en"]]
            assert card["zh"].startswith(card["suit"])


def test_tarot_spread_label_counts_actual_cards_and_states_symbolic_scope():
    result = run_cli("tarot_draw.py", "relationship", "--seed", 7)
    assert result["spread_name_cn"] == "关系阵 (7 牌)"
    assert len(result["cards"]) == 7
    assert result["interpretation_status"] == "symbolic_prompt_only"
    assert "牌位" in result["interpretation_note"]
