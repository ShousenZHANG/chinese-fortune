"""风水测量合同：二十四山分类、误差跨山不取整、磁偏角换算、盘层，测量与传统分开。"""
import pytest
from classical_search import get_passage
from conftest import run_cli
from fengshui_measure import MOUNTAINS, SOURCES, classify, measure, mountain_at


def test_the_ring_follows_the_book():
    # xieji:c002:p0009：壬子癸属坎、丑艮寅属艮……一卦管三山；子山必午向。
    assert MOUNTAINS[0] == '子' and MOUNTAINS[12] == '午' and len(set(MOUNTAINS)) == 24
    assert MOUNTAINS[mountain_at(90)] == '卯' and MOUNTAINS[mountain_at(270)] == '酉'
    for pid in SOURCES:
        assert get_passage(pid)['text']


# (角度, 误差, 盘层, 应得向山, 是否跨山)：测量误差夹具
FIXTURES = [
    (90.0, 3.0, 'zheng', '卯', False),      # 山心，离分界 7.5°
    (84.0, 3.0, 'zheng', '卯', True),       # 81–87° 跨甲卯分界 82.5°
    (359.0, 2.0, 'zheng', '子', False),     # 跨 0° 仍在子山
    (352.0, 1.0, 'zheng', '壬', True),      # 351–353° 跨壬子分界 352.5°
    (7.5, 0.0, 'zheng', '癸', False),       # 恰在分界，无误差时归后一山
    (352.5, 2.0, 'zhong', '子', False),     # 中针子位在正针壬子之间
    (7.5, 2.0, 'feng', '子', False),        # 缝针子位在子癸之缝
]


@pytest.mark.parametrize('deg,error,needle,mountain,ambiguous', FIXTURES)
def test_measurement_error_fixtures(deg, error, needle, mountain, ambiguous):
    got = classify(deg, error, needle)
    assert got['mountain'] == mountain and got['ambiguous'] is ambiguous
    covered = sum(c['degrees_within_error'] for c in got['candidates'])
    assert covered == pytest.approx(2 * error if error else 15.0)


def test_declination_converts_magnetic_to_true_and_sitting_is_opposite():
    got = measure(90, 'facing', 'magnetic', 1, -10)
    assert got['measurement']['reference_used'] == 'true' and got['measurement']['bearing_used'] == 80
    assert got['tradition']['facing']['mountain'] == '甲' and got['tradition']['sitting']['mountain'] == '庚'
    sat = measure(270, 'sitting', 'true', 1, None)
    assert sat['tradition']['pair'] == '坐酉向卯'


def test_facts_and_tradition_are_separate_and_no_verdicts():
    got = run_cli('fengshui_measure.py', '--bearing', 84, '--of', 'facing', '--reference', 'magnetic', '--error', 3)
    assert set(got['measurement']) >= {'input_bearing', 'reference_used', 'error', 'facing_interval'}
    assert got['tradition']['sources'] == SOURCES and '不判吉凶' in got['tradition']['scope']
    assert '复测' in got['say'] and '吉' not in got['say'] and '凶' not in got['say']


@pytest.mark.parametrize('argv', [
    ['--bearing', 400, '--of', 'facing', '--reference', 'magnetic', '--error', 3],
    ['--bearing', 90, '--of', 'facing', '--reference', 'magnetic', '--error', 60],
    ['--bearing', 90, '--of', 'facing', '--reference', 'true', '--error', 2, '--declination', 5],
])
def test_bad_measurements_are_refused(argv):
    assert run_cli('fengshui_measure.py', *argv, expect_rc=1)['error_class'] == 'input'


def test_router_sends_a_measured_bearing_to_the_tool():
    from question_router import route
    got = route('风水：我家大门朝向 92 度，是用手机指南针测的，坐什么山？')
    assert 'fengshui_measure.py' in got.get('command', '')
