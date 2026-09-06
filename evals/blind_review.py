"""Export version-masked review packets; import signed rubrics into new copies.

Raw recordings are never edited. This masks metadata, not implementation clues
in the actual answers, and does not turn an in-session review into an external
blind study. All output directories must be outside the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from evaluate_readings import answer_digest

ROOT = Path(__file__).resolve().parents[1]


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def write_new(path: Path, value: object) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def outside_repo(path: Path) -> Path:
    path = path.resolve()
    if path.is_relative_to(ROOT):
        raise ValueError('review exports and private mappings must remain outside the repository')
    return path


def mask_trace(value: object, cwd: str, commit: str) -> object:
    """Display-only redaction; hashes still bind to the original complete row."""
    if isinstance(value, dict):
        hidden = {'cwd', 'processId', 'pluginId', 'scriptPath'}
        return {key: '<tool-version>' if key == 'version' else mask_trace(item, cwd, commit)
                for key, item in value.items() if key not in hidden}
    if isinstance(value, list):
        return [mask_trace(item, cwd, commit) for item in value]
    if not isinstance(value, str):
        return value
    if cwd:
        for candidate in {cwd, cwd.replace('\\', '/'), cwd.replace('\\', '\\\\')}:
            value = value.replace(candidate, '<snapshot>')
    if commit:
        value = value.replace(commit, '<commit>')
    # Preserve script arguments and relative paths, hide machine executable paths.
    value = re.sub(r'[A-Za-z]:[\\/][^\r\n"\']*?\.exe', '<host-executable>', value)
    value = re.sub(r'(?i)(["\']?version["\']?\s*[:=]\s*["\']?)\d+\.\d+\.\d+(?:[-+][\w.-]+)?',
                   r'\1<tool-version>', value)
    return value


def export_packets(spec: dict, sources: list[tuple[str, Path]], public: Path,
                   private: Path, seed: int) -> dict:
    public, private = outside_repo(public), outside_repo(private)
    if public.is_relative_to(private) or private.is_relative_to(public):
        raise ValueError('public and private directories must be disjoint')
    cases = {case['id']: case for case in spec['cases']}
    rows = []
    identities = set()
    for version, path in sources:
        recording = json.loads(path.read_text(encoding='utf-8'))
        for row in recording['responses']:
            identity = (version, row['case_id'], row.get('repetition'))
            if row['case_id'] not in cases or identity in identities:
                raise ValueError('unknown case or duplicate version/case/repetition')
            identities.add(identity)
            rows.append((answer_digest(row), version, path.resolve(), recording, row))
    # Hash ordering prevents a known version-first input order plus public seed
    # from trivially revealing versions. Original rows contain opaque host IDs.
    rows.sort(key=lambda entry: entry[0])
    random.Random(seed).shuffle(rows)
    public.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=False)
    mapping, packets, reviews = [], [], []
    for index, (row_hash, version, path, recording, row) in enumerate(rows, 1):
        blind_id = f'R{index:03d}'
        case = cases[row['case_id']]
        host = row.get('host') or {}
        trace = row.get('tool_calls', [])
        trace_summary = []
        for tool_index, item in enumerate(trace, 1):
            displayed = mask_trace({key: value for key, value in item.items() if key != 'id'},
                                   host.get('cwd', ''), recording.get('commit', ''))
            evidence_name = f'{blind_id}-tool-{tool_index:03d}.json'
            write_new(public / evidence_name, displayed)
            trace_summary.append({
                'index': tool_index,
                **{key: displayed[key] for key in ('type', 'command', 'query', 'status', 'exitCode', 'durationMs') if key in displayed},
                'evidence_file': evidence_name, 'evidence_display_sha256': digest(displayed),
                'original_item_sha256': digest(item)})
        packet = {
            'blind_id': blind_id, 'case_id': case['id'],
            'case': {key: case[key] for key in ('group', 'prompt', 'turns', 'acceptance') if key in case},
            'text': row.get('text', ''),
            'turns': [{key: turn.get(key) for key in ('index', 'prompt', 'text', 'status', 'error')}
                      for turn in row.get('turns', [])],
            'execution_error': mask_trace(row.get('execution_error'), host.get('cwd', ''), recording.get('commit', '')),
            'tool_trace_summary': trace_summary,
            'binding': {'source_answer_sha256': row_hash,
                        'text_utf8_sha256': hashlib.sha256(row.get('text', '').encode('utf-8')).hexdigest(),
                        'ordered_tool_trace_sha256': digest(trace)},
            'display_limit': 'Answer text is unchanged. Tool display masks host IDs, paths and explicit version metadata; capability/source differences can still reveal a version. Originals stay in the private mapping.'}
        package_hash = digest(packet)
        packet['package_sha256'] = package_hash
        write_new(public / f'{blind_id}.json', packet)
        packets.append({'blind_id': blind_id, 'case_id': case['id'], 'package_sha256': package_hash})
        mapping.append({'blind_id': blind_id, 'version': version, 'source': str(path),
                        'case_id': row['case_id'], 'repetition': row.get('repetition'),
                        'answer_sha256': row_hash, 'package_sha256': package_hash})
        reviews.append({'blind_id': blind_id, 'package_sha256': package_hash,
                        'reviewer': None, 'disposition': None,
                        'criteria': dict.fromkeys(spec['criteria']),
                        'comprehension': {'main_point': None, 'evidence': None, 'limits': None},
                        'notes': None})
    manifest = {'schema_version': '2.0', 'seed': seed, 'packets': packets,
                'criteria': spec['criteria'], 'dispositions': spec['dispositions'],
                'instructions': 'Read every turn and relevant tool evidence. Restate the main conclusion, supporting evidence and limitation in your own words. Do not score readability by length, string matching or jargon count. Record incomplete answers and errors; do not infer semantic correctness from execution success. Do not inspect the private mapping or tested worktrees before submitting reviews.',
                'review_scope': 'version-masked in-session review, not an external blind study'}
    write_new(public / 'manifest.json', manifest)
    write_new(public / 'reviews-template.json', {'reviews': reviews})
    write_new(private / 'mapping.json', {'seed': seed, 'entries': mapping,
                                        'cases_sha256': digest(spec), 'public': str(public)})
    return {'packets': len(packets), 'public': str(public), 'private': str(private)}


def observed_metrics(row: dict) -> dict:
    """Host-visible observations only; missing usage is unknown, never zero."""
    trace = row.get('tool_calls') or []
    outputs = []
    for item in trace:
        if isinstance(item.get('aggregatedOutput'), str):
            outputs.append(item['aggregatedOutput'])
        elif 'result' in item:
            outputs.append(json.dumps(item['result'], ensure_ascii=False))
    return {'elapsed_seconds': row.get('elapsed_seconds'),
            'usage_total': (row.get('usage') or {}).get('total'),
            'tool_item_counts': dict(Counter(item.get('type', 'unknown') for item in trace)),
            'captured_tool_output_utf8_bytes': sum(len(output.encode('utf-8')) for output in outputs),
            'captured_output_items': len(outputs), 'total_tool_items': len(trace),
            'output_scope': 'aggregatedOutput strings and serialized result objects only; web search/native items may lack output bodies'}


def import_reviews(spec: dict, public: Path, private: Path, reviews_path: Path,
                   output: Path) -> dict:
    output = outside_repo(output)
    mapping = json.loads((private / 'mapping.json').read_text(encoding='utf-8'))
    if mapping['cases_sha256'] != digest(spec):
        raise ValueError('case specification changed since export')
    reviews = json.loads(reviews_path.read_text(encoding='utf-8'))['reviews']
    by_id = {review['blind_id']: review for review in reviews}
    if len(by_id) != len(reviews):
        raise ValueError('duplicate review ID')
    known_ids = {entry['blind_id'] for entry in mapping['entries']}
    if set(by_id) - known_ids:
        raise ValueError('unknown review ID')
    output.mkdir(parents=True, exist_ok=False)
    sources, summary, pending, imported = {}, defaultdict(list), [], 0
    for entry in mapping['entries']:
        source = entry['source']
        if source not in sources:
            sources[source] = json.loads(Path(source).read_text(encoding='utf-8'))
            for source_row in sources[source]['responses']:
                source_row['review'] = None
        row = next(row for row in sources[source]['responses']
                   if row['case_id'] == entry['case_id'] and row.get('repetition') == entry['repetition'])
        if answer_digest(row) != entry['answer_sha256']:
            raise ValueError('original answer or tool trace changed: ' + entry['blind_id'])
        packet = json.loads((public / (entry['blind_id'] + '.json')).read_text(encoding='utf-8'))
        stated = packet.pop('package_sha256')
        if stated != entry['package_sha256'] or digest(packet) != stated:
            raise ValueError('review packet changed: ' + entry['blind_id'])
        for tool in packet['tool_trace_summary']:
            evidence = public / tool['evidence_file']
            if evidence.resolve().parent != public.resolve():
                raise ValueError('invalid review evidence path')
            if digest(json.loads(evidence.read_text(encoding='utf-8'))) != tool['evidence_display_sha256']:
                raise ValueError('review evidence changed: ' + entry['blind_id'])
        review = by_id.get(entry['blind_id']) or {}
        complete = (review.get('reviewer') and review.get('notes')
                    and review.get('disposition') in spec['dispositions']
                    and all(review.get('criteria', {}).get(key) in ('pass', 'fail') for key in spec['criteria'])
                    and all(isinstance(review.get('comprehension', {}).get(key), str)
                            and review['comprehension'][key].strip() for key in ('main_point', 'evidence', 'limits')))
        if not complete:
            pending.append(entry['blind_id'])
            continue
        if review.get('package_sha256') != stated:
            raise ValueError('review is not bound to the exported packet: ' + entry['blind_id'])
        row['review'] = {key: value for key, value in review.items() if key not in ('blind_id', 'package_sha256')}
        row['review']['answer_sha256'] = entry['answer_sha256']
        imported += 1
        summary[entry['version']].append({'blind_id': entry['blind_id'], 'case_id': row['case_id'],
                                          'disposition': review['disposition'], 'criteria': review['criteria'],
                                          'complete_supported_answer': review['disposition'] == 'answered'
                                          and all(value == 'pass' for value in review['criteria'].values()),
                                          'observations': observed_metrics(row)})
    for index, (source, recording) in enumerate(sources.items(), 1):
        write_new(output / f'reviewed-recording-{index}.json', {'original_source': source, **recording})
    result = {'imported': imported, 'pending': pending,
              'versions': {version: {'dispositions': dict(Counter(row['disposition'] for row in rows)),
                                    'criteria_failures': dict(Counter(key for row in rows for key, value in row['criteria'].items() if value == 'fail')),
                                    'rows': rows} for version, rows in summary.items()},
              'comparison_limit': 'Compare costs within the same case and task-completion category. These are recorded judgments and observed host usage, not proof of predictive accuracy or exact billed cost.'}
    write_new(output / 'summary.json', result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    export = sub.add_parser('export')
    export.add_argument('--source', action='append', required=True, help='VERSION=recording.json; repeat for every version/run')
    export.add_argument('--public', type=Path, required=True)
    export.add_argument('--private', type=Path, required=True)
    export.add_argument('--seed', type=int, required=True)
    collect = sub.add_parser('import')
    collect.add_argument('--public', type=Path, required=True)
    collect.add_argument('--private', type=Path, required=True)
    collect.add_argument('--reviews', type=Path, required=True)
    collect.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        spec = json.loads(args.cases.read_text(encoding='utf-8'))
        if args.action == 'export':
            sources = [(value.split('=', 1)[0], Path(value.split('=', 1)[1])) for value in args.source]
            result = export_packets(spec, sources, args.public, args.private, args.seed)
        else:
            result = import_reviews(spec, args.public, args.private, args.reviews, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
