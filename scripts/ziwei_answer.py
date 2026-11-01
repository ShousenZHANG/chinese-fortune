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


def _names_palace(sentence: str, star: str, seat: re.Pattern, essay: bool) -> bool:
    # Clause by clause, so 「太陰合文曲於妻宮…，太陽會文昌於官祿」 is not credited to 太阴 for 官禄.
    return any(seat.search(c) and (essay or normalized(star) in c)
               for c in re.split('[,，、]', normalized(sentence)))   # NFKC turns ， into ,


def palace_quotes(star: str, short: str, limit: int = 2) -> list[dict]:
    """Sentences naming the palace, from 全书 paragraphs that discuss the star, as written.

    Round 6 Z04 timed out after one classical_search call per star; the focus
    block now carries the matching sentences so the host can quote them directly.
    A shared sentence is a lead to read, not a verdict about this chart.
    """
    out: list[dict] = []
    for hit in search_classics(f'{star} {short}', book='ziwei', limit=6):
        # Star essays name the star at the head and then go palace by palace (「在夫妻主於隔角」);
        # elsewhere the sentence itself must name the star. The palace must be used as a
        # palace (在夫妻、於官祿、夫妻宮), not as part of a phrase like 财官禄旺.
        essay = re.match(r'[^，。；]{0,8}?' + normalized(star), normalized(hit['text']).lstrip()) is not None
        seat = re.compile(f'(?:在|居|于|守|临|入|坐){short}|{short}宫')
        sentence = next((x.strip() for x in SENTENCE.findall(hit['text'])
                         if _names_palace(x, star, seat, essay)), None)
        if sentence:
            out.append({'passage_id': hit['passage_id'], 'text': sentence})
        if len(out) >= limit:
            break
    return out


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
    opposite = by_branch[sfsz['对宫']]
    trines = [by_branch[b] for b in sfsz['三合']]
    say = (f"{name}在{palace['branch']}（{palace['ganzhi']}），主星{_stars_text(palace)}"
           + (f"，空宫借对宫{opposite['name']}的{'、'.join(palace['borrowed_stars'])}" if palace.get('borrowed') else '')
           + f"；对宫{opposite['name']}{_stars_text(opposite)}；"
           + '；'.join(f"三合{t['name']}{_stars_text(t)}" for t in trines)
           + (f"；本宫生年{'、'.join(hua_here)}" if hua_here else '') + '。')
    return {
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
        'quotes': {star: palace_quotes(star, short) for star in seen} if name != '命宫' else {},
        'quotes_note': '取自讲这颗星的《全书》段落中提到该宫的那一句，原字照录可直接引用；是否适用于本盘仍要按原文条件解释。',
        'answer_order': ['本宫主星与亮度（空宫说明借对宫）', '对宫与三合会照', '生年四化落入', '吉煞与相关格局',
                         '每颗星先用 quotes 里的原句，不够再用 search_queries 查；没有原文的星只说位置'],
        'say': say,
    }
