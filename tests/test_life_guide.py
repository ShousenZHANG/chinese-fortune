"""Runtime lookup of real-world references: mapped, region-gated, never TODO."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from life_guide import FOREIGN_NOTE, SCENARIO_ENTRIES, entries_for, get_article, get_entry, search

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8'))
PRESENT = {(e['section'], e['number']) for e in DATA['entries']}


def _ids(rows):
    return [r['id'] if r.get('kind') == 'article' else (r['section'], r['number']) for r in rows]


def _req(scenario, current='Australia/Sydney', **event):
    return {'current_timezone': current, 'event': {'scenario': scenario, **event}}


def test_every_mapped_entry_exists_in_the_snapshot():
    articles = {a['id'] for a in DATA['articles']}
    for scenario, ids in SCENARIO_ENTRIES.items():
        for key in ids:
            assert key in (articles if isinstance(key, str) else PRESENT), (scenario, key)


def test_every_question_gated_entry_is_mapped_and_comes_before_the_limit_can_cut_it():
    from life_guide import LIMIT, QUESTION_PATTERNS
    for key in QUESTION_PATTERNS:
        homes = [ids for ids in SCENARIO_ENTRIES.values() if key in ids]
        assert homes, key
        for ids in homes:
            # Only another gated entry, or fewer than LIMIT ungated ones, may precede it.
            before = [k for k in ids[:ids.index(key)] if k not in QUESTION_PATTERNS]
            assert len(before) < LIMIT, (key, ids)


def test_the_long_article_rides_with_a_wedding_on_the_mainland_only():
    mainland = entries_for(_req('wedding', current='Asia/Shanghai'))
    assert mainland[0].get('kind') == 'article' and mainland[0]['title'].startswith('结婚划不划算')
    sydney = entries_for(_req('wedding'))
    assert all(r.get('kind') != 'article' for r in sydney)
    assert _ids(sydney) == [(10, 9)]         # reviewed as 通用: time accounting holds anywhere


@pytest.mark.parametrize('scenario,question,current,key', [
    ('travel', '下个月去西藏哪天出发好', 'Asia/Shanghai', (13, 33)),
    ('travel', '周末去野外徒步哪天好', 'Australia/Sydney', (13, 35)),
    ('billing', '下周哪天去催款好', 'Asia/Shanghai', (9, 15)),
    ('interview', '出国打工的面试哪天好', 'Asia/Shanghai', (31, 14)),
    ('interview', '考公面试哪天好', 'Asia/Shanghai', (31, 7)),
    ('work_conversation', '哪天跟境外公司谈远程合同好', 'Asia/Shanghai', (31, 15)),
    ('exam', '下个月考公哪天报名好', 'Asia/Shanghai', (31, 7)),
])
def test_an_entry_for_part_of_the_matter_comes_when_the_question_names_that_part(scenario, question, current, key):
    payload = {**_req(scenario, current=current), 'question': question}
    assert key in _ids(entries_for(payload))
    assert key not in _ids(entries_for(_req(scenario, current=current)))


def test_relationship_advice_reviewed_as_universal_reaches_sydney():
    """10:3 and 10:5 rest on experiments, not Chinese law; 10:2 cites 治安 law."""
    assert _ids(entries_for(_req('relationship_conversation'))) == [(10, 3), (10, 5)]


def test_the_compatibility_workflow_can_ask_for_its_references():
    rows = entries_for(_req('compatibility', current='Asia/Shanghai'))
    # 10:1, 10:4 and the long article say compatibility cannot be told
    # beforehand: a verdict on 合婚 itself, so none rides with it.
    assert _ids(rows) == [(10, 18), (10, 17)]
    hehun = (ROOT / 'references' / '14-hehun.md').read_text(encoding='utf-8')
    assert 'life_guide.py --scenario compatibility' in hehun


def test_the_cli_query_takes_the_users_region():
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'life_guide.py'),
                           '--query', '押金', '--current-timezone', 'Australia/Sydney'],
                          capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)['entries']
    assert rows and all(r.get('region_note') == FOREIGN_NOTE for r in rows if r['region'] == '中国大陆')


def test_mainland_rental_rules_are_not_attached_in_sydney():
    assert entries_for(_req('moving')) == []


def test_they_are_attached_when_the_flat_is_on_the_mainland():
    rows = entries_for(_req('moving', timezone='Asia/Shanghai'))
    assert rows and {r['section'] for r in rows} == {15}


def test_travel_abroad_gets_section_21_minus_todo_entries_capped_at_three():
    rows = entries_for(_req('travel', destination_timezone='Asia/Singapore'))
    assert _ids(rows)[:2] == [(21, 1), (21, 2)]
    assert (21, 4) not in _ids(rows)          # 备注 TODO（待核实）
    assert len(rows) <= 3


def test_travel_without_a_destination_or_into_the_mainland_gets_nothing():
    assert entries_for(_req('travel')) == []
    assert entries_for(_req('travel', destination_timezone='Asia/Shanghai')) == []
    assert entries_for(_req('travel', destination_timezone='Asia/Hong_Kong')) == []


def test_an_unknown_region_attaches_nothing_region_bound():
    assert entries_for(_req('moving', current='UTC', timezone='Etc/UTC')) == []


def test_unmapped_scenarios_attach_nothing():
    assert entries_for(_req('outlook', current='Asia/Shanghai')) == []
    assert entries_for(_req('讨论社团活动', current='Asia/Shanghai')) == []


def test_an_explicit_lookup_says_when_the_rules_are_not_the_users():
    row = get_entry(15, 1, _req('moving'))
    assert row['fields']['说人话']
    assert row['region_note'] == FOREIGN_NOTE and FOREIGN_NOTE.startswith('中国大陆口径')


def test_the_excluded_entries_cannot_be_reached_by_any_route():
    for key in ((6, 15), (6, 22), (29, 12)):
        assert get_entry(*key, _req('outlook')) is None, key
    assert search('算命', {}) == []


def test_search_gives_the_same_region_note_as_an_explicit_lookup():
    rows = search('押金', _req('outlook'))
    mainland = [r for r in rows if r['region'] == '中国大陆']
    assert mainland and all(r['region_note'] == FOREIGN_NOTE for r in mainland)
    assert all('region_note' not in r for r in search('押金', _req('outlook', current='Asia/Shanghai')))


def test_search_leaves_out_entries_the_book_marks_unverified():
    """21:4 carries a TODO; the book's own rule is not to use those as conclusions."""
    assert (21, 4) not in _ids(search('医疗转运', _req('outlook')))
    assert get_entry(21, 4, _req('outlook'))['todo_note']


