"""黄历多人筛日：每人按《协纪辨方书》相主各给等级，与择日用的同一套判法一致，不合成总分。"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from huangli_query import people_grades
from xiangzhu import assess_people, date_pillars

SKILL = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune'


def test_each_person_matches_the_selection_grades_and_nothing_is_combined():
    out = people_grades(['我=1990-05-15', '爸爸=壬寅'], '2026-11-08', 'Asia/Shanghai')
    assert [r['birth_year'] for r in out['rows']] == ['庚午', '壬寅'] and out['combined'] is None
    pillars = date_pillars(date(2026, 11, 8), 'Asia/Shanghai')
    same = assess_people([('我', '庚午'), ('爸爸', '壬寅')], [pillars])
    assert [r['grade'] for r in out['rows']] == [row['days'][0]['grade'] for row in same['people']]
    assert '我（庚午年生）' in out['say'] and '爸爸（壬寅年生）' in out['say']


def test_birth_before_lichun_counts_in_the_previous_year():
    out = people_grades(['甲=1990-02-01'], '2026-11-08', 'Asia/Shanghai')
    assert out['rows'][0]['birth_year'] == '己巳'


def test_cli_people_and_bad_input():
    run = [sys.executable, '-X', 'utf8', 'scripts/huangli_query.py', '--date', '2026-11-08']
    ok = subprocess.run([*run, '--person', '我=庚午'], cwd=SKILL, capture_output=True, text=True, encoding='utf-8')
    assert json.loads(ok.stdout)['people']['rows'][0]['label'] == '我'
    bad = subprocess.run([*run, '--person', '我=1990'], cwd=SKILL, capture_output=True, text=True, encoding='utf-8')
    assert bad.returncode == 1 and json.loads(bad.stdout)['error'] == 'invalid_input'
    no_name = subprocess.run([*run, '--person', '庚午'], cwd=SKILL, capture_output=True, text=True, encoding='utf-8')
    assert no_name.returncode == 1
