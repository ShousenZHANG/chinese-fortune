"""Fixes from the eleventh external review (research/gpt-results-20261118/D4/fixes.json, FIX-11-01 to FIX-11-15).

Every person here is fictional; the inputs are the frozen round-11 questions (D0/questions-e12.json, C0/questions.json).
"""
from conftest import SCRIPTS, run_cli
from ziwei_calc import build_parser as ziwei_parser
from ziwei_calc import calculate_ziwei

REFS = SCRIPTS.parent / 'references'


def _ziwei(args: str) -> dict:
    return calculate_ziwei(ziwei_parser().parse_args(args.split()))


# T42: 2001-05-26 is 辛巳年闰四月初四, so the 闰月 rule moves 命宫 and with it every palace.
T42 = '--year 2001 --month 5 --day 26 --hour 19 --minute 10 --gender male --timezone Asia/Shanghai --time-standard clock'
# E07 as frozen after D0 (the birth moved to 4月2日): Beijing, the default true-solar standard.
E07 = '--year 1999 --month 4 --day 2 --hour 20 --minute 0 --gender female --city 北京'
T25 = '--year 1994 --month 12 --day 9 --hour 11 --minute 40 --gender female --longitude 114.3054 --time-standard clock'


def test_ziwei_career_first_answer_action():
    # FIX-11-02. T42 quoted 「後化貴化祿，最宜在官祿宮」 while the same passage makes 「若居廟旺」 a condition and
    # 太阳 is 陷 in 亥; the answer gave general advice with no link to the chart, and only the default 闰月 chart.
    focus = _ziwei(T42 + ' --focus-palace 官禄')['focus']
    unmet = [c for c in focus['condition_checks'] if not c['met']]
    assert any(c['star'] == '太阳' and '若居廟旺' in c['sentence'] and c['chart'] == '陷' for c in unmet)
    # 命宫 moves one palace when the 闰月 counts as the next month, so 官禄 moves from 亥 to 子 with it.
    charts = {c['condition']: c for c in focus['condition_charts']}
    assert len(charts) == 2 and sum(c['used'] for c in charts.values()) == 1
    other = next(c for c in charts.values() if not c['used'])
    assert other['branch'] == '子' and not other['same'] and '官禄宫在子' in other['say']
    career = focus['career']
    assert [step['part'] for step in career['first_answer']] == ['facts', 'undecided', 'action']
    assert '若居廟旺' in career['undecided'][0] and '闰' in career['undecided'][-1]
    action = career['action']
    assert action['text'] and '不是从这张盘推出' in action['boundary'] and '不预测' in action['boundary']

    # E07: true solar 19:42 and clock 20:00 are both 戌时, so the clock chart is the same chart; no full clause found.
    e07 = _ziwei(E07 + ' --focus-palace 官禄')['focus']
    clock = next(c for c in e07['condition_charts'] if not c['used'])
    assert clock['same'] and '戌' in clock['condition']
    assert e07['career']['action']['text'] and e07['career']['first_answer'][0]['text'].startswith('官禄宫在酉')

    # T25 fixed the clock standard and has no 闰月: no alternative chart to lay out, the action still comes.
    t25 = _ziwei(T25 + ' --focus-palace 官禄')['focus']
    assert t25['condition_charts'] == [] and t25['career']['action']['text']
    # Only the career palace gets a work action; other palaces keep their own order.
    assert 'career' not in _ziwei(T42 + ' --focus-palace 夫妻')['focus']


def test_ziwei_compact_first_answer():
    # FIX-11-03, T41/T44: limits were repeated, two tables restated the same palaces, and 武贪、廉破、科权禄 stood
    # unexplained. The focus block now carries a plain gloss for every term its own sentence uses.
    t41 = ('--year 1996 --month 2 --day 18 --hour 9 --minute 25 --gender female --timezone Asia/Shanghai '
           '--time-standard clock --focus-palace 夫妻')
    focus = _ziwei(t41)['focus']
    for term in ('对宫', '三合', '生年四化'):
        assert term in focus['terms'] and focus['terms'][term]
    assert any(label in focus['terms'] for label in ('庙', '旺', '陷', '平', '利', '得'))
    order = '\n'.join(focus['answer_order'])
    assert '最多一张表' in order and '全称' in order
    guide = (REFS / '02-ziwei.md').read_text(encoding='utf-8')
    for rule in ('最多一张表', '星名写全称', '武贪', '首次出现'):
        assert rule in guide


