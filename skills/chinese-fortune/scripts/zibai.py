"""紫白九星：年、月哪颗星入中宫，九星飞布到哪一宫，按《钦定协纪辨方书》卷八「三元九星」各条。

- 年：康熙二十三年甲子为上元；上元甲子一白入中、中元四绿、下元七赤，逐年逆转，一百八十年一周
  （xieji:c008:p0024，书中六十年三元表逐格复算见测试）。
- 月：子午卯酉年正月八白、辰戌丑未年五黄、寅申巳亥年二黑，逐月逆转，三年一周（xieji:c008:p0025）。
- 飞布：入中之星顺布九宫，中→乾→兑→艮→离→坎→坤→震→巽（同段康熙甲子例）。
- 换年按立春、换月按节，北京时间（xieji:c034:p0024「如已過立春後年月凶神方位已定」，xieji:c020:p0003「立春正月節」）。

只排星，不判每颗星吉凶。《协纪》所引宗镜说某方「得年家月家之紫白」也可修（xieji:c034:p0016），
《选择要略》说「遇三白，九紫」（xuanze:c002:p0532）；这里只标一白、六白、八白、九紫是否到方。
日、时紫白《协纪》未载；《选择要略》的日白法以「冬至前後甲子」分元，取哪个甲子原文未定，所以不算。

CLI:
    python zibai.py --date 2026-11-08 [--time 09:30] [--sitting 子]
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from typing import Any

from fengshui_measure import MOUNTAINS, PALACE
from utils import __version__, ensure_utf8_stdio, error_envelope, jiazi_index, json_print

STARS = ('一白', '二黑', '三碧', '四绿', '五黄', '六白', '七赤', '八白', '九紫')
# 入中之星顺布：中五、乾六、兑七、艮八、离九、坎一、坤二、震三、巽四。
PALACE_ORDER = ('中', '乾', '兑', '艮', '离', '坎', '坤', '震', '巽')
YUAN = ('上元', '中元', '下元')
YEAR_START = (1, 4, 7)          # 上元甲子一白，中元四绿，下元七赤
MONTH_START = (8, 5, 2)         # 子午卯酉、辰戌丑未、寅申巳亥年正月
MONTH_GROUP = {b: i for i, group in enumerate(('子午卯酉', '辰戌丑未', '寅申巳亥')) for b in group}
MONTH_BRANCHES = '寅卯辰巳午未申酉戌亥子丑'
MONTH_NAMES = ('正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二')
ANCHOR = 1684                   # 康熙二十三年甲子，上元
ZIBAI = frozenset({'一白', '六白', '八白', '九紫'})
OPPOSITE = {m: MOUNTAINS[(i + 12) % 24] for i, m in enumerate(MOUNTAINS)}
YEARS = (1600, 2300)

SOURCES = (
    ('xieji:c008:p0024', '上元甲子中宫起一白中元甲子起四緑下元甲子起七赤', '年星入中与三元'),
    ('xieji:c008:p0024', '康熙二十三年甲子為上元', '三元起算'),
    ('xieji:c008:p0024', '以其年所值星入中宫順布九宫', '飞布'),
    ('xieji:c008:p0025', '子午卯酉年為上元正月起八白辰戌丑未年為中元正月起五黄寅申巳亥年為下元正月起二黑逐月逆轉',
     '月星入中'),
    ('xieji:c008:p0022', '一白居坎二黑居坤三碧居震四緑居巽五黄居中六白居乾七赤居兌八白居艮九紫居離', '九宫地盘'),
    ('xieji:c008:p0038', '太嵗即三元年九星入中宫之一星', '月盘里年星所在'),
    ('xieji:c034:p0024', '如已過立春後年月凶神方位已定', '换年按立春'),
    ('xieji:c020:p0003', '立春正月節', '换月按节'),
    ('xieji:c034:p0016', '得年家月家之紫白或太陽三竒亦可修也', '紫白到方'),
    ('xuanze:c002:p0532', '遇三白，九紫', '哪几颗算紫白'),
)
NOT_COMPUTED = [{'item': '日紫白、时紫白',
                 'reason': '《协纪辨方书》未载；《选择要略》日白法以「冬至前後甲子」分元，取冬至前还是后的甲子原文未定'}]


def _star(number: int) -> int:
    return (number - 1) % 9 + 1


def year_center(yuan: int, ganzhi_index: int) -> int:
    """Star number entering the centre in the year with this sexagenary index inside 上/中/下元 (0/1/2)."""
    return _star(YEAR_START[yuan] - ganzhi_index)


def month_center(group: int, month_index: int) -> int:
    """Star number entering the centre in month 正月=0 … 十二月=11 of a 子午卯酉/辰戌丑未/寅申巳亥 (0/1/2) year."""
    return _star(MONTH_START[group] - month_index)


def layout(center: int) -> dict[str, str]:
    return {palace: STARS[_star(center + i) - 1] for i, palace in enumerate(PALACE_ORDER)}


def _parse(day: str, time: str | None) -> tuple[date, int, int]:
    try:
        when = date.fromisoformat(day)
    except (TypeError, ValueError):
        raise ValueError(f'日期要写成 YYYY-MM-DD：{day!r}') from None
    if not YEARS[0] <= when.year <= YEARS[1]:
        raise ValueError(f'日期须在 {YEARS[0]}–{YEARS[1]} 年之间')
    if time is None:
        return when, 12, 0
    match = re.fullmatch(r'([01]?\d|2[0-3]):([0-5]\d)', time)
    if not match:
        raise ValueError(f'时间要写成 HH:MM（北京时间）：{time!r}')
    return when, int(match.group(1)), int(match.group(2))


def _lunar(when: date, hour: int, minute: int, second: int = 0) -> Any:
    from lunar_python import Solar
    return Solar.fromYmdHms(when.year, when.month, when.day, hour, minute, second).getLunar()


def _chart(when: date, hour: int, minute: int) -> dict:
    lunar = _lunar(when, hour, minute)
    year_gz, branch = lunar.getYearInGanZhiExact(), lunar.getMonthZhiExact()
    index = jiazi_index(year_gz[0], year_gz[1])
    number = when.year if index == (when.year - 4) % 60 else when.year - 1
    yuan = ((number - ANCHOR) // 60) % 3
    y_center = year_center(yuan, index)
    month = MONTH_BRANCHES.index(branch)
    m_center = month_center(MONTH_GROUP[year_gz[1]], month)
    y_layout, m_layout = layout(y_center), layout(m_center)
    return {
        'calendar': {'year_ganzhi': year_gz, 'year_number': number, 'month_branch': branch,
                     'month_name': MONTH_NAMES[month] + '月', 'convention': '换年按立春、换月按节，北京时间'},
        'year': {'yuan': YUAN[yuan], 'center': STARS[y_center - 1], 'palaces': y_layout},
        'month': {'center': STARS[m_center - 1], 'palaces': m_layout,
                  'year_star_palace': next(p for p, s in m_layout.items() if s == STARS[y_center - 1])},
    }


def _directions(chart: dict, sitting: list[str]) -> list[dict]:
    rows = []
    for mountain in sitting:
        if mountain not in PALACE:
            raise ValueError(f'坐山须是二十四山之一（{"".join(MOUNTAINS)}）：{mountain!r}')
        for role, name in (('坐', mountain), ('向', OPPOSITE[mountain])):
            palace = PALACE[name]
            year_star, month_star = chart['year']['palaces'][palace], chart['month']['palaces'][palace]
            rows.append({'role': role, 'mountain': name, 'palace': palace, 'year_star': year_star,
                         'month_star': month_star, 'year_zibai': year_star in ZIBAI, 'month_zibai': month_star in ZIBAI,
                         'zibai_to_direction': year_star in ZIBAI or month_star in ZIBAI})
    return rows


def _say(chart: dict) -> str:
    cal, year, month = chart['calendar'], chart['year'], chart['month']
    text = (f"{cal['year_number']}年{cal['year_ganzhi']}属{year['yuan']}，{year['center']}入中；"
            f"{cal['month_name']}（{cal['month_branch']}月）{month['center']}入中，"
            f"年星{year['center']}在月盘落{month['year_star_palace']}宫。")
    for row in chart.get('directions', []):
        mark = '，紫白到' if row['zibai_to_direction'] else ''
        text += f"{row['role']}{row['mountain']}（{row['palace']}宫）年星{row['year_star']}、月星{row['month_star']}{mark}；"
    return text.rstrip('；') + ('。' if chart.get('directions') else '')


def zibai(day: str, time: str | None = None, sitting: list[str] | None = None) -> dict:
    when, hour, minute = _parse(day, time)
    sources = [{'passage_id': pid, 'quote': quote, 'use': use} for pid, quote, use in SOURCES]
    base = {'input': {'date': day, 'time': time, 'sitting': list(sitting or [])}, 'sources': sources,
            'not_computed': NOT_COMPUTED,
            'scope': '只排入中与飞布；一白、六白、八白、九紫只标是否到方，不判每颗星吉凶'}
    first, last = _lunar(when, 0, 0), _lunar(when, 23, 59, 59)
    if time is None and (first.getYearInGanZhiExact(), first.getMonthZhiExact()) != (
            last.getYearInGanZhiExact(), last.getMonthZhiExact()):
        jie = last.getPrevJie()
        moment = jie.getSolar().toYmdHms()
        candidates = []
        for h, m in ((0, 0), (23, 59)):
            chart = _chart(when, h, m)
            chart['directions'] = _directions(chart, list(sitting or []))
            chart['say'] = _say(chart)
            candidates.append(chart)
        return {**base, 'boundary': {'jie': jie.getName(), 'moment': moment},
                'candidates': candidates,
                'say': f"{day} 是{jie.getName()}日，交节在 {moment[11:16]}（北京时间），交节前后入中星不同；"
                       '给 --time 再算，两种都列在 candidates。'}
    chart = _chart(when, hour, minute)
    chart['directions'] = _directions(chart, list(sitting or []))
    return {**base, **chart, 'say': _say(chart)}


EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version input calendar year month directions sources not_computed scope say
  on a 节 day without --time: boundary candidates instead of calendar year month directions

On error: {"ok": false, "error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='紫白九星：年、月入中与九宫飞布（协纪辨方书卷八），可接坐山',
                                epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--date', required=True, help='公历日期 YYYY-MM-DD')
    p.add_argument('--time', help='北京时间 HH:MM；只有交节那天会用到，不给时交节日两种都列')
    p.add_argument('--sitting', action='append', default=[],
                   help='坐山（二十四山之一，可用 fengshui_measure.py 换算）；误差跨山时每个候选各给一次')
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        result = zibai(args.date, args.time, args.sitting)
    except ValueError as exc:
        json_print(error_envelope('zibai', 'invalid_input', str(exc)))
        return 1
    json_print({'ok': True, 'tool': 'zibai', 'version': __version__, **result})
    return 0


if __name__ == '__main__':
    sys.exit(main())
