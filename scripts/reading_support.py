"""Evidence packets and structural checks for grounded readings.

The checker verifies chart references, quotes and declared conditions. It does
not certify prose semantics or real-world predictive validity.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from classical_search import get_passage
from utils import __version__, ensure_utf8_stdio, error_envelope, json_print, shi_shen

EVIDENCE_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'classical_evidence.json'


def load_evidence() -> dict:
    return json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))


def resolve_fact(chart: dict, path: str) -> Any:
    value: Any = chart
    for part in path.split('.'):
        if isinstance(value, dict):
            value = value[part]
        elif isinstance(value, list) and part.isdigit():
            value = value[int(part)]
        else:
            raise KeyError(path)
    return value


def bazi_reading_packet(chart: dict) -> dict:
    """Expose observations and unverified conditions without inventing events."""
    evidence = load_evidence()
    pillars = chart['four_pillars']
    facts = [{'path': f'four_pillars.{key}.ganzhi', 'value': p['ganzhi']}
             for key, p in pillars.items() if 'ganzhi' in p]
    claims: list[dict] = [
        {'id': 'chart-pillars', 'kind': 'chart_fact', 'status': 'supported',
         'text': '四柱：' + '、'.join(f["value"] for f in facts)
                 + ('；时柱待补' if not chart['hour_known'] else ''),
         'facts': facts, 'source_ids': [], 'rule_id': None, 'scope': 'natal',
         'conditions': {}, 'exceptions': []}
    ]
    for rule_id, text, paths in [
        ('bazi-month-structure', '格局候选须核查全局成败救应，暂不据格名断人生结果。',
         ['four_pillars.month.ganzhi', 'ge_ju.primary']),
        ('bazi-climate-separate', '扶抑与调候分列候选；尚不足以确定全局用神及喜忌。',
         ['yong_shen.views.fuyi.candidates', 'yong_shen.views.tiaohou.candidates']),
    ]:
        rule = next(r for r in evidence['rules'] if r['id'] == rule_id)
        refs = []
        for path in paths:
            try:
                refs.append({'path': path, 'value': resolve_fact(chart, path)})
            except (KeyError, IndexError, TypeError):
                pass
        if len(refs) != len(paths):
            continue
        claims.append({'id': rule_id, 'kind': 'traditional_interpretation',
                       'status': 'needs_review', 'text': text, 'facts': refs,
                       'source_ids': rule['source_ids'], 'rule_id': rule_id,
                       'scope': 'natal', 'conditions': dict.fromkeys(rule['required_conditions'], 'unknown'),
                       'exceptions': ['时辰未提供时，候选可能随时柱变化']})
    day_stem = chart['day_master']['stem']
    occurrences: list[dict] = []
    gods = set()
    for key, pillar in pillars.items():
        if key != 'day' and 'stem' in pillar:
            god = shi_shen(day_stem, pillar['stem'])
            if god in ('伤官', '正官'):
                gods.add(god)
                occurrences.append({'path': f'four_pillars.{key}.stem', 'value': pillar['stem']})
        for i, stem in enumerate(pillar.get('hidden_stems', [])):
            god = shi_shen(day_stem, stem)
            if god in ('伤官', '正官'):
                gods.add(god)
                occurrences.append({'path': f'four_pillars.{key}.hidden_stems.{i}', 'value': stem})
    if gods == {'伤官', '正官'}:
        claims.append({'id': 'shangguan-review', 'kind': 'traditional_interpretation',
                       'status': 'needs_review',
                       'text': '伤官与正官在天干或藏干中并见，透藏作用需区别；不能仅据并见判凶。',
                       'facts': [{'path': 'day_master.stem', 'value': day_stem}, *occurrences],
                       'rule_id': 'bazi-shangguan-guan',
                       'source_ids': ['ditian-shangguan', 'ditian-shangguan-comment'],
                       'scope': 'natal',
                       'conditions': {'co_presence': 'met', 'strength': 'unknown',
                                      'wealth_and_seal': 'unknown', 'rescue': 'unknown'},
                       'exceptions': ['身强弱及财印救应尚未逐条核实']})
    return {'schema_version': '1.0', 'claims': claims,
            'source_ids': sorted({s for c in claims for s in c['source_ids']}),
            'review_status': 'structural_only',
            'limits': ['旺衰分数是工程启发式，不是概率', '未预测现实事件或具体应期',
                       '格局与神煞中的旧断语不可直接转述', '古籍转录已核部分不等于全书已核']}


def review_claims(chart: dict, packet: dict, evidence: dict | None = None) -> list[str]:
    """Return structural violations; a clean result still requires semantic review."""
    if not isinstance(chart, dict) or not isinstance(packet, dict):
        return ['chart and packet must be objects']
    if chart.get('tool') == 'bazi_reading':
        if not chart.get('ok') or not isinstance(chart.get('chart_facts'), dict):
            return ['successful reading with chart_facts required']
        chart = chart['chart_facts']
    registry = evidence or load_evidence()
    sources = {s['id']: s for s in registry['sources']}
    rules = {r['id']: r for r in registry['rules']}
    errors = []
    claims = packet.get('claims')
    if not isinstance(claims, list) or not claims:
        return ['claims must be a nonempty list']
    ids = set()
    for i, claim in enumerate(claims):
        prefix = f'claim[{i}]'
        if not isinstance(claim, dict):
            errors.append(prefix + ': invalid claim')
            continue
        cid = claim.get('id')
        if not isinstance(cid, str) or not cid or cid in ids:
            errors.append(prefix + ': missing or duplicate id')
        else:
            ids.add(cid)
        if claim.get('kind') not in ('chart_fact', 'traditional_interpretation', 'hypothesis', 'practical_advice'):
            errors.append(prefix + ': invalid kind')
        if claim.get('status') not in ('supported', 'needs_review', 'disputed', 'insufficient'):
            errors.append(prefix + ': invalid status')
        if not isinstance(claim.get('text'), str) or not claim['text'].strip():
            errors.append(prefix + ': missing text')
        facts = claim.get('facts', [])
        if not isinstance(facts, list):
            errors.append(prefix + ': invalid facts')
            facts = []
        if claim.get('kind') in ('chart_fact', 'traditional_interpretation') and not facts:
            errors.append(prefix + ': missing chart evidence')
        for fact in facts:
            try:
                if resolve_fact(chart, fact['path']) != fact['value']:
                    errors.append(prefix + ': chart value mismatch')
            except (KeyError, IndexError, TypeError, ValueError, AttributeError):
                errors.append(prefix + ': invalid chart path')
        source_ids = claim.get('source_ids', [])
        if not isinstance(source_ids, list) or any(not isinstance(s, str) for s in source_ids):
            errors.append(prefix + ': invalid sources')
            source_ids = []
        if any(s not in sources for s in source_ids):
            errors.append(prefix + ': unknown source')
        for sid in source_ids:
            source = sources.get(sid, {})
            if source.get('passage_id'):
                try:
                    paragraph = get_passage(source['passage_id'])
                    if source.get('quote') and source['quote'] not in paragraph['text']:
                        errors.append(prefix + ': registered quote absent from frozen source')
                except (OSError, ValueError, KeyError, TypeError):
                    errors.append(prefix + ': frozen source unavailable')
        rule = rules.get(claim.get('rule_id')) if isinstance(claim.get('rule_id'), str) else None
        if claim.get('kind') == 'traditional_interpretation':
            if not rule or not set(rule['source_ids']) <= set(source_ids):
                errors.append(prefix + ': missing rule evidence')
            conditions = claim.get('conditions', {})
            if not isinstance(conditions, dict):
                conditions = {}
            required = rule['required_conditions'] if rule else []
            if any(conditions.get(k) not in ('met', 'not_met', 'unknown') for k in required):
                errors.append(prefix + ': missing conditions')
            if claim.get('status') == 'supported':
                if any(conditions.get(k) != 'met' for k in required):
                    errors.append(prefix + ': unsupported certainty')
                if any(sources.get(s, {}).get('verification') not in
                       ('transcription_checked', 'facsimile_checked') for s in source_ids):
                    errors.append(prefix + ': unverified source')
            if rule and claim.get('scope') != rule['scope']:
                errors.append(prefix + ': unsupported time precision')
        quotes = claim.get('quotes', [])
        if not isinstance(quotes, list):
            errors.append(prefix + ': invalid quotes')
            quotes = []
        for quote in quotes:
            if not isinstance(quote, dict):
                errors.append(prefix + ': invalid quote')
                continue
            sid = quote.get('source_id')
            source = sources.get(sid) if isinstance(sid, str) else None
            if (not source or not source.get('quote') or quote.get('text') != source['quote']
                    or quote.get('source_id') not in source_ids
                    or source.get('verification') not in ('transcription_checked', 'facsimile_checked')):
                errors.append(prefix + ': unverified quotation')
        passage_quotes = claim.get('passage_quotes', [])
        if not isinstance(passage_quotes, list):
            errors.append(prefix + ': invalid passage quotations')
            passage_quotes = []
        for quote in passage_quotes:
            try:
                paragraph = get_passage(quote['passage_id'])
                text = quote['text']
                if (not isinstance(text, str) or not text.strip() or text not in paragraph['text']
                        or quote.get('layer') != paragraph['layer']):
                    errors.append(prefix + ': quotation or text layer differs from frozen source')
            except (OSError, ValueError, KeyError, TypeError):
                errors.append(prefix + ': invalid passage quotation')
        if 'probability' in claim or 'confidence_percent' in claim:
            errors.append(prefix + ': uncalibrated probability')
    return errors


def render_packet(packet: dict) -> str:
    """Readable inspection artifact, not a substitute for answering the user's question."""
    sources = {s['id']: s for s in load_evidence()['sources']}
    parts = []
    for claim in packet['claims']:
        label = '盘面事实' if claim['kind'] == 'chart_fact' else '待核条件'
        refs = [f"[{sources[s]['title']}·{sources[s]['chapter']}]({sources[s]['url']})"
                for s in claim['source_ids'] if s in sources]
        parts.append(f"**{label}：** {claim['text']}" + ('\n\n依据：' + '；'.join(refs) if refs else ''))
    return '\n\n'.join(parts)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='核查结论中的盘面、条款和条件；不验证现实预测',
        epilog='Top-level JSON keys: ok tool version errors packet semantic_review; errors: error message')
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--chart', help='chart JSON file')
    inputs.add_argument('--stdin', action='store_true', help='read {chart, packet?} from stdin')
    parser.add_argument('--packet', help='review this claims JSON instead of producing a packet')
    parser.add_argument('--markdown', action='store_true', help='render a readable evidence summary')
    args = parser.parse_args(argv)
    try:
        if args.stdin and hasattr(sys.stdin, 'reconfigure'):
            sys.stdin.reconfigure(encoding='utf-8', errors='strict')
        bundle = json.load(sys.stdin) if args.stdin else {}
        chart = bundle['chart'] if args.stdin else json.loads(Path(args.chart).read_text(encoding='utf-8'))
        if args.stdin and 'packet' in bundle:
            packet = bundle['packet']
        elif args.packet:
            packet = json.loads(Path(args.packet).read_text(encoding='utf-8'))
        else:
            if chart.get('tool') not in ('bazi', 'bazi_reading') or not chart.get('ok'):
                raise ValueError('automatic packet requires a successful bazi chart')
            packet = (chart['reading_support'] if chart['tool'] == 'bazi_reading'
                      else bazi_reading_packet(chart))
        errors = review_claims(chart, packet)
        if args.markdown and not errors:
            ensure_utf8_stdio()
            print(render_packet(packet))
        else:
            json_print({'ok': not errors, 'tool': 'reading_review', 'version': __version__, 'errors': errors,
                        'packet': packet, 'semantic_review': 'required'})
        return 1 if errors else 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        json_print(error_envelope('reading_review', 'invalid_input', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
