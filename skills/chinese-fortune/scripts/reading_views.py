"""Views of one computed reading; presentation never computes another chart."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from html import escape
from pathlib import Path

from bazi_derivation import asks_derivation
from report_views import (
    professional_html,
    professional_markdown,
    redact_text,
    route_rows,
    shareable,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]


def _intern(value: dict, pool: dict[str, dict], keys: dict[str, str], prefix: str) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    key = keys.setdefault(encoded, f'{prefix}{len(keys) + 1}')
    pool.setdefault(key, value)
    return key


def compact_reading(result: dict) -> dict:
    """Deduplicate conditions and index full source passages without losing verdicts.

    A compact view is for routing and the first response. Evidence text is
    obtained by passage ID before quoting or resolving interpretive conditions.
    The input result is untouched and remains the authoritative full view.
    """
    if not result.get('ok') or result.get('tool') != 'bazi_reading':
        raise ValueError('需要成功的八字解读结果')
    compact = deepcopy(result)
    compact['view'] = 'compact'
    if not asks_derivation(result.get('question') or ''):
        compact.pop('derivation', None)
    assessment = compact['rule_assessment']
    pool: dict[str, dict] = {}
    condition_keys: dict[str, str] = {}
    for route in assessment['routes']:
        refs = []
        for condition in route.pop('conditions'):
            # Keep every condition/negation; detailed fact paths belong to full.
            condition.pop('facts', None)
            encoded = json.dumps(condition, ensure_ascii=False, sort_keys=True)
            key = condition_keys.setdefault(encoded, f'c{len(condition_keys) + 1}')
            pool.setdefault(key, condition)
            refs.append(key)
        route['condition_refs'] = refs
        # These contracts are shared across every route and recorded once below.
        route.pop('family_resolution', None)
        route.pop('scope', None)
    assessment['conditions'] = pool
    assessment['scope'] = 'natal'
    assessment['family_resolution'] = '月令候选尚须原文复核，不由前提齐全自动定格'
    bundle = compact.pop('evidence_bundle')
    compact['evidence_index'] = [p['passage_id'] for p in bundle['passages']]
    support = compact.pop('reading_support')
    compact['observations'] = [claim['text'] for claim in support['claims']]
    compact.pop('observed_structure')
    # Annual interpretations retain their own facts; the generic ten-year
    # list is unnecessary for an initial answer and remains in the full view.
    compact['chart_facts'].pop('liu_nian', None)
    compact['chart_facts']['da_yun'] = [
        {key: value for key, value in cycle.items()
         if key in ('ganzhi', 'start_year', 'end_year', 'start_age', 'end_age', 'status', 'cut_at_death_year')}
        for cycle in compact['chart_facts'].get('da_yun', [])]
    review = compact['geju_review']
    for field, prefix in (('unresolved_conditions', 'u'), ('groups', 'g')):
        pool_items: dict[str, dict] = {}
        encodings: dict[str, str] = {}
        for case in review['cases']:
            parents = [case] if field == 'unresolved_conditions' else case['observations']
            for parent in parents:
                if field not in parent:
                    continue
                refs = []
                for item in parent.pop(field):
                    encoded = json.dumps(item, ensure_ascii=False, sort_keys=True)
                    key = encodings.setdefault(encoded, f'{prefix}{len(encodings) + 1}')
                    pool_items.setdefault(key, item)
                    refs.append(key)
                parent[field + '_refs'] = refs
        review[field] = pool_items
    if 'luck_reading' in compact:
        index: dict[str, dict] = {'scenarios': {}, 'verdicts': {}}
        scenario_keys: dict[str, str] = {}
        verdict_keys: dict[str, str] = {}
        for reading in compact['luck_reading']:
            for scenario in reading.get('scenarios', []):
                metadata = {key: value for key, value in scenario.items() if key not in ('stem', 'branch')}
                parts = {part: scenario[part] for part in ('stem', 'branch')}
                for part in parts.values():
                    part['verdict_refs'] = [_intern(v, index['verdicts'], verdict_keys, 'v') for v in part.pop('verdicts')]
                scenario.clear()
                scenario.update(id=metadata['id'], scenario_ref=_intern(metadata, index['scenarios'], scenario_keys, 's'), **parts)
        compact['luck_index'] = index
    compact['details'] = {
        'source': 'python scripts/classical_search.py --passage-id <passage_id>',
        'full_view': '同一出生资料、问题、参考年和request_time，使用 --view full',
        'source_text_included': False,
        'required_before_interpretation': '条件与例外不能省略；*_refs 指向同一 review 的同名索引表；引原文或推断前按ID取完整段落及上下文',
        'luck_refs': 'scenario_ref 指向 luck_index.scenarios，verdict_refs 指向 luck_index.verdicts；条件、反例及未判原因无删减',
        'omitted_fields': ['chart_facts.liu_nian', 'evidence_bundle', 'reading_support',
                           'observed_structure', 'rule_assessment.routes.conditions.facts'],
    }
    return compact


FACTS_WRITER = 'chinese-fortune --facts-out'


def write_facts(path: str, obj: dict) -> str:
    """Save a tool's JSON for ``answer_check --facts``.

    Round 5 S18 timed out after a 42.5KB compact reading spilled out of the host's
    inline output and had to be read back from disk: writing the JSON once and
    printing the short plain-text draft saves those round trips. The file carries
    a ``facts_file`` marker; an existing file is replaced only when it bears the
    same writer and tool, so another program's JSON (even one with a ``tool`` key,
    round 6 R6-IO-01) is never overwritten.
    """
    target = Path(path).expanduser()
    if target.suffix.lower() != '.json':
        raise ValueError('--facts-out 需要 .json 文件路径')
    marker = {'written_by': FACTS_WRITER, 'tool': obj.get('tool')}
    mode = 'x'
    if target.exists():
        try:
            previous = json.loads(target.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            previous = None
        if not (isinstance(previous, dict) and previous.get('facts_file') == marker):
            raise ValueError(f'{target} 已存在且不是本工具上次用 --facts-out 写的文件，不覆盖；请换一个路径')
        mode = 'w'
    with target.open(mode, encoding='utf-8', newline='\n') as handle:
        json.dump({**obj, 'facts_file': marker}, handle, ensure_ascii=False, separators=(',', ':'), default=str)
    return str(target.resolve())


def facts_line(path: str) -> str:
    return (f'完整 JSON 已存到 {path}；引用段号或细节时按需查这个文件，'
            f'发出前核对正文：python scripts/answer_check.py --answer - --facts {path}（正文从标准输入给）。')


REDACTED = ['四柱干支', '出生日期与时间', '出生地、经度与时区', '问题原话', '公历年份', '出生时刻的推算过程',
            '完整计算资料']


def write_report(result: dict, facts_text: str, destination: str, *, style: str = 'plain',
                 redact: bool = False) -> dict:
    """Save an explicitly requested, offline report; never replace an existing file.

    style='professional' adds the pillar table, an inline SVG chart and the condition table; redact=True is a
    share preview with identifying values masked and no full JSON (report_views)."""
    path = Path(destination).expanduser().resolve()
    if path == SKILL_ROOT or SKILL_ROOT in path.parents:
        raise ValueError('个人报告须保存在技能/仓库目录之外，避免混入发行包')
    suffix = path.suffix.lower()
    if suffix not in ('.md', '.html'):
        raise ValueError('报告路径须以 .md 或 .html 结尾')
    if style not in ('plain', 'professional'):
        raise ValueError('报告写法只有 plain 或 professional')
    paragraphs = [p for p in facts_text.split('\n\n') if not p.startswith('写回答时：')]
    notice = '这是传统文化的规则读法，不是对未来的预测；未判项目保留，排盘与起运需用排盘软件复核。'
    metadata = f"版本 {result['version']} · 同一次计算结果 · 完整资料与出处见下方"
    full = json.dumps(result, ensure_ascii=False, indent=2)
    question = result['question']
    if redact:
        paragraphs = [redact_text(p, result) for p in paragraphs if shareable(p)]
        question = '（已隐去）'
        metadata = f"版本 {result['version']} · 分享预览：已隐去{'、'.join(REDACTED)}"
        cited = sorted({row['passage'] for row in route_rows(result) if row['passage'] != '—'})
        full = '所引原文段号（可在随包古籍中查）：\n' + '\n'.join(cited)
    extra_md = professional_markdown(result, redact) + '\n\n' if style == 'professional' else ''
    extra_html = professional_html(result, redact) if style == 'professional' else ''
    if suffix == '.md':
        # A variable fence prevents user input from closing the evidence block.
        fence = '`' * max(3, max((len(s) for s in re.findall(r'`+', full)), default=0) + 1)
        question_md = re.sub(r'([\\`*_{}\[\]()#+.!|>-])', r'\\\1', escape(question))
        content = (f"# 八字核对报告\n\n{metadata}\n\n{notice}\n\n"
                   f"问题：{question_md}\n\n" + extra_md + '\n\n'.join(paragraphs) +
                   f'\n\n## 完整计算资料与出处\n\n{fence}{"" if redact else "json"}\n{full}\n{fence}\n')
    else:
        # Keep the answer and fixed pillars visible before the optional detail.
        lead = ''.join(f'<p>{escape(p)}</p>' for p in paragraphs[:2])
        body = ''.join(f'<p>{escape(p)}</p>' for p in paragraphs[2:])
        content = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                   '<meta name="viewport" content="width=device-width, initial-scale=1">'
                   '<title>八字核对报告</title><style>'
                   ':root{color-scheme:light;--ink:#1e293b;--muted:#475569;--paper:#fff;--accent:#1d4ed8}'
                   '*{box-sizing:border-box}body{margin:0;background:#f8fafc;color:var(--ink);'
                   'font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif}'
                   'main{max-width:54rem;margin:auto;padding:2rem 1.25rem 4rem;overflow-wrap:anywhere}'
                   'h1{font-size:2rem;line-height:1.3}p{margin:1rem 0}.meta{color:var(--muted)}'
                   '.notice,details{background:var(--paper);border:1px solid #cbd5e1;border-radius:.5rem;padding:1rem}'
                   'summary{cursor:pointer;min-height:44px;align-content:center;font-weight:600}'
                   'summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}'
                   'pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem;line-height:1.65}'
                   'h2{font-size:1.25rem;margin-top:2rem}.scroll{overflow-x:auto}'
                   'table{border-collapse:collapse;width:100%;margin:1rem 0;font-variant-numeric:tabular-nums}'
                   'th,td{border:1px solid #cbd5e1;padding:.4rem .6rem;text-align:left;vertical-align:top}'
                   'th{background:#f1f5f9}'
                   '@media print{body{background:white}main{max-width:none;padding:0}details{break-before:page}}'
                   '</style><main><h1>八字核对报告</h1>'
                   f'<p class="meta">{escape(metadata)}</p><p class="notice">{escape(notice)}</p>'
                   f'<p><strong>本次问题：</strong>{escape(question)}</p>'
                   + extra_html + lead +
                   '<details><summary>展开盘面说明、术语与条件核查</summary>' + body + '</details>'
                   '<details><summary>展开完整计算资料、条件与原文出处</summary>'
                   f'<pre>{escape(full)}</pre></details></main></html>')
    # Exclusive creation is atomic with respect to collisions and symlinks.
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(content)
    return {'path': str(path), 'format': suffix[1:], 'offline': True, 'style': style, 'redacted': redact,
            **({'removed': REDACTED} if redact else {})}
