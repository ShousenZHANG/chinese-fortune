"""紫微回答骨架: 可照抄的 say 句子, 以及按所问宫位整理的 focus 块.

结构借自 Renhuai ziwei-doushu 的分宫解读 (夫妻、事业等宫按主星分条), 断语不借:
这里只排列盘面事实和检索入口, 每条解释仍要取《全书》原文再说。
"""
from __future__ import annotations

import re

from classical_search import normalized, search_classics

PALACE_ALIASES = {
    '命': '命宫', '兄弟': '兄弟宫', '夫妻': '夫妻宫', '婚姻': '夫妻宫', '感情': '夫妻宫', '配偶': '夫妻宫',
    '子女': '子女宫', '财帛': '财帛宫', '财运': '财帛宫', '钱财': '财帛宫', '疾厄': '疾厄宫', '健康': '疾厄宫',
    '迁移': '迁移宫', '出行': '迁移宫', '奴仆': '奴仆宫', '交友': '奴仆宫', '朋友': '奴仆宫',
    '官禄': '官禄宫', '事业': '官禄宫', '工作': '官禄宫', '田宅': '田宅宫', '房产': '田宅宫',
    '福德': '福德宫', '父母': '父母宫',
}


SENTENCE = re.compile(r'[^。；！？\n]+[。；！？]?')


STAR_NAMES = ('紫微', '天机', '太阳', '武曲', '天同', '廉贞', '廉真', '天府', '太阴', '贪狼', '巨门', '天相', '天梁',
              '七杀', '破军', '左辅', '右弼', '辅弼', '文昌', '文曲', '天魁', '天钺', '魁钺', '禄存', '天马', '擎羊',
              '陀罗', '火星', '铃星', '地空', '地劫')
SAME_STAR = {'廉贞': ('廉真',)}


def _others(star: str) -> list[str]:
    own = {star, *SAME_STAR.get(star, ())}
    return [normalized(n) for n in STAR_NAMES if n not in own]


def _names_palace(sentence: str, star: str, seat: re.Pattern, essay: bool) -> bool:
    # Clause by clause, so 「太陰合文曲於妻宮…，太陽會文昌於官祿」 is not credited to 太阴 for 官禄.
    return any(seat.search(c) and (essay or normalized(star) in c)
               for c in re.split('[,，、]', normalized(sentence)))   # NFKC turns ， into ,


def _essay_sentences(text: str, star: str) -> list[str]:
    """The sentences still about ``star`` in a paragraph that opens with it.

    Round 7 R7-FOCUS-01: c002:p0103 opens with 紫微 and then lists every star, so
    「廉真属火…在官禄为官禄主」 was quoted under 紫微. The essay ends at the first
    sentence that names another star; that sentence and the rest are not credited.
    """
    others = _others(star)
    kept = []
    for sentence in SENTENCE.findall(text):
        if any(n in normalized(sentence) for n in others):
            break
        kept.append(sentence)
    return kept


OTHER_PALACE = re.compile('身命|命宫|兄弟|夫妻|妻宫|男女|子女|财帛|疾厄|迁移|奴仆|官禄|田宅|福德|父母')
BRIGHTNESS_CONDITION = re.compile('庙|陷地|落陷|失陷|居陷|陷宫')


def _conditions(text: str, star: str, short: str) -> list[str]:
    """Brightness conditions in the passage a quote came from, still about this star and this palace.

    Round 11 T42: 「後化貴化祿，最宜在官祿宮」 was quoted, while the same passage makes 「若居廟旺，化祿化權，允為貴論」
    a condition and 太阳 sits 陷 in that chart. A sentence that names another star, another palace, or a gendered
    case (女人、妻、夫) is left out: it is not a condition on this star in this palace.
    """
    others = _others(star)
    kept = []
    for sentence in SENTENCE.findall(text):
        plain = normalized(sentence)
        if (not BRIGHTNESS_CONDITION.search(plain) or any(n in plain for n in others)
                or re.search('女|男|妻|夫|父|母', plain)
                or any(seat != short for seat in OTHER_PALACE.findall(plain))):
            continue
        kept.append(sentence.strip())
    return kept


def _requires(sentence: str) -> str | None:
    plain = normalized(sentence)
    bright, dark = '庙' in plain, '陷' in plain
    return '庙旺' if bright and not dark else '陷' if dark and not bright else None


