"""The book's search, ranking and decision workflow, ported onto the frozen library."""
import json
import re
import subprocess
import sys
from pathlib import Path

import life_search as ls
import pytest
from life_guide import decide, glossary, search, sections

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8'))
SHANGHAI = {'current_timezone': 'Asia/Shanghai'}
SYDNEY = {'current_timezone': 'Australia/Sydney'}
ENTRIES = {(e['section'], e['number']): e for e in DATA['entries']}


def _ids(rows):
    return [(r['section'], r['number']) for r in rows]


def _do_ids(result):
    return [(r['section'], r['number']) for g in result['do'] for r in g['entries']]


# --- search, filters and ranking (the book's index.html) ---------------------

def test_every_query_word_must_hit_as_on_the_books_page():
    rows = search('押金 合同', SHANGHAI, limit=20)
    assert rows and all('押金' in ls.hay(r) and '合同' in ls.hay(r) for r in rows)


@pytest.mark.parametrize('filters,check', [
    ({'grade': {'A'}}, lambda e: e['grade'] == 'A'),
    ({'ratio': {'极高'}}, lambda e: e['ratio'] == '极高'),
    ({'lens': {'换钱'}}, lambda e: e['lens'] == '换钱'),
    ({'money': {'0'}, 'time': {'少'}}, lambda e: e['cost_tags']['钱'] == '0' and e['cost_tags']['时间'] == '少'),
    ({'will': {'否'}}, lambda e: e['cost_tags']['毅力'] == '否'),
    ({'section': {34}}, lambda e: e['section'] == 34),
    ({'disputed': True}, lambda e: e['disputed']),
])
def test_each_filter_dimension_keeps_only_matching_entries(filters, check):
    rows = search('', SHANGHAI, limit=100, filters=filters)
    assert rows and all(check(r) for r in rows)


def test_ratio_sort_is_tier_then_grade():
    rows = search('保险', SHANGHAI, limit=30, sort='ratio')
    keys = [(ls.TIER_ORDER[r['ratio']], ls.GRADE_ORDER[r['grade']]) for r in rows]
    assert keys == sorted(keys)


@pytest.mark.parametrize('question,expected', [
    ('押金不退怎么办', (15, 3)),             # no spaces: cut at question words, then scored
    ('房东不退押金', (15, 1)),
    ('每天通勤两小时值不值', (4, 18)),        # 「每天」「两小时」 are quantities, 「通勤」 the topic
    ('被裁员了能拿多少补偿', (19, 4)),
    ('孩子发烧怎么办', (20, 8)),              # the book says 体温, not 发烧
    ('对乙酰氨基酚', (34, 1)),                # new at 842e11c9
])
def test_a_plain_chinese_question_finds_the_entry_it_is_about(question, expected):
    rows = search(question, SHANGHAI, limit=5)
    assert expected in _ids(rows), [(r['section'], r['number'], r['title'][:12]) for r in rows]


def test_latin_words_and_numbers_are_searched_apart_and_whole():
    assert ls.pieces('换iPhone还是安卓') == ['iphone', '安卓']
    assert ls.pieces('孩子发烧39度') == ['孩子发烧']                 # 39 度 is a quantity
    assert ls.pieces('出国留学要准备什么') == ['出国留学']
    assert not ls._holds('iphone 手机', 'phone')                     # a Latin word counts only whole


def test_the_books_escaped_asterisk_is_searched_as_written():
    """The book writes HLA-B\\*5801; its search page unescapes it, so does this."""
    rows = search('HLA-B*5801', SHANGHAI, limit=5)
    assert (16, 9) in _ids(rows) and all(r.get('match') != 'partial' for r in rows)


def test_a_partial_hit_is_marked_so_the_host_reads_the_whole_entry():
    rows = search('押金不退', SHANGHAI)
    assert rows and all(r.get('match') == 'partial' for r in rows)


def test_question_words_and_whom_it_concerns_are_not_the_topic():
    assert ls.pieces('替朋友担保签不签') == ['替朋友担保']
    weight = ls._rarity(DATA['entries'], ['替朋友担保'])
    assert weight['担保'] > weight['朋友']


def test_applicable_drops_rules_for_another_region():
    everywhere = search('押金', SYDNEY, limit=50)
    here = search('押金', SYDNEY, limit=50, applicable=True)
    assert any(r['region'] == '中国大陆' for r in everywhere)
    assert all(r['region'] in ('通用', '境外', '中国公民在境外') for r in here)


