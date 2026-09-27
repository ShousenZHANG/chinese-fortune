"""相主 (协纪辨方书卷三十三): every rule is a sentence of the passage, every
table is a passage, and the passage's own worked examples come out as it says."""
import json
import re
from datetime import date
from pathlib import Path

import pytest
from classical_search import get_passage
from xiangzhu import (
    GRADES,
    GUI_REN_CONTESTED,
    NA_YIN_CLASH,
    PASSAGE,
    QUOTES,
    TABLES,
    assess_day,
    assess_people,
    birth_year_of,
    date_pillars,
    na_yin_row,
    personal_calendar,
    pillar_factors,
    prohibitions,
)

ROOT = Path(__file__).resolve().parents[1]


def _text(passage_id: str) -> str:
    return get_passage(passage_id)['text'].replace('〔字形SK3295：㸃〕', '㸃')


def _rules(birth: str, day: str, **pillars: str) -> set[str]:
    return {f['rule'] for f in assess_day(birth, {'day': day, **pillars})['factors']}


def test_every_quote_is_verbatim():
    text = _text(PASSAGE)
    for key, quote in QUOTES.items():
        assert quote in text, key
    assert '從來皆論生年不論生日' in QUOTES['method']


def test_the_na_yin_table_is_the_passage_table():
    text = _text(PASSAGE)
    table = text[text.index('故不列表'):]
    pairs = re.findall(r'([甲乙丙丁戊己庚辛壬癸][子丑寅夘辰巳午未申酉戌亥])忌([甲乙丙丁戊己庚辛壬癸][子丑寅夘辰巳午未申酉戌亥])',
                       table)
    assert {a.replace('夘', '卯'): b.replace('夘', '卯') for a, b in pairs} == NA_YIN_CLASH
    assert len(NA_YIN_CLASH) == 60


def test_the_positional_tables_are_their_passages():
    lu_id, lu = TABLES['lu']
    assert '，'.join(f'{s}禄在{b}' for s, b in lu.items() if s not in '丙戊丁己') in _text(lu_id).replace(
        '丙戊禄在巳，丁己禄在午，', '')
    assert '丙戊禄在巳，丁己禄在午' in _text(lu_id)
    ma_id, ma = TABLES['yi_ma']
    for group in ('申子辰', '寅午戌', '巳酉丑', '亥卯未'):
        assert f'{group}马在{ma[group[0]]}' in _text(ma_id)
    sheng_id, sheng = TABLES['chang_sheng']
    assert '金生巳，木生亥，火生寅，水土生申' in _text(sheng_id)
    assert sheng == {'甲': '亥', '丙': '寅', '戊': '申', '庚': '巳', '壬': '申'}
    blade_id, blade = TABLES['yang_ren']
    assert '惟甲丙戊庚壬五陽干有刃' in _text(blade_id) and '陰干無刃' in _text(blade_id)
    # 「刃者…即禄前一位」
    order = '子丑寅卯辰巳午未申酉戌亥'
    assert all(order[(order.index(lu[s]) + 1) % 12] == b for s, b in blade.items())
    gui_id, gui = TABLES['gui_ren']
    shensha = json.loads((ROOT / 'assets' / 'shensha.json').read_text(encoding='utf-8'))
    reviewed = next(x for x in shensha['ji_shen'] if x['name'] == '天乙贵人')
    assert {s: ''.join(b) for s, b in reviewed['qi_fa_table'].items() if s != '庚'} == gui
    assert gui_id in {p['passage_id'] for p in reviewed['source_review']['passages']}
    # 26-precedence.md keeps 天乙貴人 as a dispute; the two readings part only at 庚.
    for passage_id, _branches, quote in GUI_REN_CONTESTED["庚"]:
        assert quote in _text(passage_id)
    assert '甲戊兼牛羊' in _text('yuanhai:c024:p0003')
    precedence = (ROOT / 'references' / '26-precedence.md').read_text(encoding='utf-8')
    assert '天乙贵人起法' in precedence and '并列' in precedence


def test_a_disputed_noble_is_named_and_not_counted():
    for day in ('辛丑', '己未', '壬午', '甲寅'):
        factors = assess_day('庚辰', {'day': day})['factors']
        contested = [f for f in factors if f['rule'] == 'ming_gui_contested']
        assert contested and contested[0]['polarity'] == 'note', day
        assert 'ming_gui' not in {f['rule'] for f in factors}
        assert '《三命通会》' in contested[0]['plain'] and '《渊海子平》' in contested[0]['plain']
    # 辛 reads 午寅 in both books.
    assert 'ming_gui' in _rules('辛亥', '壬午')


