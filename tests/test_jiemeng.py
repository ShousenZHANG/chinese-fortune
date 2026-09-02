"""解梦查询脚本 — 取代整读 38 KB 的 assets/jiemeng.json.

The asset carries 105 传统 interpretations that appear in no reference file
(0/105 overlap with 15-jiemeng.md's prose), so it must stay reachable — but
reading the whole file to look up one symbol costs ~10k tokens.
"""
import pytest
from conftest import run_cli

pytest.importorskip("json")


def test_lookup_known_symbol():
    d = run_cli("jiemeng_lookup.py", "--symbol", "蛇")
    assert d["symbol"] == "蛇"
    assert d["category"] == "动物"
    assert "蛇" in d["traditional"]
    assert d["modern_psychology"]
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
