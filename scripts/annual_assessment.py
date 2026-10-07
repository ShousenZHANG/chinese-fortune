"""流年: the year's pillar (太岁) against the person's day pillar, month and luck cycle.

Year-level passages answer a year-level question: 《渊海子平》 论太岁吉凶 and
论征太岁, 《三命通会》 总论岁运, 《滴天髓》 岁运论. Each relation found carries
its quote and the passage's own verdict word; where the passage leaves the
outcome to the whole chart (有无救助, 日主喜忌), it is said so. No total grade
is made from the hits, and nothing here reaches below the year.
"""
from __future__ import annotations

import re

from bazi_tables import DIZHI_CHONG, TIANGAN_HE
from utils import DIZHI_WUXING, TIANGAN_WUXING, TIANGAN_YIN_YANG, WUXING_GEN, WUXING_KE

YUANHAI_SUI = ('yuanhai:c161:p0002', 'a90d8f4e63fc534563ed3ef0f65e5ef5e7a1c329a78a8ad569b6e9d25f58f6e4')
YUANHAI_ZHENG = ('yuanhai:c174:p0003', '349a2404b1ff1d864f2e86a7496eb296be59213fcbcb905a39560817e4c934f4')
YUANHAI_HUI = ('yuanhai:c174:p0004', '3c6e80e909529aedb18812ea25fef52692fcdfa6c79e3a9e67368a6d036172ea')
SANMING_LIGHT = ('sanming:c011:p0118', '7437cfd454a85b40feef7a9167c18118628b13f4ad1e04b4d29e1ca62a41d56f')
SANMING_SUIYUN = ('sanming:c002:p0032', '88a834d8dba163c4806983e3a9e83ae6bec0b4155ecb963656028287e9631597')
DITIAN = ('ditian:c009:p0001', 'd1f02d205e375bb5bfd82b27bd6579ed83de47a90e01ee0f3c42f6a01ebd22fd')


def _rule(rule_id: str, label: str, source: tuple[str, str], quote: str, verdict: str, plain: str) -> dict:
    return {'id': rule_id, 'label': label, 'passage_id': source[0], 'sha256': source[1], 'quote': quote,
            'verdict': verdict, 'plain': plain}


RULES = {r['id']: r for r in (
    _rule('day_offends_year', '日犯岁君', YUANHAI_SUI, '日犯岁君，灾殃必重，五行有救，其年反必招财', '凶',
          '你的日干克这一年的天干'),
    _rule('year_hurts_day', '岁伤日干', SANMING_LIGHT, '歲傷日干有禍必輕', '祸轻', '这一年的天干克你的日干'),
    _rule('obscured', '晦气', YUANHAI_HUI, '日干支合太岁干支，曰晦，大运会岁干者亦然。遇此主晦气一年，反复，欲速不达', '晦',
          '你的日干和这一年的天干相合'),
    _rule('day_branch_clash', '征（日支冲太岁）', YUANHAI_ZHENG, '但看八字有无救助', '看救助',
          '你的日支和这一年的地支相冲'),
    _rule('fuyin', '伏吟', SANMING_SUIYUN, '嵗運壓日謂之伏吟二者不利六親非横破財不為吉兆', '不利',
          '这一年的干支和你的日柱相同'),
    _rule('fanyin', '返吟', SANMING_SUIYUN, '若嵗運與日相對謂之返吟', '不利',
          '这一年的天干克你的日干，地支又冲你的日支'),
    _rule('month_clash', '冲月', SANMING_SUIYUN, '若嵗運衝月必禍', '祸', '这一年的地支冲你的月支'),
    _rule('cycle_overcomes_year', '运克岁', SANMING_SUIYUN, '運衝尅嵗者凶', '凶', '你当步大运的天干克这一年的天干'),
    _rule('year_overcomes_cycle', '岁克运', SANMING_SUIYUN, '經云嵗衝尅運者吉', '吉', '这一年的天干克你当步大运的天干'),
    _rule('cycle_year_generate', '岁运相生', SANMING_SUIYUN, '嵗運相生者吉', '吉', '当步大运和这一年的天干相生'),
    _rule('cycle_year_clash', '岁运相冲', DITIAN, '休咎係乎運，尤係乎歲，衝戰視其孰降，和好視其孰切', '看喜忌',
          '当步大运和这一年的地支相冲'),
    _rule('cycle_year_combine', '岁运相合', DITIAN, '休咎係乎運，尤係乎歲，衝戰視其孰降，和好視其孰切', '看喜忌',
          '当步大运和这一年的天干相合'),
)}
# The rescue passage: 「干头需要庚辛……或得己和甲亦解之」, 「八字庚辛酉巳丑金局也」.
FRAMES = {'水': (('申', '子', '辰'), ('亥', '子', '丑')), '火': (('寅', '午', '戌'), ('巳', '午', '未')),
          '木': (('亥', '卯', '未'), ('寅', '卯', '辰')), '金': (('巳', '酉', '丑'), ('申', '酉', '戌'))}