def test_the_passage_examples_come_out_as_it_says():
    # 楊筠松為俞侍御修陽宅：乙亥生，用庚寅年庚辰月庚寅日 —— 「取乙與庚合合官格也」
    yang = assess_day('乙亥', {'year': '庚寅', 'month': '庚辰', 'day': '庚寅'})
    assert 'he_guan' in {f['rule'] for f in yang['factors']} and yang['grade'] == '大吉'
    # 曾文辿為壬午修主取四丁未：「丁與壬合合財格也又午與未合天地合格也」
    assert {'he_cai', 'tian_di_he'} <= _rules('壬午', '丁未')
    # 「一戊午年生人扵丙子造…是非不停皆衝生年也」, and the table: 戊午忌丙子
    assert assess_day('戊午', {'day': '丙子'})['grade'] == '凶'
    # 「甲子忌庚午」天尅地衝 and 「甲子忌甲午」天比地衝
    assert assess_day('甲子', {'day': '庚午'})['grade'] == '大凶'
    assert _rules('甲子', '甲午') == {'tian_bi_di_chong'}
    # 「乙夘生人造屋用辛丑年辛夘月後大不吉乙以辛為七煞也」: the year and month
    # already hold two points; a 辛 day is a third.
    sha = assess_day('乙卯', {'year': '辛丑', 'month': '辛卯', 'day': '辛巳'})
    assert sha['grade'] == '凶' and 'qi_sha_two' in {f['rule'] for f in sha['factors']}
    # The year and month alone make it 「後大不吉」, even on a 命貴人 day.
    other = assess_day('乙卯', {'year': '辛丑', 'month': '辛卯', 'day': '丙子'})
    assert other['grade'] == '凶' and other['pillar_grade'] == '大吉'
    assert [f['rule'] for f in other['factors'] if f['polarity'] == 'bad'] == ['qi_sha_two']
    # A 辛卯 day is 命禄 (大吉) and one 七煞: alone it is 吉 at best, whatever else counts.
    lu_day = assess_day('乙卯', {'year': '辛丑', 'month': '戊子', 'day': '辛卯'})
    assert (lu_day['grade'], lu_day['pillar_grade']) == ('凶', '吉')
    # 「馬有必不可用者如寅以申為馬…衝寅命凶」
    horse = assess_day('甲寅', {'day': '壬申'})
    assert 'yi_ma' not in {f['rule'] for f in horse['factors']} and horse['grade'] == '凶'
    # 「甲命以丙為食神丙禄在巳」
    assert 'shi_lu' in _rules('甲辰', '己巳')
    # 「如甲命宜四癸乙命宜四壬」
    assert 'zheng_yin' in _rules('甲辰', '癸丑') and 'zheng_yin' in _rules('乙丑', '壬辰')


@pytest.mark.parametrize('birth,day,grade', [
    ('丙申', '戊寅', '小凶'), ('丁酉', '己卯', '小凶'),   # 申酉命遇寅卯衝：止主是非
    ('甲子', '戊午', '凶'),                            # 亥子命遇巳午, but 甲子忌戊午 is in the 納音 table
    ('丙子', '甲午', '小凶'), ('丁亥', '己巳', '凶'),     # 丁亥忌己巳 is also in the table
    ('乙亥', '丁巳', '小凶'),
    ('丙寅', '戊申', '凶'), ('丁卯', '己酉', '凶'),       # 西衝東命：凶莫堪
    ('甲午', '丙子', '凶'), ('乙巳', '丁亥', '凶'),       # 北衝南命
    ('戊辰', '庚戌', '凶'), ('己丑', '辛未', '小凶'),     # 土衝土略輕; 戊辰忌庚戌 is in the table
])
def test_clash_weight_follows_the_direction(birth, day, grade):
    assert assess_day(birth, {'day': day})['grade'] == grade


