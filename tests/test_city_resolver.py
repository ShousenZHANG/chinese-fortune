"""B4: same-name places are not guessed; the user is asked for the province."""
from city_resolver import resolve
from conftest import run_cli

BIRTH = ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--gender', 'male',
         '--no-shensha', '--no-geju', '--no-yongshen']


def test_same_name_district_is_ambiguous_until_qualified():
    row, choices = resolve('朝阳')
    assert row is None and [c['name'] for c in choices] == ['北京市朝阳区', '辽宁省朝阳市']
    for text, expected in (('北京朝阳区', '北京市朝阳区'), ('辽宁朝阳', '辽宁省朝阳市'), ('南京鼓楼区', '江苏省南京市鼓楼区'),
                           ('海淀区', '北京市海淀区'), ('成都', '成都'), ('成都市', '成都')):
        assert resolve(text)[0]['name'] == expected, text
    assert len(resolve('江苏鼓楼')[1]) == 2


def test_district_longitude_is_borrowed_from_its_city_row():
    assert resolve('北京市朝阳区')[0]['lon'] == resolve('北京')[0]['lon']
    assert resolve('普陀区')[0] is None and resolve('上海普陀')[0]['resolved_via'] == '上海'


def test_engines_report_ambiguity_and_near_names():
    out = run_cli('bazi_calc.py', *BIRTH, '--city', '朝阳', expect_rc=1)
    assert out['error'] == 'ambiguous_city' and len(out['candidates']) == 2 and '请加上省份' in out['message']
    out = run_cli('bazi_calc.py', *BIRTH, '--city', '杭洲', expect_rc=1)
    assert out['error'] == 'unknown_city' and '杭州' in out['message']
    zw = run_cli('ziwei_calc.py', *BIRTH[:10], '--city', '鼓楼', expect_rc=1)
    assert zw['error'] == 'ambiguous_city'
    ok = run_cli('bazi_calc.py', *BIRTH, '--city', '北京朝阳区')
    assert ok['birthplace']['name'] == '北京市朝阳区'
