import json
import subprocess
import sys

import pytest
from answer_check import check_answer
from conftest import SCRIPTS

FAKE_QUOTE = '官星得禄，富贵双全，必主大吉'
FAKE_ANSWER = f'《子平真诠》原文「{FAKE_QUOTE}」。'


@pytest.mark.parametrize('facts', [
    {'ok': False, 'tool': 'bazi_reading', 'message': FAKE_QUOTE},
    {'ok': True, 'tool': 'classical_search', 'results': [], 'note': FAKE_QUOTE},
    {'ok': True, 'tool': 'classical_search', 'results': [
        {'passage_id': 'ziping:c009:p0002', 'text': FAKE_QUOTE}]},
], ids=['failed-tool-message', 'successful-search-note', 'fabricated-search-result'])
def test_tool_text_cannot_verify_a_fabricated_classical_quote(facts):
    result = check_answer(FAKE_ANSWER, [facts])
    assert result['passed'] is False
    assert 'unverified_quote' in [finding['code'] for finding in result['findings']]
    assert result['checked']['quotes_checked'] == 1


@pytest.mark.parametrize('field', ['question', 'query', 'normalized_query', 'prompt', 'input', 'request', 'answer'])
def test_historic_user_echo_cannot_verify_a_quote(field):
    result = check_answer(FAKE_ANSWER, [{field: FAKE_QUOTE}])
    assert result['passed'] is False
    assert 'unverified_quote' in [finding['code'] for finding in result['findings']]


def test_tool_text_alone_cannot_verify_an_unnamed_classical_quote():
    facts = [{'ok': True, 'tool': 'classical_search', 'results': [], 'note': FAKE_QUOTE}]
    result = check_answer(f'原文「{FAKE_QUOTE}」。', facts)
    assert result['passed'] is False
    assert [finding['code'] for finding in result['findings']] == ['unverified_quote']


@pytest.mark.parametrize('answer', [
    '《滴天髓》原文「官逢财印，又无刑冲破害」。',
    '《滴天髓》ditian:c002:p0001 原文「天道有寒暖，發育萬物」。',
    '《滴天髓》xieji:c033:p0011 原文「天干地支」。',
    '《滴天髓》ditian:c999:p9999 原文「天道有寒暖，發育萬物」。',
    '《神峰通考》ditian:c016:p0001 原文「天道有寒暖，發育萬物」。',
], ids=['wrong-book', 'wrong-passage', 'book-and-passage-must-agree', 'unknown-passage',
        'unknown-book-with-known-passage'])
def test_citation_constraints_must_match_the_same_corpus_source(answer):
    result = check_answer(answer, [])
    assert result['passed'] is False
    assert [finding['code'] for finding in result['findings']] == ['misattributed_quote']


@pytest.mark.parametrize('answer', [
    '《子平真诠》原文「官逢财印，又无刑冲破害」。',
    '《滴天髓》ditian:c016:p0001 原文「天道有寒暖，發育萬物」。',
    '《子平真诠》ziping:c009:p0002 原文「論用神成敗救應」。',
    '《子平真诠》原文「官逢财印……无刑冲破害」。',
    '《子平真诠》原文「生尅……格局分焉」。',
    '原文说「支干合命愈为奇，上上格」。',
], ids=['book', 'book-and-passage', 'passage-heading', 'elision', 'non-negating-elision', 'variant-glyph'])
def test_real_quotes_remain_verified_without_tool_text(answer):
    result = check_answer(answer, [])
    assert result['passed'] is True
    assert result['findings'] == []
    assert result['checked']['quotes_checked'] == 1


@pytest.mark.parametrize('quote', [FAKE_QUOTE, '官逢财印，又无刑冲破害'])
def test_unknown_named_book_is_explicitly_unverified(quote):
    result = check_answer(f'《神峰通考》原文「{quote}」。', [])
    assert [(finding['code'], finding['severity']) for finding in result['findings']] == [
        ('quote_outside_library', 'warning')]


def test_elision_cannot_reverse_a_cited_passages_condition():
    result = check_answer('《滴天髓》ditian:c016:p0001 原文「天道有寒暖，發育萬物，人道得之，……過也」。', [])
    assert result['passed'] is False
    assert [finding['code'] for finding in result['findings']] == ['elision_drops_negation']


def test_stdin_cli_rejects_search_note_as_classical_authority():
    request = {'answer': FAKE_ANSWER, 'facts': [
        {'ok': True, 'tool': 'classical_search', 'results': [], 'note': FAKE_QUOTE}]}
    done = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / 'answer_check.py'), '--stdin'],
                          input=json.dumps(request, ensure_ascii=False), capture_output=True,
                          text=True, encoding='utf-8')
    assert done.returncode == 1, done.stdout + done.stderr
    result = json.loads(done.stdout)
    assert result['passed'] is False
    assert [finding['code'] for finding in result['findings']] == ['unverified_quote']
