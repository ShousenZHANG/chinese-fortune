"""The frozen 《高性价比人生指南》 snapshot: complete, pinned, and missing only
what was excluded on purpose.

These run against the committed ``assets/life_guide.json``, not the source ZIP,
so they hold in CI. Regenerate with ``scripts/import_life_guide.py --zip``.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8'))
ENTRIES = {(e['section'], e['number']): e for e in DATA['entries']}
FIELDS = ('成本', '说人话', '收益', '证据等级', '来源', '备注')


def test_the_snapshot_is_pinned_to_a_commit_and_every_file_is_hashed():
    source = DATA['source']
    assert source['commit'] == '8276caec9508c11c5c80a65440b17895023e2fb9'
    assert source['license'] == 'Unlicense'
    assert len(source['files']) == 34            # 33 sections and the long article
    assert all(len(sha) == 64 for sha in source['files'].values())


def test_all_entries_but_the_excluded_three_are_present():
    """6:15 and 6:22 judge divination; 29:12's note lists 算命 among scams."""
    from import_life_guide import EXCLUDED
    assert set(EXCLUDED) == {(6, 15), (6, 22), (29, 12)} and all(EXCLUDED.values())
    assert len(DATA['entries']) == 605
    assert not set(EXCLUDED) & set(ENTRIES)


def test_the_shipped_file_holds_no_trace_of_the_excluded_entries():
    """Not their titles, not the references to them: the list lives in the
    importer and the docs only."""
    text = (ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8')
    for title in ('不要花钱算命、看塔罗、看星座来做决定', '为了「转运」「招财」「养人」买水晶',
                  '变故后的头三个月，凡是不可逆的大决定一律往后推'):
        assert title not in text
    assert 'excluded' not in DATA and 'cross_refs_to_excluded' not in DATA


def test_the_long_article_is_frozen_whole():
    article = DATA['articles'][0]
    assert article['id'] == 'marriage' and article['region'] == '中国大陆'
    assert article['title'].startswith('结婚划不划算') and article['text'].startswith('# 结婚划不划算')
    assert DATA['source']['files'][article['path']]
    from import_life_guide import DIVINATION_WORDS
    assert not any(w in article['text'] for w in DIVINATION_WORDS)


def test_no_kept_entry_mentions_divination():
    from import_life_guide import DIVINATION_WORDS
    for key, entry in ENTRIES.items():
        text = entry['title'] + ''.join(entry['fields'].values())
        assert not any(w in text for w in DIVINATION_WORDS), key


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


def test_a_dispute_is_the_books_own_mark_and_its_other_side_is_verbatim():
    """「争议。」 opens the other side; 「劳动争议」 or 「本身没有争议」 is not a mark."""
    assert ENTRIES[(19, 1)]['disputed'] is False       # 「争议的仲裁时效」: a labour dispute
    assert ENTRIES[(1, 7)]['disputed'] is False        # 「本身没有争议」
    other = ENTRIES[(10, 3)]['dispute']
    assert other.startswith('争议。另有研究认为') and other in ENTRIES[(10, 3)]['fields']['备注']
    for entry in DATA['entries']:
        if entry['disputed']:
            assert entry['dispute'] in entry['fields']['备注'], (entry['section'], entry['number'])
            assert len(entry['dispute']) > 10, (entry['section'], entry['number'])


def test_region_defaults_are_conservative():
    assert ENTRIES[(21, 1)]['region'] == '中国公民在境外'
    assert ENTRIES[(15, 1)]['region'] == '中国大陆'
    assert ENTRIES[(19, 3)]['region'] == '中国大陆'
    assert ENTRIES[(2, 1)]['region'] == '通用'
    assert {e['region'] for e in DATA['entries']} <= {'中国大陆', '中国公民在境外', '通用'}


@pytest.mark.parametrize('key,region', [
    # Research or physical fact: the advice holds anywhere.
    ((10, 3), '通用'), ((10, 5), '通用'), ((1, 7), '通用'), ((13, 33), '通用'), ((6, 1), '通用'),
    # The argument cites a Chinese rule, institution or hotline.
    ((5, 26), '中国大陆'), ((13, 30), '中国大陆'), ((20, 3), '中国大陆'), ((12, 1), '中国大陆'),
    ((2, 5), '中国大陆'), ((3, 19), '中国大陆'), ((22, 5), '中国大陆'),
])
def test_regions_were_reviewed_entry_by_entry(key, region):
    assert ENTRIES[key]['region'] == region


def test_every_region_override_names_a_kept_entry():
    from import_life_guide import REGION_OVERRIDES
    assert not set(REGION_OVERRIDES) - set(ENTRIES)
    assert DATA['region_policy']['overrides'] == len(REGION_OVERRIDES)
