"""The book's search, ranking and decision workflow, ported onto the frozen library."""
import json
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


def test_hotlines_are_mainland_numbers_and_say_so_elsewhere():
    here = decide('我不想活了', SHANGHAI)['stop']
    away = decide('我不想活了', SYDNEY)['stop']
    assert '12356' in here['first_action'] and 'region_note' not in here
    assert '所在地' in away['region_note']


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


def test_the_fourth_tier_and_process_cost_notes_are_attached():
    surety = decide('替朋友担保签不签', SHANGHAI)['notes']
    assert any('第 ④ 档' in n for n in surety)
    lawsuit = decide('公司欠薪要不要去仲裁', SHANGHAI)['notes']
    assert any('律师费' in n for n in lawsuit)


def test_policy_sections_carry_the_date_reminder():
    rows = [r for g in decide('失业了先做什么', SHANGHAI)['do'] for r in g['entries'] if r['section'] == 7]
    assert rows and all('官方渠道' in r['policy_note'] for r in rows)


def test_mainland_rules_say_so_for_someone_elsewhere():
    rows = [r for g in decide('失业了先做什么', SYDNEY)['do'] for r in g['entries'] if r['region'] == '中国大陆']
    assert rows and all(r['region_note'].startswith('中国大陆口径') for r in rows)


def test_nothing_in_the_book_says_so():
    result = decide('火星上种土豆要注意什么', SHANGHAI)
    assert result['not_in_book'] and not result['do'] and not result['dont']


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
