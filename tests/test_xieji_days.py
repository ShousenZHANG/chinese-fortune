"""《协纪辨方书》 day prohibitions: verbatim sources, an independent oracle, and use."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from classical_search import get_passage  # noqa: E402
from xieji_days import (  # noqa: E402
    RULES,
    SCENARIO_TERMS,
    TERM_EQUIVALENCE,
    _derivation,
    prohibitions,
)

KNOWN_TABLE_DIFFERENCES = {('gui_ji', '亥', '己丑')}
LUNAR_NAMES = {'yue_po': '月破', 'si_fei': '四废', 'si_ji': '四忌', 'si_qiong': '四穷',
               'wang_wang': '往亡', 'gui_ji': '归忌'}


def _sources(rule: dict) -> list[dict]:
    return [rule['qili'], *rule['avoid'], rule['binding'], *([rule['exception']] if 'exception' in rule else [])]


def test_every_quotation_is_verbatim_in_its_passage():
    for rule in RULES:
        for source in _sources(rule):
            assert source['quote'] in get_passage(source['passage_id'])['text'], (rule['rule'], source)
    for scenario, source in TERM_EQUIVALENCE.items():
        assert source['quote'] in get_passage(source['passage_id'])['text'], scenario


def test_which_rules_reach_which_scenario_is_read_off_the_text():
    """Only a 用事 name inside the 所忌 quotation brings a rule in."""
    reach = {s: [r['label'] for r in RULES if any(term in a['quote'] for a in r['avoid'])]
             for s, term in SCENARIO_TERMS.items()}
    assert reach == {'travel': ['月破', '四廢', '往亡'],
                     'wedding': ['月破', '四廢', '四忌', '四窮', '往亡'],
                     'moving': ['月破', '四廢', '往亡', '歸忌'],
                     'business': ['月破', '四廢', '四窮']}


@pytest.mark.parametrize('scenario,passage_id', [
    ('travel', 'xieji:c011:p0026'), ('moving', 'xieji:c011:p0036'), ('wedding', 'xieji:c011:p0034')])
def test_the_book_agrees_with_itself_event_by_event(scenario, passage_id):
    """卷十一 lists each 用事's 忌 by name. Among the six rules implemented, the
    ones it names for an event must be exactly the ones 卷十 reaches it with.
    p0026 is anchored by its note 「出行同」 and its closing 巳日 (卷十「巳日忌出行」),
    p0036 by 「移徙同」, p0034 by its closing 亥日 (「亥日忌嫁娶」)."""
    avoid = get_passage(passage_id)['text'].split('忌', 1)[1]
    named = [r['label'] for r in RULES if r['label'] in avoid]
    applied = [r['label'] for r in RULES if any(SCENARIO_TERMS[scenario] in a['quote'] for a in r['avoid'])]
    assert named == applied


def test_the_derivations_match_an_independent_calendar_engine():
    """lunar_python computes the same 神煞 from its own tables. Over ten years the
    two agree on every day that no solar term cuts in two; on a term day
    lunar_python gives the whole day to the new month, the rules here judge by
    the month at the moment asked (noon here)."""
    pytest.importorskip('lunar_python')
    from lunar_python import Solar
    disagreements = []
    for offset in range(3653):
        day = datetime.date(2020, 1, 1) + datetime.timedelta(days=offset)
        noon = Solar.fromYmdHms(day.year, day.month, day.day, 12, 0, 0).getLunar()
        ganzhi, month = noon.getDayInGanZhiExact(), noon.getMonthZhiExact()
        theirs = noon.getDayXiongSha()
        for rule, name in LUNAR_NAMES.items():
            if (_derivation(rule, ganzhi, month) is not None) != (name in theirs):
                disagreements.append((day, rule))
    assert disagreements, 'expected a few term-day differences'
    cells = set()
    for day, rule in disagreements:
        edges = {Solar.fromYmdHms(day.year, day.month, day.day, h, m, 0).getLunar().getMonthZhiExact()
                 for h, m in ((0, 1), (23, 59))}
        if len(edges) == 2:
            continue
        noon = Solar.fromYmdHms(day.year, day.month, day.day, 12, 0, 0).getLunar()
        cells.add((rule, noon.getMonthZhiExact(), noon.getDayInGanZhiExact()))
    # lunar_python's table omits 歸忌 on 己丑 in the 亥 month. The 起例 「孟月丑」
    # (xieji:c006:p0058) and 卷十 carve out no such day, so the book's rule stands;
    # any other off-term difference is a new one and must be looked at.
    assert cells == KNOWN_TABLE_DIFFERENCES


def test_the_first_month_yi_hai_exception_and_the_rules_themselves():
    assert prohibitions('wedding', '乙亥', '寅') == []  # 正月乙亥：與天願併，止忌軍事
    assert [h['label'] for h in prohibitions('wedding', '乙亥', '卯')] == ['四窮']
    assert [h['label'] for h in prohibitions('business', '乙亥', '辰')] == ['四窮']
    assert prohibitions('travel', '乙亥', '卯') == []  # 四窮 does not list 行幸
    assert [h['label'] for h in prohibitions('wedding', '戊辰', '戌')] == ['月破', '往亡']
    assert [h['label'] for h in prohibitions('moving', '甲子', '戌')] == ['歸忌']
    assert prohibitions('interview', '戊辰', '戌') == []
    hit = prohibitions('wedding', '戊辰', '戌')[0]
    assert hit['quote'] in get_passage(hit['passage_id'])['text'] and '嫁娶' in hit['quote']
    assert [s['role'] for s in hit['sources']] == ['起例', '所忌', '吉神不能化解']


def _request(scenario: str, candidates: list[dict], question: str = '', **extra) -> dict:
    from test_ranking import _travel_request
    request = _travel_request(candidates, {'start': '2026-10-15', 'end': '2026-11-20'})
    request['event'] = {**request['event'], 'scenario': scenario}
    return {**request, 'question': question, **extra}


def _slot(cid: str, date: str, start: str = '09:00', end: str = '13:00') -> dict:
    return {'id': cid, 'start': f'{date}T{start}', 'end': f'{date}T{end}'}


def test_wedding_moving_and_business_are_now_screened():
    from fortune_reading import read_request, render_answer
    from fortune_rules import capabilities
    for scenario in ('wedding', 'moving', 'business'):
        cap = capabilities(scenario)[0]
        assert cap['calendar_screening'] == 'rule_based' and cap['personal_ranking'] == 'rule_based'
    wedding = read_request(_request('wedding', [_slot('oct21', '2026-10-21', '10:00', '14:00'),
                                                _slot('oct25', '2026-10-25', '10:00', '14:00')],
                                    '婚礼定哪天好？', preferences={'prefer': 'earliest'}))
    (row,) = wedding['ranking']['excluded']
    assert row['candidate_id'] == 'oct21'
    assert [(h['label'], h['passage_id']) for h in row['excluded_by']] == [
        ('月破', 'xieji:c010:p0108'), ('往亡', 'xieji:c010:p0154')]
    assert wedding['recommendation']['first_choice'] == 'oct25'
    lead = render_answer(wedding).split('\n\n')[0]
    assert '是月破日（九月月建在戌，所衝為辰），《协纪辨方书》说这天忌嫁娶，遇到吉神也照样忌' in lead
    assert '这天对你是大吉：合官' in lead  # 壬 joins 丁 (1997, 丁丑)
    # The day rules pass 辛未, but 協紀's own table bars it for someone born in 丁丑.
    own = read_request(_request('wedding', [_slot('oct24', '2026-10-24', '10:00', '14:00')], '10月24日结婚可以吗？'))
    (hit,) = own['ranking']['excluded'][0]['excluded_by']
    assert (hit['rule'], hit['birth_year'], hit['passage_id']) == ('xiangzhu_na_yin_chong', '丁丑', 'xieji:c033:p0020')
    assert render_answer(own).startswith('不行。oct24 需要避开：覆盖到辛未日，是你（丁丑年生）的纳音克冲日')
    moving = read_request(_request('moving', [_slot('oct17', '2026-10-17')], '10月17日搬家可以吗？'))
    assert moving['recommendation']['status'] == 'excluded_by_clause'
    assert render_answer(moving).startswith('不行。oct17 需要避开：覆盖到甲子日，是歸忌日（季月歸忌在子）')
    # The practical windows are cut by the moving rules too, not the travel ones.
    assert moving['excluded_segments'] and {s['label'] for s in moving['excluded_segments']} == {'歸忌'}
    business = read_request(_request('business', [_slot('nov15', '2026-11-15')]))
    assert [h['label'] for h in business['ranking']['excluded'][0]['excluded_by']] == ['月破']
    # 天地转杀 names neither 搬家 nor 开市, so it does not screen them.
    for result in (moving, business):
        assert 'yuanhai:c052:p0004' not in json.dumps(result['ranking']['excluded'])
        assert '《渊海子平·论天地转杀》' not in render_answer(result)


def test_the_almanac_table_is_flagged_where_it_contradicts_the_book():
    def run(date: str) -> dict:
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/huangli_query.py'),
                               '--date', date], capture_output=True, text=True, encoding='utf-8')
        return json.loads(proc.stdout)
    wedding = run('2020-06-02')  # 丙子, summer 四忌; the table still lists 嫁娶
    assert wedding['ganzhi']['day'] == '丙子' and '嫁娶' in wedding['yi']
    (hit,) = wedding['clause_conflicts']
    assert (hit['label'], hit['yi_item'], hit['passage_id']) == ('四忌', '嫁娶', 'xieji:c010:p0139')
    assert '不裁决' in hit['note']
    moving = run('2026-10-29')  # 丙子, 季月歸忌; the table lists 移徙
    assert [(h['label'], h['yi_item']) for h in moving['clause_conflicts']] == [('歸忌', '移徙')]


def test_a_window_crossing_one_barred_day_names_only_that_part():
    """span runs 10-17 09:00 to 10-18 18:00 over 甲子 (歸忌 for moving). The lead
    offers starts on 10-18, so it must not tell the reader to avoid span whole."""
    from fortune_reading import read_request, render_answer
    result = read_request(_request('moving', [{'id': 'span', 'start': '2026-10-17T09:00',
                                               'end': '2026-10-18T18:00'}]))
    lead = render_answer(result).split('\n\n')[0]
    assert '可选：span 2026-10-18' in lead
    assert 'span 的 2026-10-17 09:00 至 2026-10-18 00:40 这段需要避开：覆盖到甲子日，是歸忌日' in lead