def test_a_trip_inside_one_country_gets_no_border_crossing_advice():
    assert entries_for(_req('travel', destination_timezone='Australia/Melbourne')) == []
    assert entries_for(_req('travel', current='Asia/Shanghai', destination_timezone='Asia/Urumqi')) == []
    # Crossing a border still does, from anywhere.
    assert entries_for(_req('travel', current='Asia/Shanghai', destination_timezone='Asia/Singapore'))
    # Where the trip starts is unknown: whether it crosses a border is unknown too.
    assert entries_for(_req('travel', current=None, destination_timezone='Asia/Singapore')) == []


def test_the_certificate_entry_is_only_for_questions_about_certificates():
    """23:8 is about paying for a 考证 course, not about 高考 or 考研."""
    exam = _req('exam', current='Asia/Shanghai')
    assert entries_for({**exam, 'question': '下周高考哪天好'}) == []
    assert entries_for({**exam, 'question': '下周考研哪天好？准考证还没下载'}) == []
    assert entries_for({**exam, 'question': '考研要带毕业证书吗'}) == []
    assert _ids(entries_for({**exam, 'question': '下个月考证哪天报名好'})) == [(23, 8)]
    assert _ids(entries_for({**exam, 'question': '想考个资格证，哪天报名好'})) == [(23, 8)]


