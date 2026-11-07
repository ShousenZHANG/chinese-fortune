"""梅花易数的物数、声音、丈尺、尺寸、后天端法起卦与应期，逐条按《梅花易数》原文复算。"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from classical_search import get_passage
from meihua_cast import (
    DIRECTION_TRIGRAM,
    cast_by_count,
    cast_by_length,
    cast_by_object,
    cast_by_sound,
    package,
    timing,
)
from utils import BAGUA, shichen_number

SKILL = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune'
WU_HOUR = datetime(2026, 6, 1, 12, 30)  # 午时，时数七
TRAD = str.maketrans('东离兑', '東離兌')


def _cli(*argv):
    done = subprocess.run([sys.executable, '-X', 'utf8', 'scripts/meihua_cast.py', '--datetime', '2026-06-01T12:30',
                           *argv], cwd=SKILL, capture_output=True, text=True, encoding='utf-8')
    return done.returncode, json.loads(done.stdout)


def test_count_cast_uses_the_count_above_the_hour_below_and_their_sum_for_the_line():
    # meihua:c001:p0021 以此數起作上卦，以時數配作下卦。即以卦數並時數總除六取動爻
    meta = cast_by_count(11, WU_HOUR)
    assert shichen_number(12) == 7
    assert (meta['upper_num'], meta['lower_num'], meta['change_num']) == (3, 7, 6)  # 11%8=3 离；7 艮；18%6=0→6
    assert meta['source'] == 'meihua:c001:p0021'


def test_sound_cast_adds_the_hour_to_the_lower_trigram_and_says_where_the_line_rule_comes_from():
    meta = cast_by_sound(5, WU_HOUR)
    assert (meta['upper_num'], meta['lower_num'], meta['change_num']) == (5, 4, 6)  # 5 巽；12%8=4 震；12%6→6
    assert meta['source'] == 'meihua:c001:p0022' and '物數' in meta['change_basis']


def test_zhang_chi_ignores_the_hour_and_chi_cun_adds_it():
    # meihua:c001:p0035 丈數為上卦，尺數為下卦。合丈尺之數取爻。寸數不用
    zc = cast_by_length(WU_HOUR, zhang=2, chi=3, cun=9)
    assert (zc['upper_num'], zc['lower_num'], zc['change_num']) == (2, 3, 5) and zc['ignored'] == ['寸']
    # meihua:c001:p0036 以尺數為上卦，寸數為下卦。合尺寸之數加時取爻
    cc = cast_by_length(WU_HOUR, chi=4, cun=6)
    assert (cc['upper_num'], cc['lower_num'], cc['change_num']) == (4, 6, 5)  # 4+6+7=17%6=5
    with pytest.raises(ValueError):
        cast_by_length(WU_HOUR, zhang=2)


def test_object_and_direction_use_xiantian_numbers_plus_the_hour():
    # meihua:c001:p0049 以物為上卦，方位為下卦，合物卦之數與方卦之數加時數以取動爻；
    # meihua:c002:p0007 占卜起卦合以乾一兌二離三震四巽五坎六艮七坤八之數為用。
    meta = cast_by_object('乾', '南', WU_HOUR)
    assert (meta['upper_tri'], meta['lower_tri']) == ('乾', '离')
    assert meta['change_num'] == (1 + 3 + 7 - 1) % 6 + 1
    assert cast_by_object('離', '西北', WU_HOUR)['lower_tri'] == '乾'
    with pytest.raises(ValueError):
        cast_by_object('乾', '中', WU_HOUR)


def test_direction_table_is_the_books_fang_dao_lines():
    for direction, (trigram, pid) in DIRECTION_TRIGRAM.items():
        assert BAGUA[trigram]['direction_houtian'] == direction
        assert get_passage(pid)['text'].startswith('方道：' + direction.translate(TRAD))


def test_timing_for_a_xiantian_cast_gives_the_whole_number_and_element_days():
    out = package(cast_by_count(11, WU_HOUR), None, None)
    t = out['timing']
    assert t['whole_number']['value'] == 3 + 7  # 离三＋艮七，如书中「上天一而下地八」
    assert 'posture' not in t
    body = out['ti_yong']['body_trigram']
    assert t['element_days']['body'] == body
    for row in t['element_days']['favourable'] + t['element_days']['unfavourable']:
        assert row['branches'] and row['where']
    cited = {s['passage_id'] for s in t['sources']}
    assert {'meihua:c003:p0040', 'meihua:c003:p0041'} <= cited
    for source in t['sources']:
        assert source['quote'] in get_passage(source['passage_id'])['text'], source


def test_timing_for_a_houtian_cast_gives_walking_standing_sitting():
    out = package(cast_by_object('乾', '南', WU_HOUR), None, None)
    posture = out['timing']['posture']
    base = 1 + 3 + 7
    assert posture['base'] == base
    assert posture['行'] == base / 2 and posture['立'] == base and posture['坐'] == base * 2
    assert '卧' in posture['not_given']


def test_element_days_follow_the_books_examples():
    # meihua:c003:p0040 乾為體，看卦中有坤、艮，則斷其辰、戌、丑、未之土月日；乾體見離，凶在巳午火日。
    t = timing({'upper_tri': '乾', 'lower_tri': '坤', 'change_num': 1, 'method': 'numbers'},
               body='乾', use='坤', nuclear=('艮', '巽'), changed='震')
    fav = {r['trigram']: r for r in t['element_days']['favourable']}
    assert fav['坤']['branches'] == ['辰', '戌', '丑', '未'] and fav['坤']['relation'] == '生体'
    t2 = timing({'upper_tri': '乾', 'lower_tri': '离', 'change_num': 1, 'method': 'numbers'},
                body='乾', use='离', nuclear=('巽', '兑'), changed='艮')
    bad = {r['trigram']: r for r in t2['element_days']['unfavourable']}
    assert bad['离']['branches'] == ['巳', '午'] and bad['离']['relation'] == '克体'


@pytest.mark.parametrize('argv', [
    ['count', '--count', '11'], ['sound', '--count', '5'], ['length', '--zhang', '2', '--chi', '3'],
    ['length', '--chi', '4', '--cun', '6'], ['object', '--trigram', '乾', '--direction', '南'],
])
def test_cli_new_methods(argv):
    code, out = _cli(*argv)
    assert code == 0 and out['ok'] and out['timing']['sources'], out
    assert out['envelope']['replay'].get('time_local')


@pytest.mark.parametrize('argv', [
    ['count', '--count', '0'], ['sound', '--count', '-2'], ['length', '--chi', '4'],
    ['object', '--trigram', '天', '--direction', '南'], ['object', '--trigram', '乾', '--direction', '上'],
])
def test_cli_rejects_counts_and_names_the_book_does_not_cover(argv):
    code, out = _cli(*argv)
    assert code == 1 and out['error'] == 'invalid_input' and out['message']