def test_a_light_clash_is_still_bad_when_the_year_makes_it():
    """「如辰戌丑未命遇衝…略輕…然太嵗衝之亦凶」"""
    day = assess_day('己丑', {'year': '辛未', 'month': '戊戌', 'day': '甲子'})
    context = day['context']
    assert context['year']['grade'] == '凶'
    assert context['year']['factors'][0]['quote'] == QUOTES['year_tu']
    # 甲子 is 己's 合官 (大吉) as a day, but the year's clash stands over it.
    assert day['pillar_grade'] == '大吉' and day['grade'] == '凶'
    assert assess_day('己丑', {'day': '辛未'})['grade'] == '小凶'


def test_bad_outranks_good_and_the_grades_are_ordered():
    # 丁丑忌辛未 (納音 table) though 辛 is 丁's 偏財.
    mixed = assess_day('丁丑', {'day': '辛未'})
    assert mixed['grade'] == '凶' and {'na_yin_chong', 'cai_guan'} <= {f['rule'] for f in mixed['factors']}
    assert GRADES == ('大吉', '吉', '平', '小凶', '凶', '大凶')


def test_one_seven_killing_is_tolerable_only_beside_a_good_year_and_month():
    """「或年月利而干係七煞一㸃可也」"""
    good = assess_day('丁丑', {'year': '丙午', 'month': '戊戌', 'day': '癸亥'})
    assert good['grade'] == '吉' and 'qi_sha_one' in {f['rule'] for f in good['factors']}
    # 乙未 clashes 丑 (略輕) without being a 七煞 itself: the month is against the
    # person, so the time is no better than the month.
    bad_month = assess_day('丁丑', {'year': '丙午', 'month': '乙未', 'day': '癸亥'})
    assert bad_month['context']['month']['grade'] == '小凶' and bad_month['grade'] == '小凶'
    # A 七煞 month makes the 七煞 day a second point: 「若至二㸃必凶」.
    assert assess_day('丁丑', {'year': '丙午', 'month': '癸巳', 'day': '癸亥'})['grade'] == '凶'
    # 癸未 is also 天尅地衝 for 丁丑, which is 最凶 in the month as in the day.
    assert assess_day('丁丑', {'year': '丙午', 'month': '癸未', 'day': '癸亥'})['grade'] == '大凶'


def test_repeats_the_passage_allows_once_or_twice():
    assert 'jie_cai_many' in _rules('己巳', '戊辰', year='戊子', month='戊午')
    assert 'jie_cai_many' not in _rules('己巳', '戊辰', year='戊子', month='甲子')
    assert 'yang_ren_many' in _rules('甲子', '丁卯', year='辛卯', month='乙卯')


def test_ben_ming_ri_follows_xieji_and_names_the_other_book():
    factors = assess_day('己巳', {'day': '己巳'})['factors']
    assert {f['rule'] for f in factors} == {'bi_jian', 'ben_ming_ri'}
    note = next(f for f in factors if f['rule'] == 'ben_ming_ri')
    assert note['other'] == 'xuanze:c003:p0607' and '本命日' in _text(note['other'])


def test_a_clashing_branch_brings_no_lu_or_noble():
    # 甲申's 禄 is 寅, which clashes 申.
    assert _rules('甲申', '丙寅') == {'chong_light'}


def test_every_factor_explains_itself_with_a_real_passage():
    seen = set()
    for birth in ('甲子', '丁丑', '庚寅', '癸卯', '戊辰', '辛巳', '壬午', '乙未', '丙申', '己酉', '庚戌', '癸亥'):
        for day in ('甲子', '乙丑', '丙寅', '丁卯', '戊辰', '己巳', '庚午', '辛未', '壬申', '癸酉', '甲戌', '乙亥',
                    '丙子', '丁丑', '戊寅', '己卯', '庚辰', '辛巳', '壬午', '癸未'):
            for factor in pillar_factors(birth, day):
                seen.add(factor['rule'])
                # The 纳音 prohibition quotes its own table row, which carries the 忌
                # the rule's sentence loses to an unencoded glyph; it is checked verbatim
                # for every birth year in test_answer_fidelity.
                assert factor['quote'] in QUOTES.values() or (
                    factor['rule'] == 'na_yin_chong' and factor['quote'] == na_yin_row(birth, day))
                # A disputed table names the two books instead of 协纪.
                assert factor['plain'] and ('协纪' in factor['plain'] or factor['rule'] == 'ming_gui_contested')
                if 'table' in factor:
                    assert _text(factor['table'])
    assert {'he_guan', 'he_cai', 'ming_lu', 'ming_gui', 'shi_lu', 'bi_jian', 'zheng_yin', 'cai_guan',
            'chang_sheng', 'yi_ma', 'liu_he', 'san_he', 'chong', 'chong_light', 'tian_ke_di_chong',
            'tian_bi_di_chong', 'na_yin_chong', 'qi_sha_one'} <= seen