def _areas(reading: dict) -> dict:
    return {a['area']: a for a in reading['life_areas']['areas']}


def test_relationship_first_answer_keeps_requested_window():
    # FIX-11-10. E02 asked about 「最近」 at 2026-11-15; the tool's three-year search said 「2028 年戊申（地支申藏庚（正财））
    # 带这颗星」 and the answer had to explain that 2028 is not when he will meet someone. Day master 丁 (gold E02):
    # 2026 丙午 holds 丙 劫财 and 丁、己 in 午, no 财; 2028 戊申 holds 庚 正财, outside the asked window.
    e02 = run_cli('bazi_reading.py', '--year', 1995, '--month', 11, '--day', 2, '--hour', 21, '--minute', 50,
                  '--gender', 'male', '--city', '西安', '--current-timezone', 'Asia/Shanghai',
                  '--request-time', '2026-11-15T15:00:00Z', '--question', '最近桃花怎么样，大概什么时候能脱单？')
    love = _areas(e02)['relationship']
    assert love['timing']['window'] == [2026] and '2026 年' in love['say'] and '2028' not in love['say']
    assert [row['year'] for row in love['timing']['outside_window']] == [2028]
    assert '不当近期依据' in love['timing']['outside_note']

    # E10 asked about 2027 for every area (整体运势). Day master 戊 (gold E10): 2027 丁未 holds 乙 正官 in 未, no 财;
    # 2028 戊申 holds 壬 偏财. Before, 2028 came back in 财运 and again in 感情.
    e10 = run_cli('bazi_reading.py', '--year', 1985, '--month', 12, '--day', 25, '--hour', 6, '--minute', 0,
                  '--gender', 'male', '--city', '哈尔滨', '--as-of-year', 2027,
                  '--question', '2027年整体运势怎么样？要注意些什么？')
    areas = _areas(e10)
    assert all('2028' not in a['say'] for a in areas.values())
    assert '2027 年丁未（地支未藏乙（正官））带这颗星' in areas['career']['say']
    assert '2027 年流年天干和地支藏干都不是这颗星' in areas['wealth']['say']
    # 妻星 is the same 正财、偏财 as 财运: the second area points back instead of listing the pillars again.
    assert '见上面财运' in areas['relationship']['say'] and '子藏癸' not in areas['relationship']['say']
    assert '子藏癸' in areas['wealth']['say']


