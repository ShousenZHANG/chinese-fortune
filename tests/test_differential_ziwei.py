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

# 六吉 + 禄存/羊陀. Left out of the original comparison, which is how 辛干
# 魁钺 stayed swapped until v1.7.2 — the grid only ever looked at 14 主星.
# 火铃/空劫 are deliberately excluded: their 起法 differs by 流派 (火铃 by
# 年支三合 vs 年支+时, 空劫 顺逆), so a mismatch there would not be evidence
# of a bug. Everything listed here has one uncontested rule.
AUX = {"左辅", "右弼", "文昌", "文曲", "天魁", "天钺", "禄存", "擎羊", "陀罗"}
SI_HUA = {"禄", "权", "科", "忌"}
PALACES = {"命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
           "迁移宫", "奴仆宫", "官禄宫", "田宅宫", "福德宫", "父母宫"}


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

    out = {"palaces": {}, "main_pos": {}, "aux_pos": {}, "mutagen": {}}
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
            if n in AUX:
                out["aux_pos"][n] = br
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
    # 每组都先钉住 KEY SET 再逐项比值。从前这三处写作 `for x in ours[...]`,
    # 即遍历被测方自己输出的键 —— 对"漏发字段"完全免疫: 删掉 七杀 与 化科 后
    # 903 例仍全绿。差分 oracle 只有在键集也来自 oracle 时才是 oracle。
    assert set(ours["main_stars_positions"]) == MAIN, (
        "主星集合不完整", MAIN ^ set(ours["main_stars_positions"]))
    for star in sorted(MAIN):
        assert ours["main_stars_positions"][star] == ref["main_pos"][star], (
            star, ours["main_stars_positions"][star], ref["main_pos"][star])

    ours_aux = {**ours["lucky_stars_positions"], **ours["malefic_stars_positions"]}
    assert AUX <= set(ours_aux), ("辅星集合不完整", AUX - set(ours_aux))
    for star in sorted(AUX):
        assert ours_aux[star] == ref["aux_pos"][star], (
            star, ours_aux[star], ref["aux_pos"][star])

    # 生年四化. 壬 is the contested stem (维基文库's 卷二 transcription reads
    # 天府化科, mainstream and iztro read 左辅); locking all four against an
    # independent engine says which side this project is actually on.
    assert set(ours["four_transformations_native"]) == SI_HUA, (
        "四化不齐", SI_HUA ^ set(ours["four_transformations_native"]))
    for hua in sorted(SI_HUA):
        assert ours["four_transformations_native"][hua] == ref["mutagen"][hua], (
            hua, ours["four_transformations_native"][hua], ref["mutagen"][hua])

    ours_pal = {p["name"]: p["branch"] for p in ours["twelve_palaces"]}
    assert set(ours_pal) == PALACES, ("十二宫不齐", PALACES ^ set(ours_pal))
    assert len(ours["twelve_palaces"]) == 12
    for name in sorted(PALACES):
        assert ours_pal[name] == ref["palaces"][name], (
            name, ours_pal[name], ref["palaces"][name])


# 补齐 ZIWEI_TABLE 的 9 个盲格 —— 主网格 (步长 97 天 × 3 时辰) 只命中
# 141/150 个 (五行局, 农历日) 组合。改这 9 格中任何一格, 全量套件此前全绿,
# 而该格一动, 命中它的每张盘 14 主星全移、格局改写。
# 日期由穷举 1950-1970 找出, 每格取第一个命中日。
ZIWEI_TABLE_BLIND_SPOTS = [
    ("1950-02-17", 2, 1),  ("1950-03-01", 2, 13),
    ("1950-12-03", 3, 24), ("1951-01-07", 3, 30),
    ("1950-02-07", 4, 21),
    ("1950-03-25", 5, 8),  ("1950-01-08", 5, 20),
    ("1950-06-01", 6, 16), ("1950-06-13", 6, 28),
]


@pytest.mark.parametrize("iso,ju,lday", ZIWEI_TABLE_BLIND_SPOTS,
                         ids=[f"ju{j}-day{d}" for _, j, d in ZIWEI_TABLE_BLIND_SPOTS])
def test_ziwei_table_blind_spots_agree_with_iztro(iso, ju, lday):
    """主网格够不到的 9 格, 逐格对 iztro 比对。"""
    y, m, d = (int(x) for x in iso.split("-"))
    ours = _ours(y, m, d, 10, "male")
    assert ours["wuxing_ju"]["number"] == ju, (iso, ours["wuxing_ju"])
    assert ours["lunar_date"]["day"] == lday, (iso, ours["lunar_date"])

    ref = _iztro(y, m, d, 10, "male")
    assert ours["ming_gong"]["branch"] == ref["ming"], iso
    assert ours["wuxing_ju"]["name"] == ref["wuxing_ju"], iso
    for star in sorted(MAIN):
        assert ours["main_stars_positions"][star] == ref["main_pos"][star], (
            iso, star)


def test_the_grid_plus_blind_spots_cover_every_ziwei_table_cell():
    """覆盖面本身要有断言 —— 否则下次网格参数一调, 盲格重现而无人知。"""
    covered = {(ju, d) for _, ju, d in ZIWEI_TABLE_BLIND_SPOTS}
    for day in _grid():
        for hour in (0, 10, 23):
            ours = _ours(day.year, day.month, day.day, hour,
                         "male" if day.year % 2 else "female")
            covered.add((ours["wuxing_ju"]["number"], ours["lunar_date"]["day"]))
    missing = sorted({(ju, d) for ju in (2, 3, 4, 5, 6) for d in range(1, 31)}
                     - covered)
    assert not missing, (
        f"ZIWEI_TABLE 有 {len(missing)} 格没有任何用例命中, 改坏不会被发现: {missing}")