def test_the_cli_returns_an_envelope_with_whole_entries():
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'life_guide.py'),
                           '--scenario', 'travel', '--current-timezone', 'Australia/Sydney',
                           '--destination-timezone', 'Asia/Singapore'],
                          capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data['ok'] and data['region']['region'] == '境外'
    assert data['source']['commit'].startswith('8276caec')
    assert all(set(r['fields']) >= {'说人话', '备注', '来源'} for r in data['entries'])


def test_the_cli_returns_the_long_article_whole():
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'life_guide.py'),
                           '--article', 'marriage', '--current-timezone', 'Australia/Sydney'],
                          capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    article = json.loads(proc.stdout)['entries'][0]
    assert article['text'] == DATA['articles'][0]['text'] and article['region_note'] == FOREIGN_NOTE
    assert get_article('nope', {}) is None


@pytest.mark.parametrize('scenario,question,current,key', [
    ('work_conversation', '周五远程会议跟老板谈加薪', 'Asia/Shanghai', (31, 15)),   # not income from abroad
    ('interview', '劳务派遣公司面试哪天好', 'Asia/Shanghai', (31, 14)),             # not working abroad
    ('exam', '我是公务员，考驾照科目二哪天好', 'Asia/Shanghai', (31, 7)),
    ('interview', '体制内干了十年想跳槽去私企，面试哪天好', 'Asia/Shanghai', (31, 7)),
    ('travel', '去黄土高原看窑洞哪天出发好', 'Asia/Shanghai', (13, 33)),           # about 1,000 m
    ('billing', '我欠款三万还不上，哪天去还款好', 'Asia/Shanghai', (9, 15)),        # 9:15 is for the one collecting
    ('billing', '我被催款了，哪天去还款', 'Asia/Shanghai', (9, 15)),
    ('billing', '被人要债，哪天去谈好', 'Asia/Shanghai', (9, 15)),
    ('exam', '下个月考公共英语哪天好', 'Asia/Shanghai', (31, 7)),
    ('exam', '考公司内部晋升哪天好', 'Asia/Shanghai', (31, 7)),
    ('exam', '考公安大学哪天报名好', 'Asia/Shanghai', (31, 7)),
    ('exam', '考编程二级哪天好', 'Asia/Shanghai', (31, 7)),
    ('exam', '艺考编导哪天好', 'Asia/Shanghai', (31, 7)),
    ('exam', '我是事业编，考驾照哪天好', 'Asia/Shanghai', (31, 7)),
    ('travel', '下周去青海西宁哪天出发好', 'Asia/Shanghai', (13, 33)),          # about 2,260 m
    ('travel', '从高原回上海哪天出发好', 'Asia/Shanghai', (13, 33)),
    ('travel', '那边海拔低，哪天去好', 'Asia/Shanghai', (13, 33)),
    ('work_conversation', '哪天跟海外客户开会好', 'Asia/Shanghai', (31, 15)),
    ('interview', '我有海外工作经验，面试哪天好', 'Asia/Shanghai', (31, 14)),
])
def test_a_word_that_only_looks_like_the_part_does_not_attach_it(scenario, question, current, key):
    assert key not in _ids(entries_for({**_req(scenario, current=current), 'question': question}))


@pytest.mark.parametrize('scenario,question,key', [
    ('travel', '下个月去青海湖和香格里拉哪天出发好', (13, 33)),
    ('travel', '去林芝哪天出发好', (13, 33)),
    ('travel', '去色达、理塘哪天出发好', (13, 33)),
    ('exam', '国考哪天报名好', (31, 7)),
    ('exam', '省考哪天报名好', (31, 7)),
    ('interview', '公务员面试哪天好', (31, 7)),
    ('interview', '想去国外打工，面试哪天好', (31, 14)),
    ('billing', '哪天去催收货款好', (9, 15)),
    ('work_conversation', '哪天跟境外公司谈远程合同好', (31, 15)),
])
def test_the_part_named_in_other_words_still_counts(scenario, question, key):
    payload = {**_req(scenario, current='Asia/Shanghai'), 'question': question}
    assert key in _ids(entries_for(payload)), question