def _t46() -> dict:
    from fortune_reading import read_request
    return read_request({
        'intent': 'period', 'question': '按八字分析2026年11月3日至11月9日事业运势，软件测试准备首次向主管提出内部转岗，选沟通日期',
        'request_time': '2026-11-02T18:00:00+08:00', 'current_timezone': 'Asia/Shanghai',
        'period': {'start': '2026-11-03T00:00:00+08:00', 'end': '2026-11-10T00:00:00+08:00'},
        'event': {'scenario': '内部转岗沟通', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock', 'sect': 2},
        'participants': [{'id': 'fictional', 'confirmed': True, 'person': {
            'birth': {'year': 1989, 'month': 12, 'day': 3, 'hour': 21, 'minute': 25, 'gender': 'female',
                      'city': '常州', 'timezone': 'Asia/Shanghai', 'time_standard': 'clock', 'sect': 2},
            'time_certainty': 'exact'}}],
        'granularity': 'day', 'include_natal_reading': True, 'include_research': True})


def test_period_outlook_lead_stays_inside_the_window():
    # FIX-11-10, T46: a seven-day window in November 2026; the lead quoted 「2028 年戊申（地支申藏壬（正官））带这颗星」.
    from fortune_reading import render_answer
    result = _t46()
    natal = result['participants'][0]['natal_interpretation']['life_areas']['areas']
    assert all('2028' not in a['say'] for a in natal) and '2028' not in render_answer(result)


def test_solar_term_transition_precision():
    # FIX-11-05, T45/T46: the answers said 「11月7日17:52:05立冬」 to the second; sxtwl puts 2026 立冬 at 17:51:46,
    # 18.7 s earlier. Both round to 17:52, so the tool hands the reader the minute and keeps the table second apart.
    import pytest
    from fortune_reading import host_notes
    sxtwl = pytest.importorskip('sxtwl')
    result = _t46()
    boundary = next(b for b in result['participants'][0]['target']['boundaries'] if b['solar_term'] == '立冬')
    assert boundary['instant'].startswith('2026-11-07T17:52:05') and boundary['display'] == '11月7日 17:52'
    # 丙午年 (丙辛之岁寻庚上): 戌月戊戌, 亥月己亥 on either side of 立冬, whichever calendar times it.
    assert (boundary['month_before'], boundary['month_after']) == ('戊戌', '己亥')
    assert '分钟' in boundary['precision'] and '复核' in boundary['precision']
    jq = next(j for j in sxtwl.getJieQiByYear(2026) if j.jqIndex == 21)    # 21: 立冬 in sxtwl's 冬至-first order
    t = sxtwl.JD2DD(jq.jd)
    independent = int(t.h) * 60 + int(t.m) + (1 if t.s >= 30 else 0)
    assert f'{independent // 60}:{independent % 60:02d}' == boundary['display'].split(' ')[1]
    assert any('只说到分钟' in note for note in host_notes(result))


def test_sanyuan_explicit_xieji_and_xuanze_differ():
    # FIX-11-15, N10 named 《协纪辨方书》 but the tool only had 《选择要略》's start table. 协纪 c035:p0016 (《三元經》):
    # 男 上元起坎一、中元起巽四、下元起兑七逆行; 女 上元起中五、中元起坤二、下元起艮八顺行. Gold N10 (1990 庚午男、
    # 1992 壬申女, 下元 from 1984): 男 兑七逆 6 步 -> 坎一, 女 艮八顺 8 步 -> 兑七; 小游年 (c002:p0021/p0023) 坎 -> 兑
    # at step 5, 廉贞 (五鬼). 《选择要略》's 男下元起四宫 is the 俗误 that c035:p0017 records, so its pair differs.
    from sanyuan_hehun import match
    male, female = {'year_pillar': '庚午', 'birth_year': 1990}, {'year_pillar': '壬申', 'birth_year': 1992}
    xieji = match(male, female, source='xieji')
    assert (xieji['male']['start_palace'], xieji['male']['steps'], xieji['male']['palace']) == (7, 6, 1)
    assert (xieji['female']['start_palace'], xieji['female']['steps'], xieji['female']['palace']) == (8, 8, 7)
    assert (xieji['relation'], xieji['star']) == ('五鬼', '廉贞') and xieji['source_ids'][0] == 'xieji:c035:p0016'
    for pid in ('xieji:c035:p0016', 'xieji:c002:p0021', 'xieji:c036:p0016'):
        assert pid in xieji['say']
    assert 'book_grade' not in xieji and '不合成' in xieji['say']
    xuanze = match(male, female)
    assert xuanze['male']['start_palace'] == 4 and xuanze['relation'] != xieji['relation']
    # 下元男 from 兑七 two steps back lands on 中五; c035:p0016 does not say which palace stands in, so no result.
    centre = match({'year_pillar': '丙寅', 'birth_year': 1986}, female, source='xieji')
    assert centre['status'] == 'unsupported' and '中五' in centre['reason'] and 'relation' not in centre
    # The pair tool takes the named book from the request.
    import json
    import subprocess
    import sys
    from conftest import script_path
    request = {'a': {'year': 1990, 'month': 6, 'day': 12, 'gender': 'male', 'city': '北京'},
               'b': {'year': 1992, 'month': 9, 'day': 18, 'gender': 'female', 'city': '北京'},
               'question': '请按《协纪辨方书》所载三元九宫合婚法演示'}
    done = subprocess.run([sys.executable, str(script_path('pair_facts.py')), '--stdin'], input=json.dumps(request),
                          capture_output=True, text=True, encoding='utf-8')
    assert json.loads(done.stdout)['sanyuan_jiugong']['source'] == 'xieji'


def test_sanyuan_output_exposes_cycle_epoch():
    # FIX-11-08, N19: the answer gave start palace and steps but not 1984, the 甲子 the count starts from (gold:
    # 1444 + 3 × 180 = 1984). 1992 壬申男 counts 8 steps, 1994 甲戌女 10 steps, both from 1984.
    from sanyuan_hehun import match
    out = match({'year_pillar': '壬申', 'birth_year': 1992}, {'year_pillar': '甲戌', 'birth_year': 1994})
    assert (out['male']['epoch_year'], out['male']['steps'], out['female']['epoch_year'], out['female']['steps']) \
        == (1984, 8, 1984, 10)
    assert '1984 年甲子起' in out['say'] and 'xieji:c036:p0016' in out['say']


def test_annual_he_sanming_distinguishes_exact_claim_scope():
    # FIX-11-14, N1: the tool's note said 《三命通会》 「只说日干」, and the answer repeated it as the whole book's view.
    # The sentence takes 日干 as its subject but its example 「甲日巳年」 names the year's branch. N1 (gold): day pillar
    # 甲子, 2029 己酉: 甲己 combine, 子酉 do not.
    reading = run_cli('bazi_reading.py', '--year', 1992, '--month', 8, '--day', 16, '--hour', 10, '--minute', 20,
                      '--gender', 'male', '--city', '上海', '--as-of-year', 2026,
                      '--question', '请看看我的事业、财运和感情，2027、2028、2029年哪些干支带来相关十神')
    year = next(r for r in reading['annual_reading'] if r['year'] == 2029)
    hit = next(h for h in year['hits'] if h['id'] == 'obscured')
    assert hit['branches_combine'] is False
    note = hit['scope_note']
    assert '只说日干' not in note and '日干为主语' in note and '甲日巳年' in note and '岁支' in note
    assert '日干支合太岁干支' in note and '没有说清' in note


def _outlook(question: str, person: dict) -> dict:
    from fortune_reading import read_request
    return read_request({'current_timezone': 'Asia/Shanghai', 'request_time': '2026-11-15T04:00:00Z',
                         'participants': [{'id': 'me', 'confirmed': True, 'person': person}],
                         'question': question, 'intent': 'period', 'period': '最近',
                         'event': {'scenario': 'outlook', 'longitude': 116.4}})


T10_PERSON = {'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30, 'gender': 'male',
                        'timezone': 'Asia/Shanghai', 'longitude': 116.4}, 'time_certainty': 'exact'}
