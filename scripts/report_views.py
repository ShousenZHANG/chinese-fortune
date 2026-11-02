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
        if not p:
            rows.append({'label': label, 'role': '未定', 'stem': '', 'branch': '', 'hidden': '', 'nayin': ''})
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
    return [{'ganzhi': row['ganzhi'], 'role': row.get('shi_shen', ''), 'ages': f"{row['start_age']}–{row['end_age']}",
             'years': f"{row['start_year']}–{row['end_year']}"}
            for row in result['chart_facts'].get('da_yun') or []]


def sensitive_values(result: dict) -> list[str]:
    """Strings that identify the person or the birth moment."""
    facts = result['chart_facts']
    values = [p['ganzhi'] for p in facts['four_pillars'].values() if p]
    values += [result.get('question') or '']
    for block in ('solar_date', 'lunar_date', 'true_solar_time', 'timezone', 'birthplace', 'calendar_context'):
        value = facts.get(block)
        if isinstance(value, dict):
            values += [str(v) for v in value.values() if isinstance(v, (str, int, float)) and len(str(v)) >= 2]
        elif isinstance(value, str):
            values.append(value)
    return sorted({v for v in values if _identifying(v)}, key=len, reverse=True)


def _identifying(value: str) -> bool:
    return len(value) >= 2 and (not value.isascii() or bool(re.search(r'\d{3,}|\d[-:.]\d', value)))


def _mask_ganzhi(text: str) -> str:
    kept = {i for m in KEEP_WORDS.finditer(text) for i in range(m.start(), m.end())}
    return ''.join('□' if GANZHI_CHAR.fullmatch(ch) and i not in kept else ch for i, ch in enumerate(text))


def redact_text(text: str, result: dict) -> str:
    for value in sensitive_values(result):
        text = text.replace(value, MASK)
    return _mask_ganzhi(DATE_TIME.sub(MASK, YEAR.sub(MASK, text)))


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
