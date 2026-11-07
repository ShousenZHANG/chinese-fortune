"""离线报告的两种写法与分享用的隐去版本；只排版已算好的结果，不另算命盘。

- plain（默认）：白话段落在前，术语随文解释，细节折叠。
- professional：四柱表与离线命盘图（内联 SVG，不连网）、条款核查表、大运表、原文段号。
- redact：分享预览。四柱干支、出生日期时间、地点、经度、时区、问题原话、能反推出生年的公历年份都隐去，
  不附完整 JSON；只留十神关系、条款状态与段号。四柱加性别能反查出生日期（见 pillars_to_dates），
  所以干支本身也按敏感处理。
"""
from __future__ import annotations

import re
from html import escape

ORDER = (('year', '年柱'), ('month', '月柱'), ('day', '日柱'), ('hour', '时柱'))
STATUS = {'met': '条件齐备', 'premise_not_met': '前提不成立', 'conditional': '待核条件', 'partial': '部分成立',
          'needs_review': '待核', 'needs_interpretation': '可算前提齐备，余项待人工核', 'candidate': '候选'}
MASK = '□□'
# 分享预览里单个天干地支也隐去（日主、月令、某柱天干拼起来仍能缩小出生日期范围）；
# 只放过常见词里的同形字，宁可多遮。
GANZHI_CHAR = re.compile(r'[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]')
KEEP_WORDS = re.compile(r'尚未|并未|还未|从未|仍未|未[判核定见必能有知到给写满成完曾免经被重]|子孙|孩子|儿子|女子|君子|日子|'
                        r'例子|样子|申请|申报|时辰|生辰|中午|下午|上午|人丁|自己|知己|子平|渊海|淵海')
YEAR = re.compile(r'(?<!\d)(?:1[6-9]|20|21|22|23)\d\d(?!\d)')
DATE_TIME = re.compile(r'\d{1,4}[-/年.]\d{1,2}(?:[-/月.]\d{1,2}日?)?|\d{1,2}:\d{2}(?::\d{2})?|\d{1,2}时\d{1,2}分')


def _roles(result: dict) -> dict[str, str]:
    observed = result.get('observed_structure') or {}
    roles = {row['pillar']: row['role'] for row in observed.get('exposed_stems', [])}
    roles['day'] = '日主'
    return roles


def pillar_rows(result: dict, redact: bool = False) -> list[dict]:
    pillars = result['chart_facts']['four_pillars']
    roles = _roles(result)
    rows = []
    for key, label in ORDER:
        p = pillars.get(key)
        if not p or 'stem' not in p:
            # Unknown birth time: keep the candidates, never a placeholder pillar.
            candidates = '/'.join((p or {}).get('candidate_ganzhi') or [])
            shown = ('候选（已隐去）' if candidates else '未定') if redact else (f'候选 {candidates}' if candidates else '未定')
            rows.append({'label': label, 'role': '未定', 'stem': shown, 'branch': '', 'hidden': '', 'nayin': ''})
            continue
        rows.append({'label': label, 'role': roles.get(key, '—'),
                     'stem': MASK[0] if redact else p['stem'], 'branch': MASK[0] if redact else p['branch'],
                     'hidden': '' if redact else '、'.join(p.get('hidden_stems', [])),
                     'nayin': '' if redact else p.get('nayin', '')})
    return rows


