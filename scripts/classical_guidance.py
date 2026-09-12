"""Scenario-aware classical research, kept separate from personal verdicts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from classical_search import get_chapter, get_passage, search_classics
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

CATALOG = Path(__file__).resolve().parents[1] / 'references' / 'classical-guidance.json'


def _catalog() -> dict:
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if data.get('schema_version') != '1.0':
        raise ValueError('unsupported classical guidance schema')
    return data


def research_plan(scenario: str, *, compact: bool = False) -> dict:
    """A source map is not a declaration of implemented prediction coverage."""
    data = _catalog()
    if scenario not in data['scenarios']:
        raise ValueError('unknown research scenario: ' + scenario)
    plan = data['scenarios'][scenario]
    if compact:
        return {'scenario': scenario, 'source_status': plan['source_status'],
                'command': 'python scripts/classical_guidance.py --scenario ' + scenario + ' --retrieve --limit 1',
                'personal_ranking': 'not_certified_by_source_inventory'}
    return {'scenario': scenario, **plan, 'personal_ranking': 'not_certified_by_source_inventory',
            'reading_order': ['查原文与上下文', '核对本人的适用条件与方法',
                              '审查目标时间粒度及例外', '区分古义与现代事项解释'],
            'output_order': ['白话结论', '短古籍原文与出处', '紧接白话原义和个人应用'],
            'scope': data['scope']}


def research_sources(scenario: str, *, limit: int = 2) -> dict:
    """Retrieve a bounded first pass; preserve full paragraphs and continuations."""
    if not 1 <= limit <= 3:
        raise ValueError('per-query limit must be 1..3')
    plan = research_plan(scenario)
    sections = _catalog().get('context_sections', {})
    groups = []
    for route in plan['routes']:
        if route.get('anchor'):
            source = get_passage(route['anchor']['passage_id'])
            if source['book_id'] != route['book'] or source['sha256'] != route['anchor']['sha256']:
                raise ValueError('research anchor source mismatch')
            results = [source]
        else:
            results = search_classics(route['query'], book=route['book'], limit=limit)
        group = {**route, 'results': results}
        if route.get('context_section'):
            section = sections[route['context_section']]
            included = {p['passage_id'] for p in results}
            included.update(p['passage_id'] for result in results for p in result['context'])
            extra = []
            for pid, digest in section['passage_hashes'].items():
                source = get_passage(pid)
                if source['book_id'] != route['book'] or source['sha256'] != digest:
                    raise ValueError('required context source mismatch: ' + pid)
                if pid not in included:
                    extra.append({k: source[k] for k in ('passage_id', 'text', 'layer', 'sha256',
                                                       'book_title', 'chapter_title', 'edition', 'source_url')})
            group['required_context'] = extra
            group['context_review'] = {k: v for k, v in section.items() if k != 'passage_hashes'}
            group['context_review']['verified_passage_ids'] = list(section['passage_hashes'])
        groups.append(group)
    return {'plan': plan, 'groups': groups,
            'retrieval_only': True,
            'next_step': '标题和相邻段不足时按 chapter_locator 分页读全章；空结果继续查异体字和其他版本。'}


def luck_family(family: str) -> dict:
    data = _catalog()
    if family not in data['luck_families']:
        raise ValueError('unknown luck family: ' + family)
    row = data['luck_families'][family]
    chapter = get_chapter(row['chapter'], limit=20)
    if not chapter['chapter_complete_in_this_response']:
        raise ValueError('取运章超过完整证据包容量，须更新读取流程')
    for source in chapter['results']:
        if row['passage_hashes'].get(source['passage_id']) != source['sha256']:
            raise ValueError('取运章版本变化，须重新核对：' + source['passage_id'])
    if set(row['passage_hashes']) != {p['passage_id'] for p in chapter['results']}:
        raise ValueError('取运章段落集合变化')
    return {'family': family, **row, 'evidence': chapter['results'],
            'status': 'requires_personal_condition_review',
            'temporal_scope': '大运背景；不自动扩展为逐日逐时吉凶',
            'plain_meaning': row['plain_meaning'],
            'allowed_output': '核清本人条件后解释传统取运关系；不从财官字面推出现代事件结果'}


def audit_guidance() -> dict:
    data = _catalog()
    errors = []
    for family in data['luck_families']:
        try:
            luck_family(family)
        except (ValueError, OSError, KeyError) as exc:
            errors.append(str(exc))
    for key, row in data['source_cards'].items():
        try:
            source = get_passage(row['passage_id'])
            if source['sha256'] != row['sha256'] or row['quote'] not in source['text']:
                errors.append('source card mismatch: ' + key)
        except (ValueError, OSError, KeyError) as exc:
            errors.append(str(exc))
    for scenario in data['scenarios']:
        try:
            result = research_sources(scenario, limit=1)
            for group in result['groups']:
                if not group['results']:
                    errors.append('empty research route: ' + scenario + '/' + group['query'])
        except (ValueError, OSError, KeyError) as exc:
            errors.append(str(exc))
    return {'ok': not errors, 'errors': errors, 'scenarios': len(data['scenarios']),
            'luck_families': len(data['luck_families']), 'source_cards': len(data['source_cards']),
            'scope': '来源定位、原文完整性与检索可用性；不审核个人推理或预测效度'}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__,
        epilog='Top-level JSON keys: ok tool version scenario routes groups evidence errors; '
               'all results are research or condition-review material, not personal verdicts.')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--scenario')
    mode.add_argument('--family', help='正官/财/印/食神/七杀/伤官/阳刃/禄劫')
    mode.add_argument('--audit', action='store_true')
    mode.add_argument('--list', action='store_true')
    parser.add_argument('--retrieve', action='store_true')
    parser.add_argument('--limit', type=int, default=2)
    args = parser.parse_args(argv)
    try:
        if args.audit:
            result = audit_guidance()
        elif args.family:
            result = luck_family(args.family)
        elif args.scenario:
            result = research_sources(args.scenario, limit=args.limit) if args.retrieve else research_plan(args.scenario)
        else:
            data = _catalog()
            result = {'scenarios': list(data['scenarios']), 'luck_families': list(data['luck_families']),
                      'source_cards': data['source_cards'], 'scope': data['scope']}
        json_print(ok_envelope('classical_guidance', result))
        return 0 if result.get('ok', True) else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        json_print(error_envelope('classical_guidance', 'invalid_input', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
