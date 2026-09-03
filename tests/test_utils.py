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


# --------------------------------------------------------------------------- #
# 时辰 换算 — 五个引擎曾各写一份, 现共用 utils
# --------------------------------------------------------------------------- #

def test_hour_branch_covers_all_24_hours():
    """子时 spans 23:00-01:00, so 23 and 0 share a 时辰; every other 时辰 is a
    2-hour block starting on an odd hour."""
    from utils import DIZHI, hour_branch, hour_branch_index, shichen_number

    assert hour_branch(23) == hour_branch(0) == "子"
    assert hour_branch(22) == "亥"
    assert hour_branch(1) == hour_branch(2) == "丑"
    for h in range(24):
        assert hour_branch(h) == DIZHI[hour_branch_index(h)]
        assert shichen_number(h) == hour_branch_index(h) + 1
        assert 1 <= shichen_number(h) <= 12
    # every 时辰 reachable, and each covers exactly 2 clock hours
    seen = [hour_branch(h) for h in range(24)]
    assert set(seen) == set(DIZHI)
    assert all(seen.count(b) == 2 for b in DIZHI)


def test_engines_delegate_to_the_shared_hour_helper():
    """The five engine-local wrappers must stay equivalent to utils."""
    import liuren_cast
    import meihua_cast
    import xiaoliuren_cast
    import yijing_cast
    import ziwei_tables
    from utils import hour_branch, shichen_number

    for h in range(24):
        assert ziwei_tables.branch_of_hour(h) == hour_branch(h)
        assert liuren_cast.hour_to_zhi(h) == hour_branch(h)
        assert xiaoliuren_cast.hour_branch_from_hour(h) == hour_branch(h)
        assert meihua_cast.shichen_num(h) == shichen_number(h)
        assert yijing_cast.shichen_index(h) == shichen_number(h)


def test_xun_kong_covers_all_60_pillars():
    """Every 旬 leaves exactly two branches 空亡, and the six 旬 partition the
    60 pillars. bazi and liuyao each carried a copy of this table."""
    from utils import DIZHI, TIANGAN, jiazi_index, xun_kong

    seen = {}
    for stem in TIANGAN:
        for branch in DIZHI:
            try:
                jiazi_index(stem, branch)
            except ValueError:
                continue
            kong = xun_kong(stem, branch)
            assert len(kong) == 2, f"{stem}{branch}: {kong}"
            assert all(k in DIZHI for k in kong)
            seen[stem + branch] = tuple(kong)
    assert len(seen) == 60
    assert len(set(seen.values())) == 6  # six 旬


def test_engines_delegate_xun_kong_and_chong():
    import bazi_tables
    import liuren_cast
    import liuyao_cast
    from utils import DIZHI, TIANGAN, chong_branch, jiazi_index, xun_kong

    for stem in TIANGAN:
        for branch in DIZHI:
            try:
                jiazi_index(stem, branch)
            except ValueError:
                continue
            want = xun_kong(stem, branch)
            assert bazi_tables.xun_kong_of_day(stem, branch) == want
            assert liuyao_cast.xun_kong(stem, branch) == want

    for branch in DIZHI:
        partner = chong_branch(branch)
        assert liuren_cast.chong_zhi(branch) == partner
        assert chong_branch(partner) == branch  # involution
        assert liuyao_cast.LIU_CHONG_PAIRS[branch] == partner


# --------------------------------------------------------------------------- #
# 历史时区 / 夏令时 — 钟表时间 != 标准时
# --------------------------------------------------------------------------- #

def test_resolve_timezone_offset_detects_china_dst():
    """China observed 夏令时 in 14 separate windows (1919, 1940-1949,
    1986-1991). A clock reading during one of them is an hour ahead of standard
    time, and 时辰 boundaries sit on the hour — so the 时柱 moves."""
    from utils import resolve_timezone_offset

    summer = resolve_timezone_offset("Asia/Shanghai", 1988, 7, 1, 7, 30)
    assert summer["offset_hours"] == 9.0
    assert summer["dst_hours"] == 1.0
    assert "夏令时" in summer["note"]

    after = resolve_timezone_offset("Asia/Shanghai", 1992, 7, 1, 7, 30)
    assert after["offset_hours"] == 8.0
    assert after["dst_hours"] == 0.0
    assert after["note"] == ""


def test_resolve_timezone_offset_handles_pre_1949_offsets():
    """tzdata also carries the pre-PRC offsets; 1900 Shanghai was LMT +8:05:43."""
    from utils import resolve_timezone_offset

    r = resolve_timezone_offset("Asia/Shanghai", 1900, 6, 1, 12, 0)
    assert r["offset_hours"] != 8.0


def test_resolve_timezone_offset_rejects_unknown_zone():
    import pytest as _pytest
    from utils import resolve_timezone_offset
    with _pytest.raises(ValueError, match="时区"):
        resolve_timezone_offset("Not/AZone", 1990, 1, 1, 12, 0)
