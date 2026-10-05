"""The frozen 《高性价比人生指南》 snapshot: the whole book at a pinned commit,
missing only what was excluded on purpose, computed the book's own way.

These run against the committed ``assets/life_guide.json``, not the source ZIP,
so they hold in CI. Regenerate with ``scripts/import_life_guide.py --zip``.
"""
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8'))
ENTRIES = {(e['section'], e['number']): e for e in DATA['entries']}
FIELDS = ('成本', '说人话', '收益', '证据等级', '来源', '备注')
# The three excluded entries: grade, tier, disputed (read from the book).
EXCLUDED_STATS = [('B', '高', False), ('B', '一般', False), ('C', '一般', False)]


def test_the_snapshot_is_pinned_to_a_commit_and_every_file_is_hashed():
    source = DATA['source']
    assert source['commit'] == '842e11c9d51fac7943e5abb4e332e29b460b5061'
    assert source['snapshot_date'] == '2026-10-05'
    assert source['license'] == 'CC BY 4.0'
    assert 'eternity4719' in source['license_detail']['attribution']
    assert '略去 3 条' in source['license_detail']['changes']
    assert len(source['files']) == 34 + 8 + 1          # sections, long articles, README
    assert all(len(sha) == 64 for sha in source['files'].values())


def test_the_whole_book_is_kept_but_the_three_excluded_entries():
    from import_life_guide import EXCLUDED
    assert set(EXCLUDED) == {(6, 15), (6, 22), (29, 12)}
    assert DATA['coverage'] == {'entries': 660, 'excluded': 3, 'sections': 34, 'articles': 8, 'errata': 9}
    assert not set(EXCLUDED) & set(ENTRIES)
    assert {e['section'] for e in DATA['entries']} == set(range(1, 35))


def test_the_counts_match_the_books_own_readme():
    """README: 663 条, A 433 / B 176 / C 54; 极高 113 / 高 301 / 一般 249;
    67 disputed, 3 TODO. Adding the three excluded entries back must give
    exactly those, which pins both the parser and the tier algorithm."""
    grades = Counter(e['grade'] for e in DATA['entries']) + Counter(g for g, _, _ in EXCLUDED_STATS)
    tiers = Counter(e['ratio'] for e in DATA['entries']) + Counter(t for _, t, _ in EXCLUDED_STATS)
    assert sum(grades.values()) == 663
    assert grades == {'A': 433, 'B': 176, 'C': 54}
    assert tiers == {'极高': 113, '高': 301, '一般': 249}
    assert sum(e['disputed'] for e in DATA['entries']) + sum(d for _, _, d in EXCLUDED_STATS) == 67
    assert sum(e['todo'] for e in DATA['entries']) == 3


@pytest.mark.parametrize('tags,score,tier', [
    ({'钱': '0', '时间': '少', '毅力': '否', '收益': '大'}, 0, '极高'),
    ({'钱': '少', '时间': '少', '毅力': '些', '收益': '大'}, 2, '高'),
    ({'钱': '多', '时间': '少', '毅力': '否', '收益': '大'}, 2, '高'),
    ({'钱': '多', '时间': '中', '毅力': '否', '收益': '大'}, 3, '一般'),
    ({'钱': '0', '时间': '少', '毅力': '否', '收益': '中'}, 0, '高'),
    ({'钱': '少', '时间': '少', '毅力': '否', '收益': '中'}, 1, '一般'),
    ({'钱': '0', '时间': '少', '毅力': '否', '收益': '小'}, 0, '一般'),
])
def test_the_tier_is_the_books_algorithm(tags, score, tier):
    """index.html: COST_W money 0/少/多, time 少/中/多, will 否/些/是 = 0/1/2;
    大: 0 → 极高, ≤2 → 高; 中: 0 → 高; the rest 一般."""
    from import_life_guide import ratio
    assert ratio(tags) == (score, tier)


