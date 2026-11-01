"""B1: candidate birth times across dates — which pillars hold, which change, what each change moves."""
import json
import subprocess
import sys

from conftest import SCRIPTS

BIRTH = {'gender': 'male', 'timezone': 'Asia/Shanghai', 'longitude': 116.4}


def run(request):
    done = subprocess.run([sys.executable, str(SCRIPTS / 'birth_candidates.py'), '--stdin'], input=json.dumps(request),
                          capture_output=True, text=True, encoding='utf-8')
    return done.returncode, json.loads(done.stdout)


def test_range_over_lichun_and_midnight_finds_each_boundary_to_the_minute():
    rc, out = run({'birth': BIRTH, 'range': {'start': '2000-02-04T19:00', 'end': '2000-02-05T02:00'}})
    assert rc == 0 and out['mode'] == 'range'
    assert out['varying']['year'] == ['己卯', '庚辰'] and out['varying']['month'] == ['丁丑', '戊寅']
    assert out['varying']['day'] == ['壬辰', '癸巳']
    starts = {s['from'] for s in out['segments']}
    assert '2000-02-04T20:41' in starts            # 立春 2000-02-04 20:40 北京时间
    assert '2000-02-05T00:29' in starts            # 真太阳时子正换日（经度 116.4）
    assert '日主' in out['affects']['day'] and any(line.startswith('日柱会变') for line in out['say'])


def test_candidates_report_fixed_pillars_and_dst_is_respected():
    # 1990 年中国夏令时：钟表 5 月 11 日 00:40 是标准时 10 日 23:40，与 10 日 23:50 同柱。
    rc, out = run({'birth': {**BIRTH, 'gender': 'female', 'longitude': 121.47},
                   'candidates': ['1990-05-10T23:50', '1990-05-11T00:40']})
    assert rc == 0 and out['varying'] == {} and len(out['fixed']) == 4
    rc, out = run({'birth': BIRTH, 'candidates': ['1995-03-05T23:50', '1995-03-06T01:10']})
    assert rc == 0 and 'day' in out['varying'] and 'year' in out['fixed']


def test_bad_requests_are_input_errors():
    for request in ({'birth': BIRTH}, {'birth': {}, 'candidates': ['2000-01-01T00:00', '2000-01-02T00:00']},
                    {'birth': BIRTH, 'range': {'start': '2000-01-01T00:00', 'end': '2000-01-05T00:00'}},
                    {'birth': BIRTH, 'range': {'start': '2000-01-02T00:00', 'end': '2000-01-01T00:00'}},
                    {'birth': BIRTH, 'candidates': ['tomorrow', '2000-01-01T00:00']}):
        rc, out = run(request)
        assert rc == 1 and out['ok'] is False, request


def test_router_sends_unsure_cross_date_births_here():
    sys.path.insert(0, str(SCRIPTS))
    from question_router import route
    assert route('我不确定是5号晚上还是6号凌晨出生的，帮我看八字')['flow'] == 'birth_candidates'
    assert route('看看我的八字格局')['flow'] != 'birth_candidates'