WORD = {'凶': '凶', '祸轻': '有祸但轻', '晦': '晦气', '看救助': '看八字有无救助', '不利': '不利',
        '祸': '有祸', '吉': '吉', '看喜忌': '要看日主喜什么', '有救': '有救，反主得财'}
LIMIT = '一年一个说法，按这一年的干支和你的日柱、月柱、当步大运比；有没有救、日主喜什么，原文要看整张盘，这里只列能算的关系。'


def _overcomes(a: str, b: str) -> bool:
    return WUXING_KE.get(TIANGAN_WUXING.get(a, '')) == TIANGAN_WUXING.get(b)


def _clash(a: str | None, b: str | None) -> bool:
    return bool(a and b) and frozenset((a, b)) in DIZHI_CHONG


def _rescue(chart: dict) -> list[str]:
    """What checks or combines the day stem: a stem that overcomes it, one that
    combines with it, or a complete branch frame of the element that overcomes it."""
    pillars = chart['four_pillars']
    day = chart['day_master']['stem']
    found = [f"{p}干{pillars[p]['stem']}" for p in ('year', 'month', 'hour')
             if (pillars.get(p) or {}).get('stem') and (_overcomes(pillars[p]['stem'], day)
                                                       or frozenset((pillars[p]['stem'], day)) in TIANGAN_HE)]
    enemy = next((w for w, target in WUXING_KE.items() if target == TIANGAN_WUXING[day]), None)
    branches = {(pillars.get(p) or {}).get('branch') for p in ('year', 'month', 'day', 'hour')}
    for frame in FRAMES.get(enemy or '', ()):
        if set(frame) <= branches:
            found.append(f"地支{''.join(frame)}成{enemy}局")
    return found


def _hit(rule_id: str, **extra: object) -> dict:
    rule = RULES[rule_id]
    return {'id': rule_id, 'label': rule['label'], 'verdict': rule['verdict'], 'plain': rule['plain'],
            'quote': rule['quote'], 'passage_id': rule['passage_id'], **extra}


def assess_year(chart: dict, year: int, ganzhi: str, cycle: dict | None = None,
                luck_stem: str | None = None) -> dict:
    """The relations of one year's pillar with this chart, each with its passage."""
    pillars = chart.get('four_pillars') or {}
    day = (pillars.get('day') or {})
    if not day.get('stem') or not day.get('branch'):
        return {'status': 'unavailable', 'year': year, 'ganzhi': ganzhi, 'reason': '日柱没定，比不了太岁', 'limit': LIMIT}
    stem, branch = ganzhi[0], ganzhi[1]
    hits: list[dict] = []
    if ganzhi == day['stem'] + day['branch']:
        hits.append(_hit('fuyin'))
    if _overcomes(day['stem'], stem):
        rescue = _rescue(chart)
        extra: dict = {'rescue': rescue}
        if rescue:
            extra['verdict'] = '有救'
        # 三命：行好运而日干伤流年天元为祸轻，行不好运为祸重.
        if luck_stem in ('favoured', 'avoided'):
            extra['luck_weight'] = '祸轻' if luck_stem == 'favoured' else '祸重'
        hits.append(_hit('day_offends_year', **extra))
    if _overcomes(stem, day['stem']):
        hits.append(_hit('fanyin' if _clash(branch, day['branch']) else 'year_hurts_day'))
    if frozenset((day['stem'], stem)) in TIANGAN_HE:
        # 「日干合太嵗如甲日巳年之例太嵗合日干如巳日甲年之例甲合巳災重巳合甲災輕」
        heavy = TIANGAN_YIN_YANG.get(day['stem']) == '阳'
        hits.append(_hit('obscured', weight='灾重' if heavy else '灾轻',
                         weight_quote='甲合巳災重巳合甲災輕', weight_passage=SANMING_SUIYUN[0]))
    if _clash(branch, day['branch']) and not any(h['id'] == 'fanyin' for h in hits):
        hits.append(_hit('day_branch_clash'))
    if _clash(branch, (pillars.get('month') or {}).get('branch')):
        hits.append(_hit('month_clash'))
    if cycle and cycle.get('ganzhi'):
        c_stem, c_branch = cycle['ganzhi'][0], cycle['ganzhi'][1]
        if _overcomes(c_stem, stem):
            hits.append(_hit('cycle_overcomes_year', cycle=cycle['ganzhi']))
        elif _overcomes(stem, c_stem):
            hits.append(_hit('year_overcomes_cycle', cycle=cycle['ganzhi']))
        elif WUXING_GEN.get(TIANGAN_WUXING[c_stem]) == TIANGAN_WUXING[stem] or \
                WUXING_GEN.get(TIANGAN_WUXING[stem]) == TIANGAN_WUXING[c_stem]:
            hits.append(_hit('cycle_year_generate', cycle=cycle['ganzhi']))
        if frozenset((c_stem, stem)) in TIANGAN_HE:
            hits.append(_hit('cycle_year_combine', cycle=cycle['ganzhi']))
        if _clash(c_branch, branch):
            hits.append(_hit('cycle_year_clash', cycle=cycle['ganzhi']))
    limit = LIMIT if chart.get('hour_known') else LIMIT + '出生时辰未知：只用年、月、日柱，时柱的救助没算。'
    return {'status': 'assessed', 'year': year, 'ganzhi': ganzhi, 'cycle': (cycle or {}).get('ganzhi'),
            'hits': hits, 'limit': limit,
            'branch_element': DIZHI_WUXING.get(branch)}


