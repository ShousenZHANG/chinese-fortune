"""The frozen 《高性价比人生指南》 snapshot: complete, pinned, and missing only
what was excluded on purpose.

These run against the committed ``assets/life_guide.json``, not the source ZIP,
so they hold in CI. Regenerate with ``scripts/import_life_guide.py --zip``.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8'))
ENTRIES = {(e['section'], e['number']): e for e in DATA['entries']}
FIELDS = ('成本', '说人话', '收益', '证据等级', '来源', '备注')


def test_the_snapshot_is_pinned_to_a_commit_and_every_file_is_hashed():
    source = DATA['source']
    assert source['commit'] == '8276caec9508c11c5c80a65440b17895023e2fb9'
    assert source['license'] == 'Unlicense'
    assert len(source['files']) == 33
    assert all(len(sha) == 64 for sha in source['files'].values())


def test_all_entries_but_the_excluded_two_are_present():
    assert len(DATA['entries']) == 606
    assert (6, 15) not in ENTRIES and (6, 22) not in ENTRIES
    assert {(x['section'], x['number']) for x in DATA['excluded']} == {(6, 15), (6, 22)}
    assert all(x['reason'] for x in DATA['excluded'])


def test_a_keyword_that_merely_resembles_the_excluded_topic_is_kept():
    """21:4 says 医疗转运 (medical evacuation); a keyword rule on 转运 would drop it."""
    assert '转运' in ENTRIES[(21, 4)]['title']
    # 5:33 is about accounting for money spent on 手串, not about their efficacy.
    assert '手串' in ENTRIES[(5, 33)]['title']


def test_every_entry_keeps_all_six_fields_and_its_cost_tags():
    for key, entry in ENTRIES.items():
        assert all(entry['fields'][f] for f in FIELDS), key
        assert entry['grade'] in ('A', 'B', 'C'), key
        assert {'钱', '时间', '毅力', '收益', '口径'} <= set(entry['cost_tags']), key


def test_todo_and_disputed_flags_come_from_the_entry_text():
    assert ENTRIES[(21, 4)]['todo'] is True          # 备注: TODO（待核实：……费用区间）
    assert ENTRIES[(21, 1)]['todo'] is False
    assert sum(e['todo'] for e in DATA['entries']) >= 30
    assert sum(e['disputed'] for e in DATA['entries']) >= 50


def test_region_defaults_are_conservative():
    assert ENTRIES[(21, 1)]['region'] == '中国公民在境外'
    assert ENTRIES[(15, 1)]['region'] == '中国大陆'
    assert ENTRIES[(19, 3)]['region'] == '中国大陆'
    assert ENTRIES[(2, 1)]['region'] == '通用'
    assert {e['region'] for e in DATA['entries']} <= {'中国大陆', '中国公民在境外', '通用'}


def test_no_kept_entry_points_at_an_excluded_one_unreviewed():
    for flag in DATA['cross_refs_to_excluded']:
        assert flag.get('resolution'), flag