def _star_hits(star: str, short: str, limit: int = 2) -> tuple[list[dict], list[dict]]:
    """palace_quotes plus the brightness conditions from the same passages."""
    out: list[dict] = []
    conditions: list[dict] = []
    for hit in search_classics(f'{star} {short}', book='ziwei', limit=6):
        # Star essays name the star at the head and then go palace by palace (「在夫妻主於隔角」);
        # elsewhere the sentence itself must name the star. The palace must be used as a
        # palace (在夫妻、於官祿、夫妻宮), not as part of a phrase like 财官禄旺.
        essay = re.match(r'[^，。；]{0,8}?' + normalized(star), normalized(hit['text']).lstrip()) is not None
        seat = re.compile(f'(?:在|居|于|守|临|入|坐){short}|{short}宫')
        if essay:
            candidates = _essay_sentences(hit['text'], star)
        else:   # the sentence names the star itself and no other star shares the clause
            candidates = [x for x in SENTENCE.findall(hit['text'])
                          if not any(n in c and seat.search(c) for c in re.split('[,，、]', normalized(x))
                                     for n in _others(star))]
        sentence = next((x.strip() for x in candidates if _names_palace(x, star, seat, essay)), None)
        if sentence:
            out.append({'passage_id': hit['passage_id'], 'text': sentence})
            conditions.extend({'passage_id': hit['passage_id'], 'sentence': c}
                              for c in _conditions(hit['text'], star, short) if c != sentence)
        if len(out) >= limit:
            break
    return out, conditions[:3]


def palace_quotes(star: str, short: str, limit: int = 2) -> list[dict]:
    """Sentences naming the palace, from 全书 paragraphs that discuss the star, as written.

    Round 6 Z04 timed out after one classical_search call per star; the focus
    block now carries the matching sentences so the host can quote them directly.
    A shared sentence is a lead to read, not a verdict about this chart.
    """
    return _star_hits(star, short, limit)[0]


def palace_name(text: str) -> str | None:
    key = text.strip().removesuffix('宫')
    return PALACE_ALIASES.get(key) or (text if text in PALACE_ALIASES.values() else None)


def _stars_text(palace: dict) -> str:
    mains = palace['main_stars']
    if not mains:
        return '无主星'
    return '、'.join(f"{s['name']}（{s['brightness']}）" if s.get('brightness') else s['name']
                    for s in (m if isinstance(m, dict) else {'name': m} for m in mains))


def _where(chart: dict, star: str) -> str | None:
    branch = chart['main_stars_positions'].get(star) or chart['lucky_stars_positions'].get(star)
    return next((p['name'] for p in chart['twelve_palaces'] if p['branch'] == branch), None)


def build_say(chart: dict) -> list[str]:
    palaces = chart['twelve_palaces']
    ming = palaces[0]
    shen = next(p for p in palaces if p['branch'] == chart['shen_gong']['branch'])
    lines = [f"命宫在{ming['branch']}（{ming['stem']}{ming['branch']}），"
             f"主星{_stars_text(ming)}；身宫在{shen['name']}（{shen['branch']}）。",
             f"{chart['wuxing_ju']['name']}；命主{chart['ming_zhu']}，身主{chart['shen_zhu']}。"]
    hua = '，'.join(f"{star}化{kind}在{_where(chart, star) or '盘外'}"
                    for kind, star in chart['four_transformations_native'].items())
    lines.append(f"生年{chart['year_stem']}干四化：{hua}。")
    for pattern in chart.get('patterns', []):
        source = (f"《全书》{pattern['passage_id']}" if pattern['passage_id'] else '现代通行说法，所选《全书》转录未载')
        if pattern.get('reading_note'):
            source += '，条件为本项目选读：' + pattern['reading_note'].rstrip('。')
        tail = f"；减力条件：{'、'.join(pattern['breaking'])}" if pattern['breaking'] else ''
        tail += f"；待核：{'、'.join(pattern['to_check'])}" if pattern.get('to_check') else ''
        lines.append(f"{pattern['name']}：{'、'.join(pattern['required'])}（{source}）{tail}。")
    if not chart.get('patterns'):
        lines.append('本盘没有命中已收录的格局条件。')
    school = chart['school']
    leap = {'split': '十五日前后分月', 'next': '整月归下月', 'prev': '整月归本月'}[school['leap_month']]
    lines.append(f"排盘口径：闰月{leap}，"
                 f"晚子时{'算次日' if school['late_zi_sect'] == 1 else '日仍算当日'}，"
                 f"{'立春' if school['year_divide'] == 'lichun' else '正月初一'}换年"
                 + ('，倪海厦派预设' if school['preset'] == 'nihai' else '') + '。')
    return lines


