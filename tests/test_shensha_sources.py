"""Source fidelity and honest scope, separately from lookup-table consistency."""
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
from bazi_shensha import detect_all_shensha
from classical_search import get_passage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def asset():
    return json.loads((ROOT / 'assets/shensha.json').read_text(encoding='utf-8'))


def rows(asset):
    return {r['name']: r for group in ('ji_shen', 'xiong_sha') for r in asset[group]}


def hits(asset, day='甲', branches=None, stems=None, gender='male'):
    branches = branches or {'year': '亥', 'month': '巳', 'day': '未', 'hour': '卯'}
    stems = stems or {'year': '甲', 'month': '戊', 'day': day, 'hour': '庚'}
    return detect_all_shensha(asset, day, branches['day'], day + branches['day'],
                              stems['year'], branches['year'], branches['month'],
                              stems, branches, gender)


def test_every_named_rule_has_an_honest_explicit_source_state(asset):
    named = rows(asset)
    assert len(named) == 35
    assert Counter(r['source_review']['status'] for r in named.values()) == {
        'located_partial': 5, 'method_difference': 4, 'pending': 26,
    }
    for row in named.values():
        review = row['source_review']
        assert review['selected_method']
        assert review['unverified']  # none of the partial work certifies a complete method
        assert review['facsimile_status'] == 'not_checked'
        if review['status'] == 'pending':
            assert review['passages'] == []
        else:
            assert review['passages'] and review['differences']
    assert len(asset['kong_wang']) == 6
    assert all(r['source_review']['status'] == 'arithmetic_definition' for r in asset['kong_wang'])


def test_every_registered_quote_and_revision_matches_the_frozen_original(asset):
    # This checks fidelity of the registered excerpt; it does not certify its
    # historical accuracy or make the documented method differences disappear.
    for row in rows(asset).values():
        for source in row['source_review']['passages']:
            passage = get_passage(source['passage_id'])
            assert source['quote'] in passage['text'], (row['name'], source)
            for key in ('sha256', 'edition', 'source_url', 'revision', 'layer'):
                assert source[key] == passage[key], (row['name'], key)


def test_geng_tianyi_preserves_the_actual_two_book_difference(asset):
    review = rows(asset)['天乙贵人']['source_review']
    by_id = {r['passage_id']: r['quote'] for r in review['passages']}
    assert '庚辛逢马虎' == by_id['yuanhai:c024:p0004']
    assert any('甲戊庚牛羊' in r['quote'] for r in review['passages'])
    result = hits(asset, day='庚', branches={'year': '丑', 'month': '辰', 'day': '戌', 'hour': '子'})
    found = next(h for h in result if h['name'] == '天乙贵人')
    assert found['hit'] == '丑' and found['source_review']['status'] == 'method_difference'


def test_wenchang_legacy_hit_is_not_certified_by_a_different_source_table(asset):
    result = hits(asset, day='乙', branches={'year': '辰', 'month': '戌', 'day': '丑', 'hour': '午'})
    found = next(h for h in result if h['name'] == '文昌贵人')
    assert found['hit'] == '午'
    assert found['source_review']['status'] == 'method_difference'
    # The independent frozen source explicitly says 乙猪頭, hence 亥, not 午.
    assert '乙猪頭' in found['source_review']['passages'][0]['quote']


def test_taiji_soil_shen_is_recorded_as_an_unimplemented_source_difference(asset):
    result = hits(asset, day='戊', branches={'year': '申', 'month': '子', 'day': '寅', 'hour': '午'})
    assert not any(h['name'] == '太极贵人' for h in result)
    review = rows(asset)['太极贵人']['source_review']
    assert review['status'] == 'located_partial'
    assert '戊己土也喜生乎申得辰戌丑未為正庫' in [r['quote'] for r in review['passages']]


def test_xuetang_ding_you_example_is_located_without_certifying_nayin_method(asset):
    result = hits(asset, day='丁', branches={'year': '子', 'month': '寅', 'day': '巳', 'hour': '酉'})
    found = next(h for h in result if h['name'] == '学堂' and h['source_pillar'] == 'hour')
    assert found['source_review']['status'] == 'located_partial'
    assert any(r['quote'] == '如丁日酉時或酉月之類' for r in found['source_review']['passages'])


def test_ciguan_does_not_claim_nayin_sentence_proves_day_stem_table(asset):
    result = hits(asset, day='甲', branches={'year': '子', 'month': '丑', 'day': '辰', 'hour': '寅'})
    found = next(h for h in result if h['name'] == '词馆')
    assert found['hit'] == '寅' and found['source_review']['status'] == 'method_difference'
    assert '壬申納音又屬金' in found['source_review']['passages'][0]['quote']
    assert 'source_clause' not in rows(asset)['词馆']


def test_yima_huagai_jiangxing_have_independent_targets_and_precise_source_limits(asset):
    result = hits(asset)
    by_name = {h['name']: h for h in result if h['name'] in ('驿马', '华盖', '将星')}
    assert {name: (h['hit'], h['source_pillar']) for name, h in by_name.items()} == {
        '驿马': ('巳', 'month'), '华盖': ('未', 'day'), '将星': ('卯', 'hour'),
    }
    for h in by_name.values():
        assert h['source_review']['status'] == 'located_partial'
    quotes = [r['quote'] for r in by_name['驿马']['source_review']['passages']]
    assert '火局在申水局在寅金局在亥木局在己' in quotes
    assert '亥卯未馬在巳' in quotes


def test_every_hit_including_alias_and_split_names_carries_its_own_review(asset):
    result = hits(asset, day='甲', branches={'year': '戌', 'month': '亥', 'day': '子', 'hour': '午'})
    assert {'红艳', '天罗', '三奇贵人'} <= {h['name'] for h in result}
    for h in result:
        assert h['rule_name'] in rows(asset)
        assert h['source_review'] == rows(asset)[h['rule_name']]['source_review']
        assert h['interpretation_status'] == 'trigger_only'
        assert 'meaning' not in h
    # The output is independently editable; it cannot change the shared asset.
    before = deepcopy(asset)
    result[0]['source_review']['status'] = 'caller_changed'
    assert asset == before


def test_missing_review_metadata_falls_back_to_pending_not_verified(asset):
    for row in rows(asset).values():
        row.pop('source_review', None)
    result = hits(asset)
    assert result
    assert all(h['source_review']['status'] == 'pending' for h in result)


def test_deleting_unused_scanner_keeps_month_branch_targets_working(asset):
    # 卯月天德 is the branch 申, not a stem. This path did not call the
    # deleted, stem-only private scanner and must remain functional.
    result = hits(asset, branches={'year': '子', 'month': '卯', 'day': '午', 'hour': '申'})
    found = next(h for h in result if h['name'] == '天德贵人')
    assert (found['hit'], found['position']) == ('申', '时支')
