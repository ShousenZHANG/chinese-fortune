"""Every scenario graded by 相主 says where 协纪 licenses it, or that it borrows.

相主 is 协纪's method for choosing a time for the principal of an undertaking
(「選擇之道……合局相主」, xieji:c033:p0002). The undertakings it chooses for are
the ones 协纪 lists; for commoners that is 「民用三十七事」 (xieji:c011:p0005).
A modern event on that list is licensed by it. One that is not — an interview,
an exam, a salary talk — can still be graded by the same method, but the
answer must say the method is being borrowed, not that the book covers it.
"""
from classical_search import get_passage
from fortune_rules import YONGSHI_PASSAGE, capabilities
from test_ranking import _travel_request

LISTED = {'travel': '出行', 'wedding': '嫁娶', 'moving': '移徙', 'business': '開市'}


def _personal():
    return [c for c in capabilities() if c['personal_ranking'] == 'rule_based']


def test_every_personally_ranked_scenario_declares_its_authority():
    caps = _personal()
    assert caps, 'no personally ranked scenario found'
    for cap in caps:
        authority = cap.get('authority')
        assert authority and authority['kind'] in ('passage', 'borrowed'), cap['scenario']
        assert authority['reason'], cap['scenario']


def test_listed_undertakings_cite_the_list_and_the_term_is_verbatim():
    text = get_passage(YONGSHI_PASSAGE)['text']
    by_key = {c['scenario']: c['authority'] for c in _personal()}
    for scenario, term in LISTED.items():
        assert by_key[scenario] == {**by_key[scenario], 'kind': 'passage', 'term': term,
                                    'passage_id': YONGSHI_PASSAGE}, scenario
        assert term in text, term


def test_everything_else_is_marked_as_borrowed():
    for cap in _personal():
        if cap['scenario'] not in LISTED:
            assert cap['authority']['kind'] == 'borrowed', cap['scenario']
    custom = capabilities('讨论社团活动')[0]
    assert custom['authority']['kind'] == 'borrowed'


def test_a_borrowed_nearest_term_is_really_on_the_list():
    """「最接近的是上官」 is only worth saying if 上官 is on the list."""
    text = get_passage(YONGSHI_PASSAGE)['text']
    for cap in _personal():
        term = cap['authority'].get('term')
        if cap['authority']['kind'] == 'borrowed' and term:
            assert term in text, (cap['scenario'], term)


def _markdown(scenario: str) -> str:
    from fortune_reading import read_request, render_answer
    request = _travel_request([{'id': 'a', 'start': '2026-10-15T09:00', 'end': '2026-10-15T13:00'}],
                              {'start': '2026-10-13', 'end': '2026-10-17'})
    request['event']['scenario'] = scenario
    return render_answer(read_request(request))


def test_the_answer_says_licensed_or_borrowed():
    travel = _markdown('travel')
    assert '民用三十七事' in travel and '「出行」' in travel and YONGSHI_PASSAGE in travel
    assert '借用' not in travel
    interview = _markdown('interview')
    assert '民用三十七事' in interview and '借用' in interview
    # The old catch-all sentence said the same thing for every event.
    assert '这里把同一套相主规则用在这件事上' not in travel + interview
