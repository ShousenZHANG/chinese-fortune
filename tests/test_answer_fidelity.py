"""Plain wording may not claim more than the words it quotes.

A mechanical scan of free text catches very little of this (HowToLiveBetter's
own audit of 544 entries: one hit by keyword scan, 104 by reviewers with a
shared rubric). So these checks sit on the data paths where the code itself
turns a clause into a claim, and the semantic rest goes to blind review.

Downgrading is allowed and sometimes required (one 比肩 day is 吉, not the
passage's 上吉 for a whole set); upgrading past the quoted wording is not.
"""
import re
from functools import cache

import pytest
from classical_search import get_passage
from wuxing_colours import colour_advice
from xiangzhu import pillar_factors

STEMS = '甲乙丙丁戊己庚辛壬癸'
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
JIAZI = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]

# The strongest grade each word can carry.
LICENSE = {
    ('good', '大吉'): ('最吉', '上上', '貴格', '富格'),
    ('good', '吉'): ('最吉', '上上', '貴格', '富格', '上吉', '宜', '次之', '喜', '格'),
    ('bad', '大凶'): ('最凶',),
    ('bad', '凶'): ('最凶', '凶', '忌'),
    ('bad', '小凶'): ('最凶', '凶', '忌', '略輕', '是非', '不吉'),
}


@cache
def _text(passage_id: str) -> str:
    # The transcription marks unencoded glyphs as 〔字形SKnnnn：X〕 with X the
    # displayed character; a quote shows X, so compare against the displayed form.
    return re.sub(r'〔字形SK\d+：(.)〕', lambda m: m.group(1), get_passage(passage_id)['text'])


def _every_factor():
    for birth in JIAZI:
        for pillar in JIAZI:
            for at in ('year', 'month', 'day', 'hour'):
                yield from pillar_factors(birth, pillar, at=at)


def test_every_xiangzhu_grade_is_licensed_by_the_words_it_quotes():
    seen = set()
    for factor in _every_factor():
        key = (factor['polarity'], factor['grade'])
        if key not in LICENSE:
            continue   # 'note' factors are 平 and claim nothing
        seen.add((factor['rule'], factor['grade']))
        assert any(word in factor['quote'] for word in LICENSE[key]), (factor['rule'], key, factor['quote'])
    # Guard against the loop going vacuous: the strongest grades must actually occur.
    assert {g for _, g in seen} >= {'大吉', '吉', '凶', '大凶', '小凶'}, seen


def test_every_xiangzhu_quote_is_verbatim_in_its_passage():
    checked = set()
    for factor in _every_factor():
        key = (factor['passage_id'], factor['quote'])
        if key in checked:
            continue
        checked.add(key)
        assert factor['quote'] in _text(factor['passage_id']), key
    assert len(checked) >= 10


@pytest.mark.parametrize('stem', list(STEMS))
def test_a_conditional_tiaohou_stem_never_takes_the_first_place(stem):
    """「次取丙火」 or 「有条件才取」 must not be rendered as the first choice."""
    for branch in '寅卯辰巳午未申酉戌亥子丑':
        advice = colour_advice({'day_master': {'stem': stem}, 'four_pillars': {'month': {'branch': branch}}})
        first = advice['needed'][0]['stem']
        conditional = set(advice['tiaohou']['conditional_stems'])
        general = {n['stem'] for n in advice['needed']}
        assert first not in conditional - general, (stem, branch, first)
