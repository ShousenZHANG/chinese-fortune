"""Real-world references ride after the divination answer and change nothing in it."""
import re

from answer_style import style_violations
from fortune_reading import read_request, render_answer
from test_ranking import _slot, _travel_request

HEADER = '现实参考（《高性价比人生指南》快照 2026-09-27，与上面的术数结论无关）'


def _trip(destination=None, scenario='travel'):
    request = _travel_request([_slot('a', '2026-10-15', '09:00', '13:00'),
                               _slot('b', '2026-10-16', '09:00', '13:00')],
                              {'start': '2026-10-13', 'end': '2026-10-17'})
    request['event']['scenario'] = scenario
    request['preferences'] = {'prefer': 'earliest'}
    if destination:
        request['event']['destination_timezone'] = destination
    return request


def test_a_trip_abroad_carries_section_21_after_the_answer():
    result = read_request(_trip('Asia/Singapore'))
    ref = result['life_reference']
    assert [(e['section'], e['number']) for e in ref['entries']][:2] == [(21, 1), (21, 2)]
    assert ref['region']['region'] == '境外' and ref['source']['commit'].startswith('8276caec')
    text = render_answer(result)
    assert HEADER in text
    assert text.index(HEADER) > text.index('\n\n'), 'the references must not be in the first paragraph'
    assert '（第 21 节第 1 条，证据等级 A；面向中国公民；以官方最新规定为准）' in text


def test_the_references_change_nothing_in_the_divination_answer():
    with_ref = read_request(_trip('Asia/Singapore'))
    without = read_request(_trip())
    assert with_ref['recommendation'] == without['recommendation']
    assert with_ref['practical_choice'] == without['practical_choice']
    assert render_answer(with_ref).split('\n\n')[0] == render_answer(without).split('\n\n')[0]
    assert without['life_reference']['entries'] == []
    assert HEADER not in render_answer(without)


def test_titles_are_quoted_verbatim_so_no_number_is_invented():
    result = read_request(_trip('Asia/Singapore'))
    text = render_answer(result)
    section = text[text.index(HEADER):]
    for entry in result['life_reference']['entries']:
        assert entry['title'] in section
    # Every digit run outside the (section, number, grade) tag comes from a title.
    body = re.sub(r'（第 \d+ 节第 \d+ 条[^）]*）', '', section)
    titles = ''.join(e['title'] for e in result['life_reference']['entries'])
    for digits in re.findall(r'\d+', body.replace(HEADER, '')):
        assert digits in titles, digits


def test_mainland_rules_are_not_attached_for_a_move_in_sydney():
    result = read_request(_trip(scenario='moving'))
    assert result['life_reference']['entries'] == []
    assert HEADER not in render_answer(result)


def test_the_rendered_answer_still_passes_the_style_rules():
    assert not style_violations(render_answer(read_request(_trip('Asia/Singapore'))))


def test_a_disputed_entry_carries_the_books_other_side_verbatim():
    """10:3's 备注 opens 「争议。另有研究认为……」; the answer quotes it, never paraphrases."""
    from life_guide import _index
    request = _trip(scenario='relationship_conversation')
    text = render_answer(read_request(request))
    dispute = _index()[(10, 3)]['dispute']
    assert f'原书备注：「{dispute}」' in text
    assert text.index(dispute) > text.index(HEADER)


def test_a_wedding_on_the_mainland_names_the_long_article():
    request = _trip(scenario='wedding')
    request['event']['timezone'] = 'Asia/Shanghai'
    request['event']['longitude'] = 121.47
    text = render_answer(read_request(request))
    assert '- 长文《结婚划不划算：把一笔糊涂账拆成五笔清楚账》（书里另附的一篇长文；以官方最新规定为准）' in text
