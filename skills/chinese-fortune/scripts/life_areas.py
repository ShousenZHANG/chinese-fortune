"""人生领域速读：事业、财运、感情、学业各看哪颗星、哪一宫，原局在哪，当步大运和最近几年流年哪年透出。

只列位置和年份，不判好坏：《子平真诠》论行运说运岁每一字都要「配命中八字而统观之，爲喜爲忌」
（ziping:c025:p0001），本盘用神未定时喜忌就未定。每个领域写明古籍按什么看：

- 事业：古籍以官星论贵（ziping:c031:p0001），「事业」是现代说法，属类比。
- 财运：财为财帛（ziping:c033:p0001）。
- 感情：男看妻宫（日支）与妻星（财）（ziping:c024:p0002、p0003）；女以官为夫（yuanhai:c189:p0163）。
- 学业：日干长生在月支或时支为学堂，刑冲破损则读书难成（sanming:c003:p0013）。

健康不在这里：古籍的疾病、夭寿说法不用来断个人健康。
"""
from __future__ import annotations

from utils import chong_branch, shi_shen

AREA_WORDS = {
    'career': ('事业', '工作', '升职', '跳槽', '职场', '仕途', '当官'),
    'wealth': ('财运', '收入', '赚钱', '发财', '钱财'),
    'relationship': ('感情', '婚姻', '恋爱', '对象', '姻缘', '桃花', '配偶', '另一半', '结婚', '离婚', '订婚', '分手'),
    'study': ('学业', '读书', '升学', '考研', '考公', '学习运'),
}
ALL_WORDS = ('人生领域', '各方面', '整体运势', '全面看', '速读')
LABELS = {'career': '事业', 'wealth': '财运', 'relationship': '感情', 'study': '学业'}
PILLARS = (('year', '年柱'), ('month', '月柱'), ('day', '日柱'), ('hour', '时柱'))
# 长生：阳干顺、阴干逆（sanming:c003:p0013「甲見亥乙見午等例」）。
CHANGSHENG = {'甲': '亥', '丙': '寅', '戊': '寅', '庚': '巳', '壬': '申',
              '乙': '午', '丁': '酉', '己': '酉', '辛': '子', '癸': '卯'}
YEARS_AHEAD = 3

SOURCES = {
    'career': [('ziping:c031:p0001', '正官者，分所當尊', '古籍以官星论贵；用于现代事业是类比')],
    'wealth': [('ziping:c033:p0001', '爲財帛，爲妻妾，爲才能', '财为财帛')],
    'relationship_male': [('ziping:c024:p0003', '既看妻宮，又看妻星。妻星者，干頭之財也', '妻宫与妻星'),
                          ('ziping:c024:p0002', '以妻論之，坐下財官，妻當賢貴', '妻宫是日支（坐下）')],
    'relationship_female': [('yuanhai:c189:p0163', '如女命戊日生，以乙木为夫', '女命以官为夫'),
                            ('yuanhai:c189:p0163', '又不专以夫星定之', '原文说不只看夫星')],
    'study': [('sanming:c003:p0013', '五行長生之神乃甲見亥乙見午等例或月時一位見者即是', '学堂：日干长生在月或时'),
              ('sanming:c003:p0013', '但有刑衝破損讀書便不成', '学堂逢冲')],
    'timing': [('ziping:c025:p0001', '運中每運行一字，即必以此一字，配命中八字而統觀之，爲喜爲忌', '运岁要配原局喜忌')],
}


def areas_asked(question: str) -> list[str]:
    if any(word in question for word in ALL_WORDS):
        return list(LABELS)
    return [area for area, words in AREA_WORDS.items() if any(word in question for word in words)]


def _sources(key: str) -> list[dict]:
    return [{'passage_id': pid, 'quote': quote, 'use': use} for pid, quote, use in SOURCES[key]]


def _positions(facts: dict, stars: tuple[str, ...]) -> list[str]:
    day = facts['day_master'].get('stem')
    found = []
    for key, label in PILLARS:
        pillar = facts['four_pillars'].get(key) or {}
        stem = pillar.get('stem')
        if day and stem and key != 'day' and shi_shen(day, stem) in stars:
            found.append(f'{label}天干{stem}（{shi_shen(day, stem)}）')
        for hidden in pillar.get('hidden_stems') or []:
            if day and shi_shen(day, hidden) in stars:
                found.append(f"{label}{pillar.get('branch', '')}藏{hidden}（{shi_shen(day, hidden)}）")
    return found