def test_the_books_section_questions_and_glossary_are_readable():
    rows = sections()
    assert len(rows) == 34 and rows[6]['question'] and rows[6]['intro']
    assert glossary('HR')[0]['meaning'].startswith('风险比')
    assert ls.sections_for(DATA['guide']['questions'], '失业了能领什么')[0] == 7


def test_glossary_terms_are_found_in_entry_text():
    found = {t['term'] for t in ls.glossary_terms(DATA['guide']['glossary'], ['HR 0.87，95% CI 0.80–0.95'])}
    assert {'HR', '95% CI'} <= found
    assert not ls.glossary_terms(DATA['guide']['glossary'], ['THRESHOLD'])   # HR inside a word is not HR


# --- the decision workflow (skills/life-decision-guide) ----------------------

@pytest.mark.parametrize('question,kind,section', [
    ('有人倒地没呼吸怎么办', 'emergency', 13),
    ('我不想活了', 'crisis', None),
    ('我被传唤了怎么办', 'legal', 8),
])
def test_an_emergency_crisis_or_legal_process_stops_first(question, kind, section):
    result = decide(question, SHANGHAI)
    assert result['stop']['kind'] == kind
    if section:
        assert all(r['section'] == section for r in result['stop']['entries'])
    assert '性价比' not in result['stop']['first_action'] or kind == 'emergency'


# Each reviewed stop number with a word its title must still hold.
STOP_TITLES = {(1, 25): '自杀念头', (1, 32): '自杀念头', (29, 11): '12356', (8, 5): '传唤', (8, 20): '被起诉',
               (13, 1): '倒地没呼吸', (13, 2): '倒地', (13, 3): '嘴歪', (13, 4): '卒中', (13, 7): '胸口压着疼',
               (13, 8): '剧痛', (13, 11): '喘不上气', (13, 12): '大出血', (13, 15): '过敏性休克', (13, 16): '抽搐',
               (13, 18): '触电', (13, 19): '一氧化碳', (13, 20): '误服', (13, 24): '火灾', (13, 25): '溺水',
               (13, 26): '噎住', (13, 43): '噎住'}


def test_every_reviewed_stop_number_still_holds_its_entry():
    from life_decision import CRISIS_ENTRIES, EMERGENCY_ENTRIES, LEGAL_ENTRIES
    used = {k for _, keys in EMERGENCY_ENTRIES for k in keys} | set(CRISIS_ENTRIES) | set(LEGAL_ENTRIES)
    assert used == set(STOP_TITLES)
    for key, word in STOP_TITLES.items():
        assert word in ENTRIES[key]['title'], key


@pytest.mark.parametrize('question,expected', [
    ('家里着火了', [(13, 24)]),
    ('我爸突然嘴歪说话说不清', [(13, 3), (13, 4)]),
    ('孩子误服了洗衣液', [(13, 20)]),
    ('我想去死', [(1, 25), (1, 32), (29, 11)]),
    ('收到法院传票了', [(8, 5), (8, 20)]),
])
def test_a_stop_gives_only_the_entries_reviewed_for_that_situation(question, expected):
    result = decide(question, SHANGHAI)
    assert _ids(result['stop']['entries']) == expected
    assert not result['do'] and not result['dont']


@pytest.mark.parametrize('question', ['中风险理财值不值得买', '火灾险要不要买', '怎么预防心梗', '如果被起诉了怎么办'])
def test_insurance_prevention_and_hypotheticals_do_not_stop(question):
    assert 'stop' not in decide(question, SHANGHAI)


@pytest.mark.parametrize('question', ['我不想活了', '有人倒地没呼吸怎么办'])
def test_hotlines_are_given_only_to_someone_in_mainland_china(question):
    here = decide(question, SHANGHAI)['stop']['first_action']
    away = decide(question, SYDNEY)['stop']['first_action']
    assert re.search(r'先打(全国心理援助热线 12356| 120)', here)
    assert '所在地' in away and '12356' not in away and '先打 120' not in away


def test_rows_are_ranked_within_each_lens_and_never_across():
    result = decide('失业了先做什么', SHANGHAI)
    lenses = [g['lens'] for g in result['do']]
    assert len(lenses) == len(set(lenses))
    first = result['do'][0]['entries'][0]
    assert first['citation'].startswith('第 7 节第 1 条（')