@pytest.mark.parametrize('day,zone,expected', [
    (date(2026, 10, 14), 'Asia/Shanghai', {'year': '丙午', 'month': '戊戌', 'day': '辛酉'}),
    (date(2026, 10, 7), 'Asia/Shanghai', {'year': '丙午', 'month': '丁酉', 'day': '甲寅'}),
    # The day before 立春 2026: still 乙巳 year and 己丑 month. 253 days before 辛酉 is 戊申.
    (date(2026, 2, 3), 'Asia/Shanghai', {'year': '乙巳', 'month': '己丑', 'day': '戊申'}),
    (date(2026, 10, 14), 'America/Los_Angeles', {'year': '丙午', 'month': '戊戌', 'day': '辛酉'}),
])
def test_date_pillars_follow_the_local_date_and_the_term_tables(day, zone, expected):
    assert date_pillars(day, zone) == expected


def test_birth_year_comes_only_from_a_settled_year_pillar():
    assert birth_year_of({'four_pillars': {'year': {'stem': '丁', 'branch': '丑'}}}) == '丁丑'
    assert birth_year_of({'four_pillars': {'year': {'status': '待定'}}}) is None
    assert birth_year_of({}) is None


def _unknown_near_lichun(**extra):
    from fortune_reading import read_request
    return read_request({
        'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-17T02:00:00Z', 'intent': 'period',
        'period': {'start': '2026-10-12', 'end': '2026-10-19'}, 'event': {'scenario': 'outlook', 'longitude': 121.47},
        'question': '下周哪天对我好？', **extra,
        'participants': [{'id': 'me', 'confirmed': True, 'person': {
            'birth': {'year': 2000, 'month': 2, 'day': 4, 'gender': 'male', 'timezone': 'Asia/Shanghai',
                      'longitude': 120.64}, 'time_certainty': 'unknown'}}]})


def test_an_unsettled_birth_year_is_graded_both_ways_and_the_worse_stands():
    """Born on 立春 2000 without a time: 己卯 or 庚辰. A day counts as good only
    when it is good for both, and is avoided when either year is against it."""
    from fortune_reading import render_answer
    result = _unknown_near_lichun()
    assert result['recommendation']['status'] == 'personal_calendar'
    assert 'birth_year_required' not in {b['code'] for b in result['decision_blockers']}
    for entry in result['personal_calendar']['entries']:
        years = {p['birth_year']: p['days'][0]['grade'] for p in entry['people']}
        assert set(years) == {'己卯', '庚辰'}
        assert entry['grade'] == max(years.values(), key=GRADES.index)
    text = render_answer(result)
    assert text.startswith('按你出生那年的干支（己卯或庚辰，生在立春前后，按较差的算）看')
    assert '按己卯年：' in text and '按庚辰年：' in text


def test_no_birth_year_at_all_says_what_is_missing(monkeypatch):
    import fortune_ranking
    import fortune_selection
    monkeypatch.setattr(fortune_ranking.xiangzhu, 'birth_years_of', lambda natal: [])
    monkeypatch.setattr(fortune_selection.xiangzhu, 'birth_years_of', lambda natal: [])
    from fortune_reading import render_answer
    result = _unknown_near_lichun()
    assert result['personal_calendar']['status'] == 'birth_year_unknown'
    assert 'birth_year_required' in {b['code'] for b in result['decision_blockers']}
    lead = render_answer(result).split('\n\n')[0]
    assert lead.startswith('哪天对你好坏要按你出生那一年的干支看，但你的出生年柱还没定下来')
    assert '没有这一类' not in lead