BRIGHTNESS_GLOSS = '亮度等级，从强到弱是庙、旺、得、利、平、不、陷；只是星在这一宫的传统亮度，不是好坏评分'
TERMS = {
    '对宫': '正对面的那一宫；看一宫时连对宫一起看',
    '三合': '和本宫隔四位、成三角的两个宫，会照本宫',
    '三方四正': '本宫、对宫和两个三合宫，看一个主题时一起看的四个宫',
    '生年四化': '出生年天干带来的四个标记（化禄、化权、化科、化忌），各落在一颗星上',
    '借对宫': '本宫没有主星时，借对宫的主星来看',
}
# Round 11 FIX-11-02: E07 stopped at 「不足以选定职业」 and T42 gave advice with no anchor. One action that holds for
# anyone, said as such, so the reader has something to do without a career verdict drawn from the stars.
CAREER_ACTION = {
    'text': '先把下一份工作或下一次谈话要确认的三件事写下来：谁给你授权和拍板、成果按什么标准评、'
            '工作量超了找谁调整；面谈或和上级沟通时逐条问清。',
    'boundary': '这是一般工作做法，对谁都适用，不是从这张盘推出来的，也不预测结果。',
}


def _terms(say: str, palace: dict) -> dict:
    """Plain glosses for the terms the focus sentence uses (FIX-11-03: 武贪、科权禄 went unexplained)."""
    # 三方四正 and 生年四化 are always in the one table the answer order asks for, whether or not this sentence says them.
    out = {term: gloss for term, gloss in TERMS.items() if term in say or term in ('三方四正', '生年四化')}
    if palace.get('borrowed'):
        out['借对宫'] = TERMS['借对宫']
    for label in dict.fromkeys(re.findall('[（(](庙|旺|得|利|平|不|陷)[）)]', say)):
        out[label] = BRIGHTNESS_GLOSS
    return out


def _career(say: str, seen: list[str], quotes: dict, checks: list[dict]) -> dict:
    undecided = [f"《全书》{c['passage_id']}「{c['sentence'].rstrip('。')}」要{c['star']}{c['requires']}，"
                 f"本盘{c['star']}是{c['chart']}，这一层不套用。" for c in checks if not c['met']]
    if not any(quotes.get(star) for star in seen):
        undecided.append(f"没有找到把{'、'.join(seen) or '本宫'}落在官禄宫对应到具体工作的完整原句，工作方向这次不定。")
    else:
        undecided.append('原句讲的是古代任职，换成今天的行业属于类比，不能据此指定职业。')
    return {'undecided': undecided, 'action': dict(CAREER_ACTION),
            'first_answer': [{'part': 'facts', 'text': say}, {'part': 'undecided', 'text': ''.join(undecided)},
                             {'part': 'action', 'text': CAREER_ACTION['text'] + CAREER_ACTION['boundary']}]}