FIRST_PERSON = {'birth': {'year': 1990, 'month': 5, 'day': 15, 'hour': 10, 'minute': 0, 'gender': 'male',
                          'timezone': 'Asia/Shanghai', 'longitude': 120.16}, 'time_certainty': 'exact'}
TEN_GODS = ('正官', '七杀', '正财', '偏财', '正印', '偏印', '食神', '伤官', '比肩', '劫财')


def _first_paragraph(draft: str) -> str:
    return draft.split(chr(10) * 2)[0]


def test_career_first_answer_separates_calendar():
    # FIX-11-01, T10/T45: the career answer opened with judged/unjudged, then three scenarios and a 相主 grade appendix
    # nobody asked for. When no date is asked, the grades are not laid out; the first paragraph ends on one step.
    from fortune_reading import host_notes, render_answer
    t10 = _outlook('看看我最近的事业运。', T10_PERSON)
    draft = render_answer(t10)
    lead = _first_paragraph(draft)
    assert '没判' in lead and '不是命理结论' in lead
    assert '附：传统择日等级' not in draft and '大吉' not in draft
    assert any('不展开相主等级' in note for note in host_notes(t10))
    # T45 asks which 日段 are better: the grades come, after the lead and labelled as borrowed.
    t45 = _outlook('请用八字看近期事业倾向，说明相对有利或需谨慎的日段及依据', T10_PERSON)
    asked = render_answer(t45)
    assert asked.index('不是命理结论') < asked.index('附：传统择日等级（借用相主，不是事业预测）')