def test_a_bad_year_is_not_hidden_by_a_good_day():
    """The audit case: 丁丑 on 2027-03-31 is a 命貴人 day in a 丁未 year. The
    passage bars 天比地衝 in 「年月日時」 and weighs 「太歳衝命最凶」."""
    pillars = date_pillars(date(2027, 3, 31), 'Asia/Shanghai')
    assert pillars == {'year': '丁未', 'month': '癸卯', 'day': '己酉'}
    assessed = assess_people([('me', '丁丑')], [pillars])
    day = assessed['people'][0]['days'][0]
    assert (day['grade'], day['pillar_grade'], assessed['grade']) == ('凶', '大吉', '凶')
    hits = prohibitions(assessed)
    assert [(h['rule'], h['pillar'], h['pillar_ganzhi']) for h in hits] == [
        ('xiangzhu_tian_bi_di_chong', 'year', '丁未')]
    assert hits[0]['label'] == '年柱天比地冲' and '这一年（丁未）' in hits[0]['plain']


def test_the_hour_is_read_when_the_time_has_one():
    """「今選擇家通忌天尅地衝年月日時…並忌天比地衝年月日時」, and 「時為輕」."""
    # The audit's case: a 丁未 hour is 天比地衝 for 丁丑.
    assessed = assess_people([('me', '丁丑')], [{'year': '丙午', 'month': '壬辰', 'day': '丁酉', 'hour': '丁未'}])
    assert assessed['grade'] == '凶'
    assert [(h['rule'], h['pillar'], h['pillar_ganzhi']) for h in prohibitions(assessed)] == [
        ('xiangzhu_tian_bi_di_chong', 'hour', '丁未')]
    # 丁丑忌辛未 is a table of days (「日納音尅化命納音」); in the hour a plain clash
    # is lighter than a day's 略輕 one, so it is said and does not grade.
    light = assess_day('丁丑', {'year': '丙午', 'month': '壬辰', 'day': '己酉', 'hour': '辛未'})
    assert light['grade'] == '大吉' and light['pillar_grade'] == '大吉' and light['hour_ganzhi'] == '辛未'
    hour = [f for f in light['factors'] if f['pillar'] == 'hour']
    assert [(f['rule'], f['polarity'], f['quote']) for f in hour] == [('chong_hour', 'note', QUOTES['weight'])]
    assert '只作提示' in hour[0]['plain']
    assert not prohibitions(assess_people([('me', '丁丑')], [{'year': '丙午', 'month': '壬辰', 'day': '己酉',
                                                            'hour': '辛未'}]))
    # 天尅地衝 stays 最凶 in any pillar.
    assert assess_day('甲子', {'day': '丙寅', 'hour': '庚午'})['grade'] == '大凶'
    # Points are counted over the hour too: 七煞 in the month and the hour.
    two = assess_day('乙卯', {'year': '丙午', 'month': '辛卯', 'day': '丙子', 'hour': '辛卯'})
    assert two['grade'] == '凶' and 'qi_sha_two' in {f['rule'] for f in two['factors']}
    # Without an hour nothing is read from one.
    assert 'hour_ganzhi' not in assess_day('丁丑', {'day': '己酉'})


def test_a_month_is_graded_with_its_year():
    calendar = personal_calendar([('me', '丁丑')], '2027-03-01', '2027-06-01', 'Asia/Shanghai', 'month')
    assert calendar['unit'] == 'month' and calendar['entries']
    for entry in calendar['entries']:
        person = entry['people'][0]
        assert person['context']['year']['ganzhi'] == '丁未'
        assert entry['grade'] in ('凶', '大凶'), entry['label']
    years = personal_calendar([('me', '丁丑')], '2026-01-01', '2029-01-01', 'Asia/Shanghai', 'year')
    assert {e['ganzhi']: e['grade'] for e in years['entries']}['丁未'] == '凶'


def _period_1997(start: str, end: str, question: str = '这几天哪天对我好？') -> dict:
    from fortune_reading import read_request
    return read_request({
        'current_timezone': 'Asia/Shanghai', 'request_time': '2027-03-20T02:00:00Z', 'intent': 'period',
        'period': {'start': start, 'end': end}, 'event': {'scenario': 'outlook', 'longitude': 121.47},
        'question': question,
        'participants': [{'id': 'me', 'confirmed': True, 'person': {
            'birth': {'year': 1997, 'month': 6, 'day': 15, 'hour': 10, 'minute': 0, 'gender': 'male',
                      'timezone': 'Asia/Shanghai', 'longitude': 121.47}, 'time_certainty': 'exact'}}]})