def focus_palace(chart: dict, name: str) -> dict:
    """The asked palace laid out for a per-palace answer: stars, 对宫/三合, 四化, patterns, search terms."""
    palaces = {p['name']: p for p in chart['twelve_palaces']}
    by_branch = {p['branch']: p for p in chart['twelve_palaces']}
    palace = palaces[name]
    sfsz = palace['san_fang_si_zheng']
    short = name.removesuffix('宫')
    mains = [m['name'] for m in palace['main_stars']]
    seen = mains or list(palace.get('borrowed_stars', []))
    hua_here = [f"{star}化{kind}" for kind, star in chart['four_transformations_native'].items()
                if star in mains + palace.get('lucky_stars', [])]
    patterns = [p['name'] for p in chart.get('patterns', []) if name in '、'.join(p['required']) or name == '命宫']
    quoted = set(seen)
    held_back = [star for star in palace.get('lucky_stars', []) + palace.get('malefic_stars', [])
                 + palace.get('miscellaneous_stars', []) if star not in quoted]
    opposite = by_branch[sfsz['对宫']]
    trines = [by_branch[b] for b in sfsz['三合']]
    say = (f"{name}在{palace['branch']}（{palace['ganzhi']}），主星{_stars_text(palace)}"
           + (f"，空宫借对宫{opposite['name']}的{'、'.join(palace['borrowed_stars'])}" if palace.get('borrowed') else '')
           + f"；对宫{opposite['name']}{_stars_text(opposite)}；"
           + '；'.join(f"三合{t['name']}{_stars_text(t)}" for t in trines)
           + (f"；本宫生年{'、'.join(hua_here)}" if hua_here else '') + '。')
    hits = {star: _star_hits(star, short) for star in seen} if name != '命宫' else {}
    quotes = {star: found for star, (found, _) in hits.items()}
    brightness = {m['name']: m.get('brightness') for m in palace['main_stars']}
    checks = []
    for star, (_, conditions) in hits.items():
        for c in conditions:
            requires = _requires(c['sentence'])
            if requires and brightness.get(star):
                met = brightness[star] in ('庙', '旺') if requires == '庙旺' else brightness[star] == '陷'
                checks.append({'star': star, 'passage_id': c['passage_id'], 'sentence': c['sentence'],
                               'requires': requires, 'chart': brightness[star], 'met': met})
    extra = {'career': _career(say, seen, quotes, checks)} if name == '官禄宫' else {}
    lead = (['开头三句照 career.first_answer：盘面一句、未判一句、一条现实工作动作（连同它的 boundary 一起说）']
            if extra else [])
    return {**extra,
        'palace': name, 'branch': palace['branch'], 'ganzhi': palace['ganzhi'],
        'main_stars': palace['main_stars'], 'borrowed_from_branch': palace.get('borrowed_from_branch'),
        'borrowed_stars': palace.get('borrowed_stars', []),
        'lucky_stars': palace.get('lucky_stars', []), 'malefic_stars': palace.get('malefic_stars', []),
        'miscellaneous_stars': palace.get('miscellaneous_stars', []), 'sihua_here': hua_here,
        'opposite': {'palace': opposite['name'], 'branch': opposite['branch'],
                     'main_stars': [m['name'] for m in opposite['main_stars']]},
        'trines': [{'palace': t['name'], 'branch': t['branch'], 'main_stars': [m['name'] for m in t['main_stars']]}
                   for t in trines],
        'patterns': patterns,
        'search_queries': [f'{star} {short}' for star in seen] or [f'{short}宫'],
        'quotes': quotes,
        'quotes_note': '取自讲这颗星的《全书》段落中提到该宫的那一句，原字照录可直接引用；是否适用于本盘仍要按原文条件解释。',
        'condition_checks': checks,
        'condition_checks_note': '同一段原文里对这颗星的庙旺、落陷条件，逐条对照本盘亮度；met 为 false 的那层不能套用。',
        'terms': _terms(say, palace),
        # Round 10 T41-T44: the facts were right but limits were repeated inside every paragraph. The answer now
        # leads with what this chart supports, and every limit is said once, in one place at the end.
        # Round 11 FIX-11-03: two tables restated the same palaces and 武贪、科权禄 went unexplained.
        'answer_order': lead + ['开头一至两句：本题能支持的结论；条件不全时直接说结论只到哪一步',
                         '必要盘面：本宫主星与亮度（空宫说明借对宫）、对宫与三合会照、生年四化落入，最多一张表列完',
                         '逐条解释：先白话，再给直接支持它的原句和段号（quotes）；没有原句的星只在表里列位置；'
                         'condition_checks 里不成立的条件，在那条解释旁说一次',
                         '星名写全称（不写武贪、廉破、科权禄这类缩写）；术语首次出现时用 terms 里的白话当场解释',
                         '补查记录（全篇只写这一处，每项一次）：held_back 里只列位置、不作解释的星，还没核的解释，转录版本状态'],
        'held_back': held_back,
        'note_once': '转录尚未逐字校勘、未核原刻影像：放进补查记录说一次，不在每段重复。',
        'say': say,
    }