def test_first_career_plain_next_step():
    # FIX-11-07, FIRST/E01: the reply opened 「事业看正官、七杀：原局年柱午藏丁（正官）…」; readers met three terms before
    # knowing what was judged. The lead now says the relation in plain words, names the book term once in brackets,
    # and gives a real step before asking for more.
    from fortune_reading import render_answer
    draft = render_answer(_outlook('帮我看看八字，最近事业怎么样？', FIRST_PERSON))
    lead = _first_paragraph(draft)
    assert lead.startswith('事业方面')
    first_two = '。'.join(lead.split('。')[:2]).replace('书上叫正官、七杀', '')
    assert not any(term in first_two for term in TEN_GODS)
    assert lead.index('不是命理结论') < draft.index('要再往下说')
    e01 = run_cli('bazi_reading.py', '--year', 1991, '--month', 3, '--day', 8, '--hour', 7, '--minute', 30,
                  '--gender', 'female', '--city', '成都', '--as-of-year', 2026,
                  '--question', '明年想换工作，帮我看看八字，适合换吗？')
    career = _areas(e01)['career']
    assert career['lead'].startswith('事业方面') and '书上叫正官、七杀' in career['lead']
    assert '不是命理结论' in career['action']


def test_rescue_pillars_are_named_in_chinese():
    # Found while checking the T10 draft: 「你的盘里有year干己、month干丁能制住或合住日干」.
    from annual_assessment import _rescue
    chart = {'four_pillars': {'year': {'stem': '己', 'branch': '卯'}, 'month': {'stem': '丁', 'branch': '丑'},
                              'day': {'stem': '壬', 'branch': '申'}, 'hour': {'stem': '乙', 'branch': '巳'}},
             'day_master': {'stem': '壬'}}
    assert _rescue(chart) == ['年干己', '月干丁']


def test_move_first_request_answers_partial_before_clarification():
    # FIX-11-11, E05: 「12月想搬家，12月哪几天比较好？」 got only two questions back (公历还是农历、在哪个城市). A day's 干支,
    # 建除 and sourced prohibitions follow the civil date, and 1987-10-20 is 丁卯 whether read as 公历 or 农历, so the
    # month can be laid out first; 相主 ranking still waits for the place.
    import pytest
    sxtwl = pytest.importorskip('sxtwl')
    out = run_cli('huangli_query.py', '--month', '2026-12', '--question', '12月想搬家，12月哪几天比较好？',
                  '--person', '我=1987-10-20')
    assert out['scenarios'] == ['moving'] and len(out['rows']) == 31
    assert out['births'][0]['gregorian'] == out['births'][0]['lunar'] == '丁卯' and out['births'][0]['same']
    # 卯 clashes 酉: the 酉 days of December 2026 by an independent calendar.
    branches = '子丑寅卯辰巳午未申酉戌亥'
    you = [d for d in range(1, 32) if branches[sxtwl.fromSolar(2026, 12, d).getDayGZ().dz] == '酉']
    assert [int(r['date'][-2:]) for r in out['rows'] if r['clashes']] == you
    assert all(r['ganzhi'][1] == branches[sxtwl.fromSolar(2026, 12, int(r['date'][-2:])).getDayGZ().dz]
               for r in out['rows'])
    assert '不排个人先后' in out['not_ranked'] and 'grade' not in out['rows'][0]
    assert any('term_day' in r for r in out['rows'])          # 大雪 falls on 12月7日
    guide = (REFS / '00-intake.md').read_text(encoding='utf-8')
    assert 'huangli_query.py --month' in guide and '两种读法' in guide
