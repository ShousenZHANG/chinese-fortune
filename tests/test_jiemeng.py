"""Dream topics remain reachable without inventing unsourced interpretations."""
import pytest
from conftest import run_cli

pytest.importorskip("json")


def test_lookup_known_symbol():
    d = run_cli("jiemeng_lookup.py", "--symbol", "蛇")
    assert d["symbol"] == "蛇"
    assert d["category"] == "动物"
    assert d["traditional"] is None
    assert d["modern_psychology"] is None
    assert d["interpretation_status"] == "pending_source_verification"
    assert d["source_status"]["traditional"] == "unverified_no_citation"
    assert any(s["scene"] == "蛇咬" for s in d["common_scenarios"])


def test_search_returns_partial_matches():
    d = run_cli("jiemeng_lookup.py", "--search", "水")
    assert d["count"] >= 1
    assert all("水" in m["symbol"] or "水" in m.get("category", "")
               for m in d["matches"])


def test_list_categories():
    d = run_cli("jiemeng_lookup.py", "--categories")
    assert "动物" in d["categories"]
    assert d["total_symbols"] == 105


def test_unknown_symbol_suggests_and_exits_1():
    d = run_cli("jiemeng_lookup.py", "--symbol", "不存在的梦", expect_rc=1)
    assert d["error"] == "symbol_not_found"
    assert "suggestions" in d


def test_all_topics_and_scenarios_are_indices_without_unsourced_claims():
    from jiemeng_lookup import load_symbols

    symbols = load_symbols()
    assert len(symbols) == 105
    assert len({s["symbol"] for s in symbols}) == 105
    for entry in symbols:
        assert entry["traditional"] is None
        assert entry["modern_psychology"] is None
        assert entry["interpretation_status"] == "pending_source_verification"
        assert entry["common_scenarios"]
        for scenario in entry["common_scenarios"]:
            assert scenario["scene"]
            assert scenario["meaning"] is None
            assert scenario["source_status"] == "unverified_no_citation"


@pytest.mark.parametrize("args", [("--symbol", "蛇"), ("--search", "动物")])
def test_lookup_and_search_do_not_reintroduce_predictions(args):
    import json

    d = run_cli("jiemeng_lookup.py", *args)
    output = json.dumps(d, ensure_ascii=False)
    for removed in ("主有大病", "主进财", "主生贵子", "事业腾达", "弗洛伊德", "荣格"):
        assert removed not in output
    entries = d["matches"] if "matches" in d else [d]
    assert entries
    assert all(e["traditional"] is None and e["modern_psychology"] is None for e in entries)