def test_the_answer_says_the_year_first_and_calls_no_day_good():
    from fortune_reading import render_answer
    text = render_answer(_period_1997('2027-03-29', '2027-04-03'))
    lead = text.split('\n\n')[0]
    assert lead.startswith('按你出生那年的干支（丁丑）看，这段时间没有对你好的日子：这一年（丁未）冲你的生年')
    assert '太岁冲命最凶' in lead and '换哪天都避不开' in lead
    assert '大吉' not in lead and '3月29日（丁未，天比地冲）本身也冲你' in lead
    # Layer 2 keeps the day pillar as a part, said as such.
    assert '3月31日（己酉）：凶（只看日柱是大吉，被年、月或时辰拉低）' in text
    assert text.count('这一年（丁未）：凶') == 1


def test_a_selection_in_a_clashing_year_says_the_day_cannot_avoid_it():
    from fortune_reading import read_request, render_answer
    result = read_request({
        'current_timezone': 'Asia/Shanghai', 'request_time': '2027-03-20T02:00:00Z', 'intent': 'selection',
        'question': '签合同选哪个时间？', 'period': {'start': '2027-03-29', 'end': '2027-04-03'},
        'event': {'scenario': 'signing', 'timezone': 'Asia/Shanghai', 'longitude': 121.47},
        'duration_minutes': 120, 'granularity': 'hour',
        'candidates': [{'id': 'a', 'start': '2027-03-31T13:00', 'end': '2027-03-31T15:00'},
                       {'id': 'b', 'start': '2027-03-30T09:00', 'end': '2027-03-30T11:00'}],
        'participants': [{'id': 'me', 'confirmed': True, 'person': {
            'birth': {'year': 1997, 'month': 6, 'day': 15, 'hour': 10, 'minute': 0, 'gender': 'male',
                      'timezone': 'Asia/Shanghai', 'longitude': 121.47}, 'time_certainty': 'exact'}}]})
    assert result['conclusion']['status'] == 'excluded_by_clause'
    rows = result['ranking']['excluded']
    assert {r['candidate_id'] for r in rows} == {'a', 'b'}
    assert all(any(h.get('pillar') == 'year' for h in r['excluded_by']) for r in rows)
    lead = render_answer(result).split('\n\n')[0]
    assert lead.startswith('a、b 都需要避开：你（丁丑年生）的年柱天比地冲')
    assert lead.count('年柱天比地冲') == 1 and lead.endswith('这一年里换哪天都避不开，要换就得换出这一年。')
    # The 辛未 hour of a is read, and is light.
    hours = {d.get('hour_ganzhi') for p in rows[0]['personal']['people'] for d in p['days']}
    assert '辛未' in hours


def test_a_clashing_month_inside_the_period_is_said_once_with_its_dates():
    """己卯 (2000-01-15): the 丁酉 month runs to 寒露 (2026-10-08) and clashes 卯
    (「凶莫堪」). Its days are named as one stretch, not one by one; a day that
    also clashes on its own is still named."""
    from fortune_reading import read_request, render_answer
    result = read_request({
        'current_timezone': 'Asia/Shanghai', 'request_time': '2026-09-01T02:00:00Z', 'intent': 'period',
        'period': {'start': '2026-09-28', 'end': '2026-10-13'}, 'event': {'scenario': 'outlook', 'longitude': 121.47},
        'question': '这两周哪天对我好？',
        'participants': [{'id': 'me', 'confirmed': True, 'person': {
            'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30, 'gender': 'male',
                      'timezone': 'Asia/Shanghai', 'longitude': 120}, 'time_certainty': 'exact'}}]})
    lead = render_answer(result).split('\n\n')[0]
    assert lead == ('按你出生那年的干支（己卯）看，这段时间对你最好的日子是10月11日（戊午，命禄），是大吉；'
                    '9月28日至10月8日在丁酉月里，这个月冲你的生年（月柱冲命，凶），协纪说月次于太岁、重于日，'
                    '这些日子都要避开；另外要避开10月2日（己酉，天比地冲）。')
    months = personal_calendar([('me', '丁丑')], '2027-01-01T00:00:00+08:00', '2028-01-01T00:00:00+08:00',
                               'Asia/Shanghai', 'month')
    first = months['entries'][0]
    assert first['ganzhi'] == '庚子' and first['grade'] == '吉'  # 丙午 year, before 立春 2027
    from fortune_reading import _entry_list
    assert _entry_list([first], unit='month') == '庚子月（1月1日至1月5日，财官、六合）'