def test_the_shipped_file_holds_no_trace_of_the_excluded_entries():
    """Not their titles, not section 6's overview line that lists them."""
    text = (ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8')
    for fragment in ('不要花钱算命、看塔罗、看星座来做决定', '为了「转运」「招财」「养人」买水晶',
                     '变故后的头三个月，凡是不可逆的大决定一律往后推', '花钱买运气和心情', '花钱算命看星座'):
        assert fragment not in text, fragment
    assert 'excluded' not in DATA and 'cross_refs_to_excluded' not in DATA


def test_all_eight_long_articles_are_frozen_whole():
    articles = {a['id']: a for a in DATA['articles']}
    assert set(articles) == {'marriage', 'emergency_kit', 'platform_licenses', 'stranger_emergency',
                             'night_shift', 'laid_off', 'birth_paperwork', 'chronic_diagnosis'}
    assert articles['marriage']['title'].startswith('结婚划不划算')
    assert articles['night_shift']['region'] == '通用'          # research only
    assert articles['laid_off']['region'] == '中国大陆'
    from import_life_guide import DIVINATION_WORDS
    for a in articles.values():
        assert DATA['source']['files'][a['path']]
        assert not any(w in a['text'] for w in DIVINATION_WORDS), a['id']


def test_each_section_keeps_its_question_and_intro():
    questions = {q['section']: q['question'] for q in DATA['guide']['questions']}
    assert set(questions) == set(range(1, 35))
    assert '能领什么' in questions[7]
    intros = {s['section']: s['intro'] for s in DATA['sections']}
    assert all(intros[s] for s in (1, 6, 29, 34))
    assert any('保健品和补剂' in p for p in intros[6])


def test_the_readme_method_and_glossary_are_kept():
    guide = DATA['guide']
    assert len(guide['glossary']) == 41
    terms = {g['term'] for g in guide['glossary']}
    assert {'HR', 'RR', '总死亡率'} <= terms
    assert '不同口径之间不做比较' in guide['ratio'] and '陌生人' in guide['resources']
    assert '荟萃分析' in guide['grades']


def test_cross_references_resolve_to_kept_entries():
    """Resolved the book's way (tools/check-refs.mjs, 1260 references at this
    commit); the ones pointing at an excluded entry were reviewed and dropped."""
    kept = set(ENTRIES)
    refs = [tuple(r) for e in DATA['entries'] for r in e['refs']]
    refs += [tuple(r) for s in DATA['sections'] for r in s['refs']]
    refs += [tuple(r) for a in DATA['articles'] for r in a['refs']]
    assert len(refs) > 1000 and set(refs) <= kept
    # 8:18 (借条和担保) points at 8:45 (AB 贷); 19:4 (被裁算 N) at 19:18 (离职补偿的个税).
    assert [8, 45] in ENTRIES[(8, 18)]['refs'] and [19, 18] in ENTRIES[(19, 4)]['refs']


def test_no_kept_text_mentions_divination():
    from import_life_guide import DIVINATION_WORDS
    for key, entry in ENTRIES.items():
        text = entry['title'] + ''.join(entry['fields'].values())
        assert not any(w in text for w in DIVINATION_WORDS), key
    for s in DATA['sections']:
        assert not any(w in ''.join(s['intro']) for w in DIVINATION_WORDS), s['section']


def test_a_keyword_that_merely_resembles_the_excluded_topic_is_kept():
    """21:4 says 医疗转运 (medical evacuation); a keyword rule on 转运 would drop it."""
    assert '转运' in ENTRIES[(21, 4)]['title']


def test_every_entry_keeps_all_six_fields_and_its_cost_tags():
    for key, entry in ENTRIES.items():
        assert all(entry['fields'][f] for f in FIELDS), key
        assert entry['grade'] in ('A', 'B', 'C'), key
        assert {'钱', '时间', '毅力', '收益', '口径'} <= set(entry['cost_tags']), key
        assert entry['lens'] in ('换寿命', '换钱', '换时间精力', '换人身自由'), key


def test_todo_and_disputed_flags_follow_the_book():
    """TODO: 待核实 or TODO in 来源/收益/备注/成本. Disputed: 备注 opens with 争议."""
    assert ENTRIES[(21, 4)]['todo'] is False             # resolved upstream since 8276caec
    assert ENTRIES[(31, 6)]['todo'] is True
    assert ENTRIES[(19, 1)]['disputed'] is False         # 「争议的仲裁时效」: a labour dispute
    assert ENTRIES[(1, 7)]['disputed'] is False          # 「本身没有争议」
    other = ENTRIES[(10, 3)]['dispute']
    assert other.startswith('争议。另有研究认为') and other in ENTRIES[(10, 3)]['fields']['备注']
    for entry in DATA['entries']:
        assert entry['disputed'] == entry['fields']['备注'].lstrip().startswith('争议')
        if entry['disputed']:
            assert entry['dispute'] in entry['fields']['备注'], (entry['section'], entry['number'])
            assert len(entry['dispute']) > 10, (entry['section'], entry['number'])


def test_region_defaults_are_conservative():
    assert ENTRIES[(21, 1)]['region'] == '中国公民在境外'
    assert ENTRIES[(15, 1)]['region'] == '中国大陆'
    assert ENTRIES[(2, 1)]['region'] == '通用'
    assert {e['region'] for e in DATA['entries']} <= {'中国大陆', '中国公民在境外', '通用'}


@pytest.mark.parametrize('key,region', [
    # Research or physical fact: the advice holds anywhere.
    ((10, 3), '通用'), ((10, 5), '通用'), ((1, 7), '通用'), ((13, 33), '通用'), ((6, 1), '通用'),
    ((2, 3), '通用'), ((33, 5), '通用'),
    # Second review: a Chinese name in passing is not the argument.
    ((3, 22), '通用'), ((3, 24), '通用'), ((4, 13), '通用'),
    # The argument cites a Chinese rule, institution or hotline.
    ((5, 26), '中国大陆'), ((13, 30), '中国大陆'), ((20, 3), '中国大陆'), ((12, 1), '中国大陆'),
    ((2, 5), '中国大陆'), ((3, 18), '中国大陆'), ((14, 4), '中国大陆'), ((27, 13), '中国大陆'),
    ((5, 11), '中国大陆'), ((28, 6), '中国大陆'), ((1, 26), '中国大陆'), ((6, 18), '中国大陆'),
    # New at 842e11c9, reviewed: pharmacology is universal, a label dose is not.
    ((34, 7), '通用'), ((34, 8), '通用'), ((1, 39), '通用'), ((34, 1), '中国大陆'), ((34, 2), '中国大陆'),
    ((2, 40), '中国大陆'), ((5, 20), '中国大陆'),
])
def test_regions_were_reviewed_entry_by_entry(key, region):
    assert ENTRIES[key]['region'] == region


def test_every_review_names_a_kept_title():
    """Reviews are keyed by title; a title the book changed fails here, not
    silently on another entry."""
    from life_guide_review import DISPUTE_SENTENCES, REGION
    titles = {e['title'] for e in DATA['entries']}
    assert set(REGION) <= titles and set(DISPUTE_SENTENCES) <= titles
    assert DATA['region_policy']['overrides'] == len(REGION)


@pytest.mark.parametrize('key,reaches', [
    ((3, 9), '目前没有可靠证据说得清'),            # past a cross reference
    ((16, 1), '连安慰剂（假药）都吃满的人死亡率也低'),
    ((5, 17), '这个结论可能下得过重了'),
    ((6, 1), '吃的人得癌症的比例低约 8%'),
    ((1, 19), '肠镜对死亡率的好处以前被高估过'),
    ((2, 9), '吃太少和吃太多都不好'),
    ((2, 15), '它仍然只是跟踪记录'),
    ((2, 28), '三是按通行的证据打分法'),
    ((5, 14), '会短暂失守'),
    ((13, 30), '符合抗震设防要求的建筑内'),
])
def test_a_lead_in_dispute_is_quoted_until_it_states_the_other_side(key, reaches):
    dispute = ENTRIES[key]['dispute']
    assert reaches in dispute and dispute in ENTRIES[key]['fields']['备注'], dispute


def test_an_erratum_sits_beside_the_entry_and_leaves_its_text_alone():
    """「一审普通程序 6 个月起」 against 民事诉讼法 第 152 条 (a limit, not a start)."""
    marked = [e for e in DATA['entries'] if e.get('errata')]
    assert len(marked) == 9
    for entry in marked:
        erratum = entry['errata'][0]
        assert all('6 个月起' in entry['fields'][f] for f in erratum['fields'])   # the book's words stay
        assert '6 个月内审结' in erratum['note'] and '6 个月起' not in erratum['note']
        assert '第 152、164 条' in erratum['source'] and erratum['source'].count('https://') == 1
    assert any('6 个月内审结' in v for v in ENTRIES[(8, 45)]['fields'].values()) and not ENTRIES[(8, 45)].get('errata')


def test_an_erratum_whose_wrong_words_are_gone_must_be_reviewed_again():
    import pytest
    from import_life_guide import _attach_errata
    from life_guide_review import ERRATA
    title = next(iter(ERRATA))
    fields = dict.fromkeys(('成本', '说人话', '收益', '证据等级', '来源', '备注'), '')
    with pytest.raises(ValueError, match='须重审'):
        _attach_errata([{'title': title, 'fields': fields}], check_reviews=True)