@pytest.mark.parametrize('question,expected', [
    ('失业了先做什么', (7, 1)),
    ('工伤怎么赔偿', (19, 11)),
    ('替朋友担保签不签', (8, 18)),
    ('每天通勤两小时值不值', (4, 18)),
])
def test_the_reported_questions_reach_their_entries(question, expected):
    assert expected in _do_ids(decide(question, SHANGHAI))


def test_the_books_dont_list_is_set_apart():
    result = decide('保健品值不值得买', SHANGHAI)
    dont = [(r['section'], r['number']) for r in result['dont']]
    assert (6, 10) in dont and all(s == 6 for s, _ in dont)
    assert all(r['section'] != 6 for g in result['do'] for r in g['entries'])


def test_a_citation_names_the_section_entry_and_title_words():
    row = next(r for g in decide('替朋友担保签不签', SHANGHAI)['do'] for r in g['entries']
               if (r['section'], r['number']) == (8, 18))
    assert row['citation'] == '第 8 节第 18 条（借钱写清借条）'
    assert row['fields']['说人话'] and row['ratio'] and row['grade']


@pytest.mark.parametrize('question,word', [
    ('替朋友担保签不签', '第 ④ 档'), ('路上看到老人摔倒要不要扶', '第 ④ 档'),
    ('公司欠薪要不要去仲裁', '律师费'), ('公司拖欠工资三个月怎么办', '律师费'),
])
def test_the_fourth_tier_and_process_cost_notes_are_attached(question, word):
    assert any(word in n for n in decide(question, SHANGHAI)['notes'])


def test_a_citation_keeps_the_first_clause_whole():
    from life_decision import citation
    for entry in DATA['entries']:
        inside = citation(entry).split('（', 1)[1][:-1]
        assert inside and inside.count('（') == inside.count('）') and inside.count('(') == inside.count(')'), entry['title']
        assert entry['title'].startswith(inside) or len(inside) < len(entry['title'])


def test_policy_sections_carry_the_date_reminder():
    rows = [r for g in decide('失业了先做什么', SHANGHAI)['do'] for r in g['entries'] if r['section'] == 7]
    assert rows and all('官方渠道' in r['policy_note'] for r in rows)


def test_mainland_rules_say_so_for_someone_elsewhere():
    rows = [r for g in decide('失业了先做什么', SYDNEY)['do'] for r in g['entries'] if r['region'] == '中国大陆']
    assert rows and all(r['region_note'].startswith('中国大陆口径') for r in rows)


def test_nothing_in_the_book_says_so():
    result = decide('火星上种土豆要注意什么', SHANGHAI)
    assert result['not_in_book'] and not result['do'] and not result['dont']


def test_the_part_the_book_does_not_cover_is_named():
    from life_decision import render
    result = decide('换iPhone还是安卓', SHANGHAI)
    assert result['uncovered'] == ['iphone'] and not result['not_in_book']
    assert '「iphone」这部分本库没有对得上的条目' in render(result)
    assert decide('失业了先做什么', SHANGHAI)['uncovered'] == []


def test_the_source_and_both_licences_travel_with_the_data():
    from life_guide import library_source
    src = library_source()
    assert src['license'] == 'CC BY 4.0' and src['license_url'].startswith('https://creativecommons.org/')
    assert src['code_license'].startswith('MIT')
    assert DATA['source']['license_detail']['code_notice'].startswith('MIT License')
    assert decide('失业了先做什么', SHANGHAI)['source'].startswith('出处：《高性价比人生指南》，eternity4719')


def test_the_markdown_draft_cites_every_row_and_leaves_the_conclusion_to_the_host():
    from life_decision import render
    text = render(decide('替朋友担保签不签', SHANGHAI))
    assert '第 8 节第 18 条（借钱写清借条）' in text and '第 ④ 档' in text
    assert text.startswith('先做')


def test_the_cli_decides_and_lists():
    def run(*argv):
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'life_guide.py'), *argv],
                              capture_output=True, text=True, encoding='utf-8')
        assert proc.returncode == 0, proc.stderr
        return proc.stdout
    decision = json.loads(run('--decide', '失业了先做什么', '--current-timezone', 'Asia/Shanghai'))['decision']
    assert decision['do'] and decision['sections'][0]['section'] == 7
    assert '第 7 节第 1 条' in run('--decide', '失业了先做什么', '--current-timezone', 'Asia/Shanghai', '--markdown')
    assert len(json.loads(run('--sections'))['sections']) == 34
    assert len(json.loads(run('--articles'))['articles']) == 8
    assert len(json.loads(run('--term', 'all'))['glossary']) == 41
    rows = json.loads(run('--query', '保险', '--grade', 'A', '--ratio', '极高', '--sort', 'ratio', '--limit', '20'))['entries']
    assert rows and all(r['grade'] == 'A' and r['ratio'] == '极高' for r in rows)


