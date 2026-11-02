"""Fictional births around independently computed sxtwl 2.0.7 Li Chun instants.

getJieQiByYear/JD2DD gives fixed UTC+8 1984-02-04 23:18:44.292755 and
2000-02-04 20:40:24.174500. Frozen expected pairs below use those boundaries,
with every birth more than nine minutes away. No optional oracle is needed
at test runtime. Reproduction and raw oracle output are in the natal-year
implementation evidence for v60-finalization-20261102.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from ziwei_calc import build_parser, calculate_ziwei

CASES = [
    ('1984-02-04T23:08', 'Asia/Shanghai', 'clock', 1, 120, '癸亥'),
    ('1984-02-04T23:08', 'Asia/Shanghai', 'clock', 2, 120, '癸亥'),
    ('1984-02-04T23:30', 'Asia/Shanghai', 'clock', 1, 120, '甲子'),
    ('1984-02-04T23:30', 'Asia/Shanghai', 'clock', 2, 120, '甲子'),
    ('2000-02-04T20:30', 'Asia/Shanghai', 'clock', 2, 116.4, '己卯'),
    ('2000-02-04T20:30', 'Asia/Shanghai', 'true-solar', 2, 116.4, '己卯'),
    ('2000-02-04T20:50', 'Asia/Shanghai', 'clock', 2, 116.4, '庚辰'),
    ('2000-02-04T20:50', 'Asia/Shanghai', 'true-solar', 2, 116.4, '庚辰'),
    ('2000-02-04T07:30', 'America/New_York', 'clock', 2, -74.006, '己卯'),
    ('2000-02-04T07:50', 'America/New_York', 'clock', 2, -74.006, '庚辰'),
]


def chart(clock: str, *, zone: str | None = 'Asia/Shanghai', standard: str = 'clock',
          sect: int = 2, longitude: float = 120, tz: float = 8,
          divide: str | None = 'lichun', lunar: bool = False) -> dict:
    birth = datetime.fromisoformat(clock)
    argv = ['--year', str(birth.year), '--month', str(birth.month), '--day', str(birth.day),
            '--hour', str(birth.hour), '--minute', str(birth.minute), '--gender', 'male',
            '--sect', str(sect), '--time-standard', standard, '--longitude', str(longitude),
            '--tz', str(tz), '--no-patterns']
    if zone:
        argv += ['--timezone', zone]
    if divide:
        argv += ['--year-divide', divide]
    if lunar:
        argv += ['--lunar']
    result = calculate_ziwei(build_parser().parse_args(argv))
    assert result['ok'], result
    return result


@pytest.mark.parametrize(('clock', 'zone', 'standard', 'sect', 'longitude', 'expected'), CASES)
def test_natal_lichun_year_uses_birth_instant(clock, zone, standard, sect, longitude, expected):
    result = chart(clock, zone=zone, standard=standard, sect=sect, longitude=longitude)
    assert result['year_stem'] + result['year_branch'] == expected


@pytest.mark.parametrize(('clock', 'zone', 'standard', 'sect', 'longitude', 'expected'), CASES)
def test_year_switch_preserves_lunar_date_and_effective_birth_clock(clock, zone, standard, sect, longitude, expected):
    options = {'zone': zone, 'standard': standard, 'sect': sect, 'longitude': longitude}
    lichun = chart(clock, **options)
    lunar = chart(clock, divide='lunar-new-year', **options)
    default = chart(clock, divide=None, **options)
    assert default == lunar
    assert lunar['year_stem'] + lunar['year_branch'] == lunar['lunar_date']['year_ganzhi']
    for key in ('solar_date', 'lunar_date', 'true_solar_time', 'shen_gong'):
        assert lichun[key] == lunar[key], key
    assert lichun['ming_gong']['branch'] == lunar['ming_gong']['branch']
    assert lichun['input']['effective_lunar_month'] == lunar['input']['effective_lunar_month']


def test_fixed_offset_and_lunar_input_identify_the_same_post_lichun_instant():
    shanghai = chart('2000-02-04T20:50')
    fixed_offset = chart('2000-02-04T07:50', zone=None, tz=-5, longitude=-74.006)
    lunar = chart('1999-12-29T20:50', standard='true-solar', longitude=116.4, lunar=True)
    for result in (shanghai, fixed_offset, lunar):
        assert result['year_stem'] + result['year_branch'] == '庚辰'
    assert fixed_offset['solar_date']['hour'] == 7
    assert lunar['solar_date'] == {
        'year': 2000, 'month': 2, 'day': 4, 'hour': 20, 'minute': 21,
    }
    assert lunar['lunar_date']['year_ganzhi'] == '己卯'


def test_late_zi_still_advances_only_the_selected_day_and_hour_convention():
    early = chart('1984-02-04T23:08', sect=1)
    midnight = chart('1984-02-04T23:08', sect=2)
    assert early['solar_date'] == {'year': 1984, 'month': 2, 'day': 5, 'hour': 0, 'minute': 0}
    assert midnight['solar_date'] == {'year': 1984, 'month': 2, 'day': 4, 'hour': 23, 'minute': 8}
    assert early['lunar_date']['day'] == midnight['lunar_date']['day'] + 1
    assert early['year_stem'] + early['year_branch'] == midnight['year_stem'] + midnight['year_branch'] == '癸亥'
