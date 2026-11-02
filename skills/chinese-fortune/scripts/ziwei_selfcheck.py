"""紫微盘面自检: 用安星规则之间互相约束的关系, 复核一张已排好的盘.

只读输出字典, 不重新排盘, 所以输出在任何一步被改坏 (手抄、序列化、宿主转述
前的中间处理) 都能查出来。每项写明依据; 不判吉凶。
"""
from __future__ import annotations

from utils import DIZHI
from ziwei_stars import LU_CUN, MAIN_STARS, TIANFU_MIRROR, place_main_stars
from ziwei_tables import calc_ming_gong, stem_of_palace

# 身宫只落命、夫妻、财帛、迁移、官禄、福德六宫 (生时子午在命, 丑未在福德, 寅申在官禄,
# 卯酉在迁移, 辰戌在财帛, 巳亥在夫妻)。
SHEN_PALACES = ('命宫', '夫妻宫', '财帛宫', '迁移宫', '官禄宫', '福德宫')


def _check(name: str, ok: bool, detail: str) -> dict:
    return {'name': name, 'ok': ok, 'detail': detail}


def _names(palace: dict) -> list[str]:
    """main_stars holds dicts in the full view and bare names under --brief-palaces."""
    return [s['name'] if isinstance(s, dict) else s for s in palace['main_stars']]


def _main_stars(chart: dict) -> list[dict]:
    seen = [s for p in chart['twelve_palaces'] for s in _names(p)]
    missing = [s for s in MAIN_STARS if s not in seen]
    repeated = sorted({s for s in seen if seen.count(s) > 1})
    out = [_check('main_stars_complete', not missing and not repeated,
                  '14 主星各一次' if not missing and not repeated
                  else f"缺 {'、'.join(missing) or '无'}；重复 {'、'.join(repeated) or '无'}")]
    zw, tf = chart['main_stars_positions'].get('紫微'), chart['main_stars_positions'].get('天府')
    out.append(_check('ziwei_tianfu_mirror', bool(zw) and TIANFU_MIRROR.get(zw or '') == tf,
                      f'紫微{zw}、天府{tf}；天府须与紫微以寅申为轴对称'))
    # The other twelve stars sit at fixed offsets from 紫微 and 天府, so one star
    # moved to another palace breaks the layout even with all fourteen present.
    placed = {s: p['branch'] for p in chart['twelve_palaces'] for s in _names(p)}
    expected = place_main_stars(placed['紫微']) if '紫微' in placed else {}
    moved = sorted(s for s in MAIN_STARS if placed.get(s) != expected.get(s))
    out.append(_check('main_star_layout', not moved,
                      '其余主星都在紫微、天府系的固定位置' if not moved else f"不在固定位置：{'、'.join(moved)}"))
    return out


def _positions(chart: dict) -> list[dict]:
    """The *_positions maps repeat what the palaces show; the two copies must agree."""
    palaces = chart['twelve_palaces']
    views = [('main_stars_positions', lambda p: _names(p))]
    if 'lucky_stars' in palaces[0]:
        views += [('lucky_stars_positions', lambda p: p['lucky_stars']),
                  ('malefic_stars_positions', lambda p: p['malefic_stars']),
                  ('miscellaneous_stars_positions', lambda p: p['miscellaneous_stars'])]
    wrong = []
    for key, stars_of in views:
        shown = {s: p['branch'] for p in palaces for s in stars_of(p)}
        wrong += [f'{key}.{s}' for s, b in chart[key].items() if shown.get(s) != b]
    return [_check('positions_match_palaces', not wrong,
                   '星位表与各宫星曜一致' if not wrong else f"星位表与各宫不符：{'、'.join(wrong)}")]


def _palaces(chart: dict) -> list[dict]:
    palaces = chart['twelve_palaces']
    branches = [p['branch'] for p in palaces]
    order_ok = (len(set(branches)) == 12 and palaces[0]['branch'] == chart['ming_gong']['branch']
                and all((DIZHI.index(branches[i]) - DIZHI.index(branches[i + 1])) % 12 == 1 for i in range(11)))
    bad_stems = [p['branch'] for p in palaces if p['stem'] != stem_of_palace(chart['year_stem'], p['branch'])]
    shen = next((p['name'] for p in palaces if p['branch'] == chart['shen_gong']['branch']), None)
    hour = chart['solar_date']['hour']
    ming = calc_ming_gong(chart['lunar_date']['month'], hour)
    return [
        _check('palace_order', order_ok, '十二宫从命宫起逆行排布、地支不重复'),
        _check('palace_stems', not bad_stems,
               '宫干按五虎遁由年干起寅' if not bad_stems else f"宫干与五虎遁不符：{'、'.join(bad_stems)}"),
        _check('ming_gong_formula', ming == chart['ming_gong']['branch'],
               f"寅起正月顺数到生月、再逆数到生时，应为{ming}，盘上是{chart['ming_gong']['branch']}"),
        _check('shen_gong_palace', shen in SHEN_PALACES, f'身宫落{shen}；只能在命、夫妻、财帛、迁移、官禄、福德'),
    ]


def _stars(chart: dict) -> list[dict]:
    malefic = chart['malefic_stars_positions']
    lu = LU_CUN.get(chart['year_stem'])
    i = DIZHI.index(lu) if lu else 0
    flank = (malefic.get('禄存') == lu and malefic.get('擎羊') == DIZHI[(i + 1) % 12]
             and malefic.get('陀罗') == DIZHI[(i - 1) % 12])
    on_chart = {s for p in chart['twelve_palaces'] for s in _names(p) + p.get('lucky_stars', [])}
    lucky_shown = any('lucky_stars' in p for p in chart['twelve_palaces'])
    targets = list(chart['four_transformations_native'].values())
    absent = [t for t in targets if t not in on_chart] if lucky_shown else \
        [t for t in targets if t not in on_chart and t not in chart['lucky_stars_positions']]
    return [
        _check('lu_yang_tuo', flank, f'禄存{malefic.get("禄存")}按年干应在{lu}，擎羊在其后一位、陀罗在其前一位'),
        _check('sihua_on_chart', not absent,
               '生年四化的四颗星都在盘上' if not absent else f"化星不在盘上：{'、'.join(absent)}"),
    ]


def run_checks(chart: dict) -> list[dict]:
    return _main_stars(chart) + _positions(chart) + _palaces(chart) + _stars(chart)


def self_check(chart: dict) -> dict:
    """{ok, checked, failed} for a ziwei_calc output; details only for what failed."""
    checks = run_checks(chart)
    return {'ok': all(c['ok'] for c in checks), 'checked': [c['name'] for c in checks],
            'failed': [{'name': c['name'], 'detail': c['detail']} for c in checks if not c['ok']],
            'scope': '只核安星规则之间的互相约束，不核流派选择本身，也不判吉凶。'}