# --- 5.3.1: what the audit of v5.3.0 found ----------------------------------

@pytest.mark.parametrize('question,kind', [
    ('我胸痛喘不上气，很危险，怎么办', 'emergency'),             # 「危险」 is not insurance
    ('同事触电昏迷了，我有保险怎么办', 'emergency'),             # another clause's background
    ('我现在胸痛喘不上气，帮我起卦看一下', 'emergency'),          # safety before divination
    ('厨房燃气泄漏了', 'emergency'), ('闻到煤气味', 'emergency'),
    ('他没有呼吸了', 'emergency'), ('怕不是心梗吧，胸口压着疼', 'emergency'),
    ('我没有胸痛也没有呼吸困难，想买保险', None), ('去年中风过，现在怎么康复', None),
    ('中风险理财值不值得买', None), ('我没被起诉', None), ('如果被起诉了怎么办', None),
])
def test_a_stop_is_judged_clause_by_clause(question, kind):
    from life_decision import stop_kind
    assert stop_kind(question) == kind


def test_a_gas_leak_gets_out_first_as_the_book_says():
    stop = decide('家里燃气泄漏了，怎么办', SHANGHAI)['stop']
    assert stop['first_action'].startswith('先把人都带到室外') and '别回去关阀门' in stop['first_action']
    assert _ids(stop['entries']) == [(13, 19)]
    away = decide('家里燃气泄漏了，怎么办', SYDNEY)['stop']['first_action']
    assert '119' not in away and '所在地' in away


@pytest.mark.parametrize('question,zone,expected', [
    ('房东不退押金，我要起诉怎么办', SHANGHAI, '第 152、164 条'),
    ('公司欠薪，我想申请劳动仲裁怎么办', SHANGHAI, '45 日内结案'),
    ('公司拖欠工资，我要起诉怎么办', SYDNEY, '有管辖权的地方'),
])
def test_the_process_note_fits_the_matter_and_the_place(question, zone, expected):
    notes = ''.join(decide(question, zone)['notes'])
    assert expected in notes and '6 个月起' not in notes


def test_an_erratum_reaches_the_row_and_the_draft():
    from life_decision import _row, render
    index = {(e['section'], e['number']): e for e in DATA['entries']}
    row = _row(ENTRIES[(19, 17)], index, '中国大陆')
    assert row['errata'][0]['note'].startswith('本库勘误（原文未改）')
    text = render({'question': '', 'do': [{'lens': '换钱', 'entries': [row]}], 'dont': [], 'articles': [],
                   'not_in_book': False, 'notes': [], 'terms': [], 'source': '出处'})
    assert '本库勘误（原文未改）' in text


def test_a_what_first_question_brings_the_articles_own_first_steps():
    result = decide('2026年10月8日被裁了，第一步做什么', SHANGHAI)
    article = next(a for a in result['articles'] if a['id'] == 'laid_off')
    assert article['first_steps']['heading'].startswith('当天')
    assert '主动辞职' in article['first_steps']['items'][0]
    assert 'first_steps' not in next(a for a in decide('被裁了能拿多少补偿', SHANGHAI)['articles'])


def test_dates_and_time_words_are_not_topics():
    assert ls.pieces('2026年10月8日被裁了，第一步做什么') == ['被裁']
    assert ls.pieces('我明天签租房合同，押金要注意什么') == ['签租房合同', '押金']


def test_rows_are_chosen_within_each_lens_not_across():
    """A tier in one 口径 never decides which rows of another get in."""
    from life_decision import _pick
    def row(lens, ratio, relevance, n):
        return ({'lens': lens, 'ratio': ratio, 'grade': 'A', 'section': 1, 'number': n}, 'partial', relevance)
    rows = [row('换钱', '极高', 10, n) for n in range(1, 8)] + [row('换寿命', '一般', 10, 20)]
    picked = _pick(rows, 7)
    assert any(r[0]['lens'] == '换寿命' for r in picked)       # not crowded out by 7 极高 in 换钱
    lenses = [r[0]['lens'] for r in picked]
    assert lenses == sorted(lenses, key=lenses.index)           # each 口径's rows together
