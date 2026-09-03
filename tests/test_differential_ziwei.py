"""紫微 differential test against an INDEPENDENT engine: iztro-py.

iztro-py is a pure-Python port of iztro (4,117 stars), which implements the
《紫微斗数全书》 三合派 placement rules this project also follows. Across 7 hand
picked charts it agreed with ziwei_calc on 56 of 57 fields; the 57th was our
命主 bug, fixed in v1.6.0. This locks that agreement over a grid.

Two input conventions differ and are mapped here rather than "fixed":
- iztro's time_index 12 (晚子时) ALSO rolls the lunar day for the star table;
  this project defaults to 子正换日 (day does not roll), so a 23:xx birth is fed
  to iztro as the same calendar day at time_index 0.
- iztro names the palace 仆役宫; this project uses 奴仆宫.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

iztro_astro = pytest.importorskip("iztro_py").astro
pytest.importorskip("lunar_python")

ROOT = Path(__file__).resolve().parent.parent

PALACE_ALIAS = {"仆役宫": "奴仆宫", "交友宫": "奴仆宫", "事业宫": "官禄宫"}
MAIN = {"紫微", "天机", "太阳", "武曲", "天同", "廉贞",
        "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"}


def _ours(y, m, d, hour, gender):
    """In-process call: 900 subprocess spawns pushed the release harness past
    its timeout; calling main() directly runs the same grid in a few seconds."""
    import io as _io
    import json
    from contextlib import redirect_stdout

    sys.path.insert(0, str(ROOT / "scripts"))
    import ziwei_calc

    buf = _io.StringIO()
    with redirect_stdout(buf):
        rc = ziwei_calc.main(["--year", str(y), "--month", str(m), "--day", str(d),
                              "--hour", str(hour), "--gender", gender])
    assert rc == 0
    return json.loads(buf.getvalue())


def _iztro(y, m, d, hour, gender):
    from iztro_py.data.types import Star
    time_index = 0 if hour == 23 else (hour + 1) // 2
    chart = iztro_astro.by_solar(f"{y}-{m}-{d}", time_index, "男" if gender == "male" else "女")

    def name(key):
        return Star(name=key, type="major", scope="origin").translate_name("zh-CN")

    out = {"palaces": {}, "main_pos": {}, "mutagen": {}}
    out["wuxing_ju"] = chart.five_elements_class
    out["soul"] = name(chart.soul)
    out["body"] = name(chart.body)
    for p in chart.palaces:
        pname = PALACE_ALIAS.get(p.translate_name("zh-CN"), p.translate_name("zh-CN"))
        br = p.translate_earthly_branch("zh-CN")
        out["palaces"][pname] = br
        if pname == "命宫":
            out["ming"] = br
        if p.is_body_palace:
            out["shen"] = br
        for s in list(p.major_stars) + list(p.minor_stars):
            n = s.translate_name("zh-CN")
            if n in MAIN:
                out["main_pos"][n] = br
            if s.mutagen:
                out["mutagen"][str(s.mutagen)] = n
    return out


def _grid():
    start, end, step = date(1950, 3, 7), date(2030, 1, 1), timedelta(days=97)
    d = start
    while d < end:
        yield d
        d += step


@pytest.mark.parametrize("day", list(_grid()))
@pytest.mark.parametrize("hour", [0, 10, 23])
def test_core_fields_agree_with_iztro(day, hour):
    gender = "male" if day.year % 2 else "female"
    ours = _ours(day.year, day.month, day.day, hour, gender)
    ref = _iztro(day.year, day.month, day.day, hour, gender)

    assert ours["ming_gong"]["branch"] == ref["ming"]
    assert ours["shen_gong"]["branch"] == ref["shen"]
    assert ours["wuxing_ju"]["name"] == ref["wuxing_ju"]
    assert ours["ming_zhu"] == ref["soul"]
    assert ours["shen_zhu"] == ref["body"]
    for star, br in ours["main_stars_positions"].items():
        assert ref["main_pos"].get(star) == br, (star, br, ref["main_pos"].get(star))
    for pal in ours["twelve_palaces"]:
        assert ref["palaces"].get(pal["name"]) == pal["branch"], (
            pal["name"], pal["branch"], ref["palaces"].get(pal["name"]))
