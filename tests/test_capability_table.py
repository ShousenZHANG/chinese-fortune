"""README's coverage table is generated from the code, so it cannot drift.

It had: README still said personal day grading was unimplemented after 相主
grading shipped for ten scenarios. Regenerate with
``python scripts/fortune_rules.py --capabilities-markdown`` and paste between
the markers.
"""
from pathlib import Path

from fortune_rules import capabilities, capability_markdown

ROOT = Path(__file__).resolve().parents[1]
START, END = '<!-- capability-table:start -->', '<!-- capability-table:end -->'


def _block(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    assert START in text and END in text, path.name
    return text.split(START, 1)[1].split(END, 1)[0].strip()


def test_readme_table_is_exactly_the_generated_one():
    assert _block(ROOT / 'README.md') == capability_markdown().strip()


def test_the_table_has_a_row_per_scenario_and_says_borrowed_where_it_is():
    table = capability_markdown()
    for cap in capabilities():
        assert f"`{cap['scenario']}`" in table, cap['scenario']
    assert '借用' in table and '「出行」' in table


def test_the_readme_no_longer_says_personal_grading_is_missing():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert '还没有经完整古籍条件验证的排名算法' not in text