def _timing(facts: dict, stars: tuple[str, ...]) -> dict:
    day, year = facts['day_master'].get('stem'), facts.get('reference_year')
    cycle = next((c for c in facts.get('da_yun') or [] if isinstance(year, int)
                  and c.get('start_year') and c['start_year'] <= year <= c['end_year']), None)
    out: dict = {'reference_year': year}
    if cycle and day:
        role = shi_shen(day, cycle['stem'])
        out['current_cycle'] = {'ganzhi': cycle['ganzhi'], 'years': f"{cycle['start_year']}–{cycle['end_year']}",
                                'stem_role': role, 'brings_star': role in stars}
    if isinstance(year, int) and day:
        rows = []
        for y in range(year, year + YEARS_AHEAD):
            stem = '甲乙丙丁戊己庚辛壬癸'[(y - 4) % 10]
            branch = '子丑寅卯辰巳午未申酉戌亥'[(y - 4) % 12]
            rows.append({'year': y, 'ganzhi': stem + branch, 'stem_role': shi_shen(day, stem),
                         'brings_star': shi_shen(day, stem) in stars})
        out['years'] = rows
    return out


def _star_area(area: str, stars: tuple[str, ...], facts: dict, sources: list[dict]) -> dict:
    found = _positions(facts, stars)
    timing = _timing(facts, stars)
    star_years = [r['year'] for r in timing.get('years', []) if r['brings_star']]
    cycle = timing.get('current_cycle')
    say = (f"{LABELS[area]}看{'、'.join(stars)}：原局" + ('、'.join(found) if found else '天干地支里都没有') + '。')
    if cycle:
        say += f"当步 {cycle['ganzhi']} 运天干是{cycle['stem_role']}" + ('，正是这颗星' if cycle['brings_star'] else '') + '；'
    if timing.get('years'):
        say += (f"{'、'.join(map(str, star_years))} 年流年天干透出这颗星" if star_years
                else f"{timing['years'][0]['year']}–{timing['years'][-1]['year']} 年流年天干都不是这颗星")
        say += '。是喜是忌要配原局用神，本盘用神未定就不说好坏。'
    return {'area': area, 'label': LABELS[area], 'stars': list(stars), 'natal': found, 'timing': timing,
            'sources': sources + _sources('timing'), 'say': say}


def _relationship(facts: dict, gender: str | None) -> dict:
    if gender not in ('male', 'female'):
        return {'area': 'relationship', 'label': '感情', 'status': 'gender_required',
                'say': '感情要分男女看（男看财为妻星，女看官为夫星），先确认性别。', 'sources': []}
    stars = ('正财', '偏财') if gender == 'male' else ('正官', '七杀')
    key = 'relationship_' + gender
    out = _star_area('relationship', stars, facts, _sources(key))
    day = facts['four_pillars'].get('day') or {}
    if day.get('branch'):
        palace = day['branch']
        clashed = [label for k, label in PILLARS if k != 'day'
                   and (facts['four_pillars'].get(k) or {}).get('branch') == chong_branch(palace)]
        out['palace'] = {'branch': palace, 'hidden': day.get('hidden_stems') or [], 'clashed_by': clashed}
        out['say'] = f"日支{palace}是{'妻' if gender == 'male' else '夫'}宫。" + out['say']
    if gender == 'female':
        out['say'] += '原文也说「又不专以夫星定之」，无夫星不等于无夫。'
    return out


def _study(facts: dict) -> dict:
    day = facts['day_master'].get('stem')
    target = CHANGSHENG.get(day or '')
    hits = [label for key, label in PILLARS if key in ('month', 'hour')
            and (facts['four_pillars'].get(key) or {}).get('branch') == target]
    branches = [(facts['four_pillars'].get(k) or {}).get('branch') for k, _ in PILLARS]
    clashed = bool(target) and chong_branch(target or '') in branches
    if not day:
        say = '日干未定，学堂看不了。'
    elif hits:
        say = (f"日干{day}长生在{target}，{'、'.join(hits)}地支是{target}，按《三命通会》学堂诸说属带学堂"
               + ('；但盘里有冲它的字，原文说「刑衝破損讀書便不成」' if clashed else '') + '。')
    else:
        say = f"日干{day}长生在{target}，月支、时支都不是{target}，按这一条不算带学堂；原文另有学堂会禄等多说，这里没算。"
    return {'area': 'study', 'label': '学业', 'rule': '日干长生在月支或时支为学堂', 'changsheng': target,
            'hits': hits, 'clashed': clashed, 'sources': _sources('study'), 'say': say,
            'not_computed': '学堂会禄、会食、官星学堂、魁星等其余诸说'}


def life_areas(facts: dict, gender: str | None, areas: list[str]) -> dict:
    out = []
    for area in areas:
        if area == 'career':
            out.append(_star_area('career', ('正官', '七杀'), facts, _sources('career')))
        elif area == 'wealth':
            out.append(_star_area('wealth', ('正财', '偏财'), facts, _sources('wealth')))
        elif area == 'relationship':
            out.append(_relationship(facts, gender))
        elif area == 'study':
            out.append(_study(facts))
    return {'areas': out, 'boundary': '只列古籍看哪颗星、原局在哪、哪年透出；不判好坏，不做健康断语，现代领域是类比'}