def pillar_svg(rows: list[dict]) -> str:
    """Offline chart image: four columns, ten-god label over stem over branch, hidden stems and nayin below."""
    width, col = 480, 120
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 236" role="img" '
             'aria-label="四柱命盘图" style="max-width:100%;height:auto">',
             '<rect width="100%" height="100%" fill="#ffffff"/>']
    for i, row in enumerate(rows):
        x = i * col + col / 2
        fill = '#eef2ff' if row['role'] == '日主' else '#f8fafc'
        parts.append(f'<rect x="{i * col + 6}" y="6" width="{col - 12}" height="224" rx="8" fill="{fill}" '
                     'stroke="#cbd5e1"/>')
        for y, text, size, colour in ((30, row['label'], 14, '#475569'), (56, row['role'], 15, '#1d4ed8'),
                                      (104, row['stem'], 34, '#1e293b'), (150, row['branch'], 34, '#1e293b'),
                                      (184, row['hidden'], 13, '#475569'), (210, row['nayin'], 13, '#475569')):
            if text:
                parts.append(f'<text x="{x:.0f}" y="{y}" text-anchor="middle" font-size="{size}" fill="{colour}" '
                             f'font-family="system-ui,\'Microsoft YaHei\',sans-serif">{escape(text)}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def route_rows(result: dict) -> list[dict]:
    rows = []
    for route in (result.get('rule_assessment') or {}).get('routes', []):
        missing = [c['label'] for c in route.get('conditions', []) if c.get('state') == 'not_met']
        rows.append({'title': route['title'], 'status': STATUS.get(route['status'], route['status']),
                     'missing': '、'.join(missing) or '—', 'passage': route.get('passage_id') or '—'})
    return rows


def luck_rows(result: dict) -> list[dict]:
    rows = []
    for row in result['chart_facts'].get('da_yun') or []:
        cut = row.get('cut_at_death_year')
        if cut:
            last_age = row['start_age'] + cut - row['start_year']
            ages = f"{row['start_age']}–{last_age}（卒年截止；原周期至 {row['end_age']}）"
            years = f"{row['start_year']}–{cut}（卒年截止；原周期至 {row['end_year']}）"
        else:
            ages, years = f"{row['start_age']}–{row['end_age']}", f"{row['start_year']}–{row['end_year']}"
        rows.append({'ganzhi': row['ganzhi'], 'role': row.get('shi_shen', ''), 'ages': ages, 'years': years})
    return rows


def sensitive_values(result: dict) -> list[str]:
    """Strings that identify the person or the birth moment."""
    facts = result['chart_facts']
    values: list[str] = []
    for p in facts['four_pillars'].values():
        if p:
            values += [p['ganzhi']] if p.get('ganzhi') else list(p.get('candidate_ganzhi') or [])
    values += [result.get('question') or '']
    for block in ('solar_date', 'lunar_date', 'true_solar_time', 'timezone', 'birthplace', 'calendar_context'):
        value = facts.get(block)
        if isinstance(value, dict):
            values += [str(v) for v in value.values() if isinstance(v, (str, int, float)) and len(str(v)) >= 2]
        elif isinstance(value, str):
            values.append(value)
    # Longest first so a value inside another is not replaced first; ties broken by the text itself, so the
    # result never depends on set order (R9-ST03).
    return sorted({v for v in values if _identifying(v)}, key=lambda v: (-len(v), v))


def _identifying(value: str) -> bool:
    return len(value) >= 2 and (not value.isascii() or bool(re.search(r'\d{3,}|\d[-:.]\d', value)))


def _mask_ganzhi(text: str) -> str:
    kept = {i for m in KEEP_WORDS.finditer(text) for i in range(m.start(), m.end())}
    return ''.join('□' if GANZHI_CHAR.fullmatch(ch) and i not in kept else ch for i, ch in enumerate(text))


# A paragraph that walks through the birth moment (time zone, true solar time, day count from a public
# anchor date) re-identifies the person even with every value masked, so a share preview drops it whole.
BIRTH_WALKTHROUGH = ('推算过程', '真太阳时', '出生时刻')
ZONE = re.compile(r'\b[A-Z][A-Za-z]+/[A-Za-z_]+(?:/[A-Za-z_]+)?\b|UTC\s*[+-]\s*\d{1,2}(?::?\d{2})?|GMT\s*[+-]\s*\d{1,2}')
LONG_NUMBER = re.compile(r'\d{3,}')
# A passage id names a public paragraph of a bundled book, not the person; its digits stay readable.
PASSAGE_ID = re.compile(r'([a-z_]+:c\d{3}:p\d{4})')


def shareable(paragraph: str) -> bool:
    return not paragraph.startswith(BIRTH_WALKTHROUGH)


def redact_text(text: str, result: dict) -> str:
    pieces = PASSAGE_ID.split(text)
    return ''.join(piece if i % 2 else _redact_piece(piece, result) for i, piece in enumerate(pieces))


def _redact_piece(text: str, result: dict) -> str:
    for value in sensitive_values(result):
        text = text.replace(value, MASK)
    text = ZONE.sub(MASK, DATE_TIME.sub(MASK, YEAR.sub(MASK, text)))
    return _mask_ganzhi(LONG_NUMBER.sub(MASK, text))


def professional_markdown(result: dict, redact: bool) -> str:
    rows = pillar_rows(result, redact)
    lines = ['## 四柱', '', '| 柱 | 十神 | 天干 | 地支 | 藏干 | 纳音 |', '|---|---|---|---|---|---|']
    lines += [f"| {r['label']} | {r['role']} | {r['stem']} | {r['branch']} | {r['hidden']} | {r['nayin']} |"
              for r in rows]
    lines += ['', '## 条款核查', '', '| 条款 | 状态 | 缺的条件 | 原文 |', '|---|---|---|---|']
    lines += [f"| {r['title']} | {r['status']} | {r['missing']} | {r['passage']} |" for r in route_rows(result)]
    luck = luck_rows(result)
    if luck and not redact:
        lines += ['', '## 大运', '', '| 运 | 十神 | 周岁 | 公历年 |', '|---|---|---|---|']
        lines += [f"| {r['ganzhi']} | {r['role']} | {r['ages']} | {r['years']} |" for r in luck]
    return '\n'.join(lines)


def _table(head: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    cells = ''.join(f'<th scope="col">{escape(h)}</th>' for h in head)
    body = ''.join('<tr>' + ''.join(f'<td>{escape(c)}</td>' for c in row) + '</tr>' for row in rows)
    return f'<div class="scroll"><table><thead><tr>{cells}</tr></thead><tbody>{body}</tbody></table></div>'


def professional_html(result: dict, redact: bool) -> str:
    rows = pillar_rows(result, redact)
    html = ['<h2>四柱</h2>', pillar_svg(rows),
            _table(('柱', '十神', '天干', '地支', '藏干', '纳音'),
                   [(r['label'], r['role'], r['stem'], r['branch'], r['hidden'], r['nayin']) for r in rows]),
            '<h2>条款核查</h2>',
            _table(('条款', '状态', '缺的条件', '原文'),
                   [(r['title'], r['status'], r['missing'], r['passage']) for r in route_rows(result)])]
    luck = luck_rows(result)
    if luck and not redact:
        html += ['<h2>大运</h2>', _table(('运', '十神', '周岁', '公历年'),
                                       [(r['ganzhi'], r['role'], r['ages'], r['years']) for r in luck])]
    return ''.join(html)


# 分享卡片：一张 1080×1440 的离线 SVG，配色与 README 首图一致；每行文字都取自同一次计算的工具字段。
REPO = 'github.com/ShousenZHANG/chinese-fortune'
CARD_W, CARD_H, MARGIN = 1080, 1440, 72
SANS = "'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans CJK SC',sans-serif"
SERIF = "'Songti SC','STSong','SimSun','Noto Serif CJK SC',serif"
MONO = 'ui-monospace,Menlo,Consolas,monospace'
INK, MUTED, FAINT, SEAL, PAPER, LINE, TINT = '#2b2620', '#8a7b66', '#a3947e', '#a2462e', '#faf7f2', '#e7dfd2', '#f3e9da'
CARD_ROUTES = 3


def _wrap(text: str, size: int, width: float, limit: int = 2) -> list[str]:
    """Break a line by estimated glyph width (CJK one em, ASCII about half); SVG text never wraps itself."""
    lines, line, used = [], '', 0.0
    for ch in text:
        advance = size * (0.56 if ch.isascii() else 1.0)
        if line and used + advance > width:
            lines.append(line)
            line, used = '', 0.0
        line += ch
        used += advance
    lines.append(line)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = lines[-1][:-1] + '…'
    return lines


def _t(x: float, y: float, text: str, size: int, fill: str, *, family: str = SANS, anchor: str = 'start',
       weight: str = '') -> str:
    bold = f' font-weight="{weight}"' if weight else ''
    return (f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" fill="{fill}" font-family="{escape(family)}" '
            f'text-anchor="{anchor}"{bold}>{escape(text)}</text>')


def _current_cycle(facts: dict) -> dict | None:
    year = facts.get('reference_year')
    return next((row for row in facts.get('da_yun') or []
                 if isinstance(year, int) and row['start_year'] <= year <= row['end_year']), None)


def _book_title(result: dict, passage: str) -> str:
    books = (result.get('evidence_bundle') or {}).get('books') or {}
    return str((books.get(passage.split(':', 1)[0]) or {}).get('book_title', ''))


def card_facts(result: dict, redact: bool) -> list[tuple[str, str]]:
    """Labelled lines under the pillars, each copied from a tool field; a share card drops what identifies."""
    facts, observed = result['chart_facts'], result.get('observed_structure') or {}
    stems = observed.get('month_hidden_stems') or []
    if redact:
        lines = [('日主', '已隐去（四柱干支和出生资料都不上分享卡）')]
        if stems:
            lines.append(('月令', '藏干是' + '、'.join(h['role'] for h in stems)))
        return lines
    day = facts.get('day_master') or {}
    lines = [('日主', f"{day['stem']}{day['wuxing']} · {day['yin_yang']}干" if day.get('stem') else '待定')]
    if observed.get('month_branch'):
        hidden = '、'.join(f"{h['stem']}（{h['role']}）" for h in stems)
        lines.append(('月令', f"{observed['month_branch']}，藏{hidden}" if hidden else observed['month_branch']))
    cycle = _current_cycle(facts)
    if cycle:
        lines.append(('大运', cycle.get('say') or f"{cycle['ganzhi']}（{cycle['start_year']}–{cycle['end_year']}）"))
    return lines


def _card_pillars(rows: list[dict], top: int) -> list[str]:
    gap = 16
    width = (CARD_W - 2 * MARGIN - 3 * gap) / 4
    parts = []
    for i, row in enumerate(rows):
        x = MARGIN + i * (width + gap)
        middle = x + width / 2
        fill = TINT if row['role'] == '日主' else '#ffffff'
        parts.append(f'<rect x="{x:.0f}" y="{top}" width="{width:.0f}" height="400" rx="20" fill="{fill}" '
                     f'stroke="{LINE}" stroke-width="2"/>')
        parts.append(_t(middle, top + 52, row['label'], 26, MUTED, anchor='middle'))
        if row['role'] == '未定':
            # Unknown hour: say so; candidate pillars belong to the full reading, not a card.
            parts.append(_t(middle, top + 100, '时辰不详', 28, FAINT, anchor='middle'))
            parts.append(_t(middle, top + 250, '未定', 64, FAINT, family=SERIF, anchor='middle'))
            continue
        parts.append(_t(middle, top + 100, row['role'], 28, SEAL, anchor='middle', weight='600'))
        parts.append(_t(middle, top + 214, row['stem'], 104, INK, family=SERIF, anchor='middle'))
        parts.append(_t(middle, top + 326, row['branch'], 104, INK, family=SERIF, anchor='middle'))
        if row['nayin']:
            parts.append(_t(middle, top + 376, row['nayin'], 24, FAINT, anchor='middle'))
    return parts


def _card_routes(result: dict, top: int, redact: bool) -> list[str]:
    routes = route_rows(result)
    if redact:
        routes = [{**r, 'title': redact_text(r['title'], result)} for r in routes]
    titles = sorted({_book_title(result, r['passage']) for r in routes if r['passage'] != '—'} - {''})
    heading = (f"《{'》《'.join(titles)}》" if titles else '古籍') + '条款核查'
    parts = [_t(MARGIN, top, heading, 30, INK, weight='700')]
    if not routes:
        return parts + [_t(MARGIN, top + 60, '这张盘没有检索到需要核对的条款', 28, MUTED)]
    y = top + 64
    for row in routes[:CARD_ROUTES]:
        colour = FAINT if row['status'] == STATUS['premise_not_met'] else SEAL
        parts.append(_t(MARGIN, y, _wrap(row['title'], 32, 420, 1)[0], 32, INK))
        parts.append(_t(CARD_W - MARGIN, y, _wrap(row['status'], 26, 480, 1)[0], 26, colour, anchor='end'))
        parts.append(_t(MARGIN, y + 38, row['passage'], 22, FAINT, family=MONO))
        y += 88
    if len(routes) > CARD_ROUTES:
        parts.append(_t(MARGIN, y - 10, f'另有 {len(routes) - CARD_ROUTES} 条见完整报告', 24, MUTED))
    return parts


def share_card_svg(result: dict, redact: bool = False) -> str:
    """A portrait card to post or send: pillars, day master, month, current cycle, checked clauses, repo link.

    Nothing is newly judged here; a redacted card keeps only ten-god relations, clause states and passage ids."""
    subtitle = ('分享版：四柱干支、出生日期时间地点与公历年份已隐去' if redact else
                '程序排盘，按古籍逐条核对，每条附原文段号')
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" width="{CARD_W}" '
             f'height="{CARD_H}" role="img" aria-label="有据算命 八字速览卡片">',
             '<title>有据算命 · 八字速览</title>',
             f'<rect width="100%" height="100%" fill="{PAPER}"/>',
             f'<rect x="24" y="24" width="{CARD_W - 48}" height="{CARD_H - 48}" rx="28" fill="none" '
             f'stroke="{LINE}" stroke-width="2"/>',
             _t(MARGIN, 128, '有据算命 · 八字速览', 56, INK, weight='700'),
             _t(MARGIN, 182, subtitle, 26, MUTED),
             f'<rect x="{CARD_W - MARGIN - 104}" y="72" width="104" height="104" rx="12" fill="{SEAL}"/>',
             _t(CARD_W - MARGIN - 52, 118, '有', 40, '#ffffff', family=SERIF, anchor='middle', weight='700'),
             _t(CARD_W - MARGIN - 52, 162, '据', 40, '#ffffff', family=SERIF, anchor='middle', weight='700')]
    parts += _card_pillars(pillar_rows(result, redact), 224)
    y = 704
    for label, value in card_facts(result, redact):
        lines = _wrap(value, 30, CARD_W - 2 * MARGIN - 112)
        parts.append(_t(MARGIN, y, label, 26, MUTED))
        parts += [_t(MARGIN + 112, y + i * 40, line, 30, INK) for i, line in enumerate(lines)]
        y += 40 * len(lines) + 22
    rule = max(y, 900)
    parts.append(f'<line x1="{MARGIN}" y1="{rule - 30}" x2="{CARD_W - MARGIN}" y2="{rule - 30}" stroke="{LINE}" '
                 'stroke-width="2"/>')
    parts += _card_routes(result, rule + 30, redact)
    parts += [f'<line x1="{MARGIN}" y1="1300" x2="{CARD_W - MARGIN}" y2="1300" stroke="{LINE}" stroke-width="2"/>',
              _t(MARGIN, 1346, REPO, 24, MUTED, family=MONO),
              _t(MARGIN, 1386, f"传统文化研习，不是预测 · 版本 {result['version']}", 22, FAINT),
              '</svg>']
    return ''.join(parts)