def annual_paragraph(reading: dict) -> str:
    """One year, its relations and the passages, in plain words."""
    if reading.get('year') is None:
        return f"流年这次给不出：{reading['reason']}。"
    head = f"{reading['year']}年（{reading['ganzhi']}）"
    if reading['status'] != 'assessed':
        return f"{head}：这次比不了，{reading['reason']}。"
    if not reading['hits']:
        return head + '：这一年的干支和你的日柱、月柱' + ('、当步大运' if reading.get('cycle') else '') + \
            '之间，没有原文所说的冲、克、合、伏吟、返吟，书里对这一年没有专门的说法。' + LIMIT
    parts = []
    for hit in reading['hits']:
        line = f"{hit['label']}——{hit['plain']}，原文「{hit['quote']}」（{hit['passage_id']}），按原文是{WORD[hit['verdict']]}"
        if hit['id'] == 'day_offends_year':
            line += (f"：你的盘里有{'、'.join(hit['rescue'])}能制住或合住日干，原文说这样算有救" if hit['rescue']
                     else '：你的盘天干里没有能制住或合住日干的字，地支也不成相应的局')
            if hit.get('luck_weight'):
                line += f"；当步大运按前面的取运判断，三命说这样{hit['luck_weight']}"
        if hit.get('weight'):
            line += f"，原文「{hit['weight_quote']}」，你这种是{hit['weight']}"
        parts.append(line)
    return head + '：' + '；'.join(parts) + '。' + reading['limit']


YEAR_WORDS = re.compile(r'(?<!\d)(20\d{2}|19\d{2})(?!\d)')


def years_asked(question: str, now_year: int | None) -> list[int]:
    """The calendar years a question asks about, in order; at most three."""
    years = [int(y) for y in YEAR_WORDS.findall(question or '')]
    if not years and now_year is not None:
        if '这几年' in question or '未来几年' in question:
            years = [now_year, now_year + 1, now_year + 2]
        elif '明年' in question:
            years = [now_year + 1]
        elif '后年' in question:
            years = [now_year + 2]
        elif any(w in question for w in ('今年', '流年', '这一年', '本年')):
            years = [now_year]
    return list(dict.fromkeys(years))[:3]


ANNUAL_WORDS = ('流年', '今年', '明年', '后年', '这几年', '未来几年', '这一年')


def year_pillar(year: int) -> str:
    """The pillar of a calendar year, read in mid-year (after 立春)."""
    from lunar_python import Solar  # type: ignore
    return Solar.fromYmdHms(year, 6, 1, 12, 0, 0).getLunar().getYearInGanZhiExact()


def annual_readings(chart: dict, years: list[int]) -> list[dict]:
    """Each asked year against the chart, with the luck cycle it falls in."""
    from luck_assessment import assess_luck
    readings = []
    for year in years:
        cycle = next((c for c in chart.get('da_yun') or [] if c['start_year'] <= year <= c['end_year']), None)
        luck = assess_luck(chart, cycle) if cycle else None
        stem = luck['summary']['stem'] if luck and luck['status'] == 'assessed' else None
        readings.append(assess_year(chart, year, year_pillar(year), cycle, stem))
    return readings


def unknown_year(reason: str) -> dict:
    return {'status': 'unavailable', 'year': None, 'ganzhi': '', 'reason': reason, 'limit': LIMIT}
