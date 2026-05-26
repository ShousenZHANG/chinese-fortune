"""Golden-value unit tests for the shared core (scripts/utils.py).

Pure functions only — no lunar_python dependency. These lock in the
干支/五行/十神/真太阳时 primitives every script builds on.
"""
import math

import pytest

import utils


# --------------------------------------------------------------------------- #
# 五行 / 阴阳
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("ch,expected", [
    ("甲", "木"), ("乙", "木"), ("丙", "火"), ("丁", "火"),
    ("戊", "土"), ("己", "土"), ("庚", "金"), ("辛", "金"),
    ("壬", "水"), ("癸", "水"),
    ("子", "水"), ("午", "火"), ("卯", "木"), ("酉", "金"), ("辰", "土"),
])
def test_wuxing(ch, expected):
    assert utils.tg_dz_wuxing(ch) == expected


@pytest.mark.parametrize("ch,expected", [
    ("甲", "阳"), ("乙", "阴"), ("庚", "阳"), ("癸", "阴"),
    ("子", "阳"), ("丑", "阴"), ("午", "阳"), ("亥", "阴"),
])
def test_yin_yang(ch, expected):
    assert utils.tg_dz_yin_yang(ch) == expected


def test_wuxing_unknown_raises():
    with pytest.raises(ValueError):
        utils.tg_dz_wuxing("X")


# --------------------------------------------------------------------------- #
# 十神 — full decade against 甲 day-master, plus 庚 (user's day-master)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("other,expected", [
    ("甲", "比肩"), ("乙", "劫财"),
    ("丙", "食神"), ("丁", "伤官"),
    ("戊", "偏财"), ("己", "正财"),
    ("庚", "七杀"), ("辛", "正官"),
    ("壬", "偏印"), ("癸", "正印"),
])
def test_shi_shen_jia_daymaster(other, expected):
    assert utils.shi_shen("甲", other) == expected


@pytest.mark.parametrize("other,expected", [
    ("庚", "比肩"), ("辛", "劫财"),
    ("壬", "食神"), ("癸", "伤官"),
    ("甲", "偏财"), ("乙", "正财"),
    ("丙", "七杀"), ("丁", "正官"),
    ("戊", "偏印"), ("己", "正印"),
])
def test_shi_shen_geng_daymaster(other, expected):
    assert utils.shi_shen("庚", other) == expected


def test_shi_shen_rejects_branch():
    with pytest.raises(ValueError):
        utils.shi_shen("甲", "子")


# --------------------------------------------------------------------------- #
# 60 甲子
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("stem,branch,idx", [
    ("甲", "子", 0),
    ("乙", "丑", 1),
    ("甲", "戌", 10),
    ("庚", "子", 36),
    ("癸", "亥", 59),
])
def test_jiazi_index(stem, branch, idx):
    assert utils.jiazi_index(stem, branch) == idx


def test_jiazi_invalid_pair_raises():
    # 甲丑 is not a valid 甲子 pairing (parity mismatch).
    with pytest.raises(ValueError):
        utils.jiazi_index("甲", "丑")


# --------------------------------------------------------------------------- #
# 真太阳时 — longitude correction incl. day roll-over regression
# --------------------------------------------------------------------------- #

def test_longitude_no_offset_on_reference_meridian():
    assert utils.longitude_correction(14, 30, 120.0, 8.0) == (0, 14, 30)


def test_longitude_east_adds_minutes():
    # 135°E is 15° east of 120 -> +60 min.
    assert utils.longitude_correction(14, 30, 135.0, 8.0) == (0, 15, 30)


def test_longitude_rolls_forward_past_midnight():
    # 23:30 + 60 min -> 00:30 next day.
    assert utils.longitude_correction(23, 30, 135.0, 8.0) == (1, 0, 30)


def test_longitude_rolls_back_before_midnight():
    # REGRESSION (was clamped to same day): 00:30 at 75°E -> -180 min -> prev day 21:30.
    assert utils.longitude_correction(0, 30, 75.0, 8.0) == (-1, 21, 30)


# --------------------------------------------------------------------------- #
# Equation of Time — bounded, finite
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("doy", [1, 81, 172, 264, 355])
def test_equation_of_time_bounded(doy):
    eot = utils.equation_of_time(doy)
    assert math.isfinite(eot)
    assert -20.0 < eot < 20.0
