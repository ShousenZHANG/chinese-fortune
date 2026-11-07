"""大六壬本命行年：书中四个行年例逐条复算，课里给出行年、本命位上的天盘神与天将。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from classical_search import get_passage
from liuren_xingnian import SOURCES, xingnian

SKILL = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune'


def test_quotes_are_in_their_passages():
    for pid, quote, _ in SOURCES:
        assert quote in get_passage(pid)['text'], pid


@pytest.mark.parametrize('age,gender,expected', [
    (23, 'male', '戊子'), (23, 'female', '庚戌'),      # xuanze:c002:p0094
    (49, 'male', '甲寅'), (34, 'female', '己亥'),      # liuren:c006:p0034
    (1, 'male', '丙寅'), (1, 'female', '壬申'), (61, 'male', '丙寅'),
])
def test_the_books_examples(age, gender, expected):
    assert xingnian(age, gender) == expected


def _cast(*extra):
    return subprocess.run([sys.executable, '-X', 'utf8', 'scripts/liuren_cast.py', '--date', '2026-11-08',
                           '--time', '10:00', *extra], cwd=SKILL, capture_output=True, text=True, encoding='utf-8')


def test_the_course_shows_where_benming_and_xingnian_sit():
    done = _cast('--birth-date', '1990-05-15', '--gender', 'male')
    out = json.loads(done.stdout)
    row = out['benming_xingnian']
    assert row['age_xusui'] == 37 and row['benming']['ganzhi'] == '庚午' and row['xingnian']['ganzhi'] == '壬寅'
    for seat in (row['benming'], row['xingnian']):
        assert seat['tian_pan'] == out['tian_pan'][seat['di_pan']]
        assert out['shi_er_tian_jiang'][seat['general']]['di_pan'] == seat['di_pan']
    # 出生在立春前，本命按上一年。
    early = json.loads(_cast('--birth-date', '1990-02-01', '--gender', 'female').stdout)['benming_xingnian']
    assert early['benming']['ganzhi'] == '己巳' and early['age_xusui'] == 38
    assert 'benming_xingnian' not in json.loads(_cast().stdout)


def test_birth_without_gender_is_an_input_error():
    done = _cast('--birth-date', '1990-05-15')
    assert done.returncode == 1 and json.loads(done.stdout)['error'] == 'invalid_input'
