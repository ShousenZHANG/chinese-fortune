"""B2: a birth-data correction says what changed, what is void and what the chart is now."""
import json
import subprocess
import sys

from conftest import SCRIPTS

BASE = {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30, 'gender': 'male',
        'timezone': 'Asia/Shanghai', 'longitude': 116.4}


def run(request):
    done = subprocess.run([sys.executable, str(SCRIPTS / 'birth_correction.py'), '--stdin'],
                          input=json.dumps(request), capture_output=True, text=True, encoding='utf-8')
    return done.returncode, json.loads(done.stdout)


def test_hour_change_voids_only_hour_conclusions():
    rc, out = run({'before': BASE, 'after': {**BASE, 'hour': 22}})
    assert rc == 0 and out['changed_fields'] == ['hour'] and out['changed_pillars'] == ['hour']
    assert out['before']['four_pillars']['hour'] == '乙巳' and out['after']['four_pillars']['hour'] == '辛亥'
    assert '时柱与时干十神' in out['invalidated'] and '日主' not in out['invalidated']
    assert out['kept_pillars'] == ['年柱己卯', '月柱丁丑', '日柱壬申']
    assert out['say'][0] == '更正：时由10改为22。'


def test_day_change_voids_day_master_and_gender_change_voids_luck():
    rc, out = run({'before': BASE, 'after': {**BASE, 'day': 16}})
    assert rc == 0 and 'day' in out['changed_pillars'] and '日主' in out['invalidated']
    rc, out = run({'before': BASE, 'after': {**BASE, 'gender': 'female'}})
    assert rc == 0 and out['changed_pillars'] == [] and out['before']['da_yun'] != out['after']['da_yun']
    assert '大运顺逆（阳男阴女顺、阴男阳女逆）' in out['invalidated'] and '性别由男改为女' in out['say'][0]


def test_bad_requests():
    for request in ({'before': BASE, 'after': BASE}, {'before': BASE}, {'before': BASE, 'after': {**BASE, 'x': 1}}):
        rc, out = run(request)
        assert rc == 1 and out['ok'] is False, request


def test_router_sends_corrections_here():
    sys.path.insert(0, str(SCRIPTS))
    from question_router import route
    assert route('刚才出生时辰给错了，其实是晚上十点')['flow'] == 'birth_correction'
