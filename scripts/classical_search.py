"""Offline, provenance-preserving retrieval from the frozen classical library.

Full chapter acquisition, faithful transcription and historical predictive
validity are separate claims. Search certifies none of the latter two.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / 'knowledge'
# Common book names and technical queries. Original source words are untouched.
# This is deliberately a documented query alias table, not a general converter.
_TRAD = '詮淵窮寶鑑會髓傷財殺煞調氣候敗救應論強弱體歲運時陰陽從與為無見後先根透藏純雜順逆取捨輕濁清寒暖貴賤祿祿長養虛實隱顯眾寡進退剋沖衝無印綬臺門書經傳徵變剛柔母親姻類祇神總說節錄萬歸於東裡細賦斷機關榮壽興濕燥亙異劫祿學命實驗獲錯緩緣該當選數項規則檢查兩個陰間風險運勢轉暫未暫時條'
_SIMP = '诠渊穷宝鉴会髓伤财杀煞调气候败救应论强弱体岁运时阴阳从与为无见后先根透藏纯杂顺逆取舍轻浊清寒暖贵贱禄禄长养虚实隐显众寡进退克冲冲无印绶台门书经传征变刚柔母亲姻类祇神总说节录万归于东里细赋断机关荣寿兴湿燥亘异劫禄学命实验获错缓缘该当选数项规则检查两个阴间风险运势转暂未暂时条'
_ALIASES = str.maketrans(_TRAD, _SIMP)
_ALIASES.update({ord(k): ord(v) for k, v in {'專': '专', '爲': '为', '尅': '克', '須': '须',
                                          '補': '补', '護': '护', '洩': '泄', '幹': '干',
                                          '驛': '驿', '馬': '马', '蓋': '盖', '葢': '盖',
                                          '詞': '词', '館': '馆', '貴': '贵', '華': '华'}.items()})


def normalized(text: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text).translate(_ALIASES)).lower()


def _root(root: Path | str | None) -> Path:
    return Path(root).resolve() if root is not None else LIBRARY_ROOT.resolve()


def _path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError('library path escapes its root')
    return path


def _read(path: Path) -> dict:
    content = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(content, dict):
        raise ValueError('library document must be an object')
    return content


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checked_name(name: str) -> str:
    if not isinstance(name, str) or not name or name.startswith('/') or "\\" in name:
        raise ValueError('invalid distribution path')
    if any(part in ('', '.', '..') or ':' in part for part in name.split('/')):
        raise ValueError('unsafe distribution path: ' + name)
    return name


def _checked_digest(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('invalid SHA256 digest')
    return value


def _validate_distribution(root: Path, manifest: dict) -> str:
    if manifest.get('schema_version') != '2.0':
        raise ValueError('unsupported library schema_version; expected 2.0')
    kind = manifest.get('distribution_kind')
    if kind not in ('source', 'runtime'):
        raise ValueError('distribution_kind must explicitly be source or runtime')
    if kind == 'runtime':
        if manifest.get('source_paths_scope') != 'source_archive/knowledge':
            raise ValueError('runtime raw pointers must refer to source_archive/knowledge')
        archive = manifest['source_archive']
        name = _checked_name(archive['filename'])
        if '/' in name or not name.endswith('.zip'):
            raise ValueError('source archive must have a ZIP filename')
        _checked_digest(archive['sha256'])
        if not archive['files']:
            raise ValueError('source archive inventory is empty')
        for name, digest in archive['files'].items():
            _checked_name(name)
            _checked_digest(digest)
        files = manifest['runtime_files']
        needed = {'LICENSE', 'RELEASE.json', 'SKILL.md', 'scripts/classical_search.py', 'scripts/utils.py'}
        needed.update('knowledge/' + row['path'] for book in manifest['books'] for row in book['chapters'])
        if not needed.issubset(files) or 'knowledge/manifest.json' in files:
            raise ValueError('runtime file inventory missing required files or self-hashes its manifest')
        for name, digest in files.items():
            path = _path(root.parent, _checked_name(name))
            if _hash(path) != _checked_digest(digest):
                raise ValueError('runtime file hash mismatch: ' + name)
    return kind


def _validate_source_file(root: Path, manifest: dict, name: str, digest: str) -> None:
    name, digest = _checked_name(name), _checked_digest(digest)
    if manifest['distribution_kind'] == 'source':
        if _hash(_path(root, name)) != digest:
            raise ValueError('source hash mismatch: ' + name)
    elif manifest['source_archive']['files'].get(name) != digest:
        # Runtime validates the frozen provenance index, not unavailable raw bytes.
        raise ValueError('source archive inventory mismatch: ' + name)


def validate_library(library_root: Path | str | None = None) -> dict:
    """Recompute completeness; never trust a cached 'complete' label alone."""
    root = _root(library_root)
    errors: list[str] = []
    books = []
    kind = None
    try:
        manifest = _read(root / 'manifest.json')
        kind = _validate_distribution(root, manifest)
        required = manifest['required_books']
        if not required or len(required) != len(set(required)):
            raise ValueError('empty or duplicate required book inventory')
        actual = [b['id'] for b in manifest['books']]
        if len(actual) != len(set(actual)):
            errors.append('duplicate book id')
        for bid in required:
            if bid not in actual:
                errors.append('missing book: ' + bid)
        for source in manifest.get('supporting_sources', []):
            _validate_source_file(root, manifest, source['path'], source['sha256'])
        passage_ids: set[str] = set()
        for book in manifest['books']:
            before = len(errors)
            bid = book['id']
            expected = book['expected_chapters']
            acquired = [c['id'] for c in book['chapters']]
            if not expected or len(expected) != len(set(expected)):
                errors.append(bid + ': empty or duplicate chapter inventory')
            if len(acquired) != len(set(acquired)) or set(expected) != set(acquired):
                errors.append(bid + ': chapter inventory mismatch')
            _validate_source_file(root, manifest, book['index_path'], book['index_sha256'])
            if book.get('source_metadata_path'):
                _validate_source_file(root, manifest, book['source_metadata_path'], book['source_metadata_sha256'])
            count = 0
            for row in book['chapters']:
                cid = row['id']
                path = _path(root, row['path'])
                if not path.is_file():
                    errors.append(bid + ':' + cid + ': chapter missing')
                    continue
                if _hash(path) != row['sha256']:
                    errors.append(bid + ':' + cid + ': chapter hash mismatch')
                chapter = _read(path)
                if chapter['chapter_id'] != cid or chapter['book_id'] != bid:
                    errors.append(bid + ':' + cid + ': chapter identity mismatch')
                _validate_source_file(root, manifest, chapter['raw_path'], chapter['raw_sha256'])
                passages = chapter['passages']
                if not passages or len(passages) != row['passage_count']:
                    errors.append(bid + ':' + cid + ': empty or incomplete passages')
                for item in passages:
                    pid = item['passage_id']
                    if pid in passage_ids or not pid.startswith(bid + ':' + cid + ':'):
                        errors.append(bid + ':' + cid + ': duplicate or misplaced passage id')
                    passage_ids.add(pid)
                    if hashlib.sha256(item['text'].encode('utf-8')).hexdigest() != item['sha256']:
                        errors.append(pid + ': passage hash mismatch')
                count += len(passages)
            source_gaps = bool(book.get('source_flags'))
            missing_pages = book.get('completeness', {}).get('missing_facsimile_pages')
            has_missing_pages = isinstance(missing_pages, list) and bool(missing_pages)
            has_missing_chapters = bool(book.get('completeness', {}).get('missing_chapters'))
            if source_gaps or has_missing_pages or has_missing_chapters:
                errors.append(bid + ': declared source gap or missing chapter/page')
            books.append({'id': bid, 'title': book['title'], 'edition': book['edition'],
                          'complete_acquisition': len(errors) == before,
                          'chapters': len(acquired), 'expected_chapters': len(expected),
                          'passages': count, 'facsimile_verified': False,
                          'transcription_status': book['transcription_status'],
                          'source_flags': book.get('source_flags', [])})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return {'ok': not errors, 'schema_version': '2.0', 'distribution_kind': kind,
            'validation_scope': 'raw_sources_and_text' if kind == 'source' else 'runtime_files_and_provenance_index',
            'raw_sources_verified': kind == 'source' and not errors,
            'errors': errors, 'books': books,
            'meaning': 'Inventory and byte integrity only; runtime does not revalidate raw sources. Image collation and interpretation are separate.'}


def _selected_books(root: Path, book: str | None) -> list[dict]:
    books = _read(root / 'manifest.json')['books']
    if book:
        books = [b for b in books if normalized(book) in (normalized(b['id']), normalized(b['title']))]
        if not books:
            raise ValueError('unknown book: ' + book)
    return books


def _result(book: dict, chapter: dict, index: int) -> dict:
    passage = chapter['passages'][index]
    context = chapter['passages'][max(0, index - 1):index + 2]
    return {**passage, 'book_id': book['id'], 'book_title': book['title'],
            'edition': book['edition'], 'chapter_id': chapter['chapter_id'],
            'chapter_title': chapter['title'], 'source_url': chapter['source_url'],
            'revision': chapter['revision'], 'license': book['license'],
            'transcription_status': chapter['transcription_status'],
            'facsimile_status': chapter['facsimile_status'],
            'issues': [issue for issue in chapter.get('issues', []) if issue['passage_id'] == passage['passage_id']],
            'context': [{'passage_id': p['passage_id'], 'text': p['text'], 'layer': p['layer']}
                        for p in context],
            'use_limit': '原文查阅；不自动构成个人判断或已满足规则条件'}


def get_passage(passage_id: str, library_root: Path | str | None = None) -> dict:
    root = _root(library_root)
    parts = passage_id.split(':')
    if len(parts) != 3:
        raise ValueError('passage id must be book:chapter:passage')
    for book in _selected_books(root, parts[0]):
        for entry in book['chapters']:
            if entry['id'] == parts[1]:
                path = _path(root, entry['path'])
                if _hash(path) != entry['sha256']:
                    raise ValueError('chapter hash mismatch')
                chapter = _read(path)
                for i, passage in enumerate(chapter['passages']):
                    if passage['passage_id'] == passage_id:
                        return _result(book, chapter, i)
    raise ValueError('unknown passage: ' + passage_id)


def search_classics(query: str, book: str | None = None, chapter: str | None = None,
                    limit: int = 5, library_root: Path | str | None = None) -> list[dict]:
    """Return whole matching paragraphs plus neighbors, never invented snippets."""
    if not query.strip() or not 1 <= limit <= 50:
        raise ValueError('query required; limit must be 1..50')
    root = _root(library_root)
    terms = [normalized(term) for term in query.split()]
    found = []
    for entry in _selected_books(root, book):
        for row in entry['chapters']:
            chapter_matches = not chapter or normalized(chapter) in normalized(row['id'] + row['title'])
            path = _path(root, row['path'])
            if _hash(path) != row['sha256']:
                raise ValueError('chapter hash mismatch: ' + row['path'])
            data = _read(path)
            for i, item in enumerate(data['passages']):
                if not chapter_matches and normalized(chapter or '') not in normalized(item['section']):
                    continue
                text = normalized(item['text'])
                searchable = text + normalized(data['title']) + normalized(item['section'])
                if all(term in searchable for term in terms):
                    title = normalized(data['title'])
                    bare_title = re.sub(r'^[一二三四五六七八九十百零〇\d]+[、.．]', '', title)
                    bare_title = bare_title.removeprefix('论')
                    title_score = 2 if bare_title == normalized(query) else int(all(t in title for t in terms))
                    layer_score = {'base_text': 3, 'historical_work_transcription': 2,
                                   'base_text_with_commentary': 2, 'historical_work_transcription_with_commentary': 1,
                                   'commentary': 1, 'historical_commentary': 1,
                                   'paratext': 0, 'historical_preface': 0}.get(item['layer'], 0)
                    # For a chapter-topic query, preserve the author's exposition
                    # order; repeated keywords in a later paragraph are not a
                    # better introduction than the opening definition.
                    frequency_score = 0 if title_score == 2 else sum(text.count(term) for term in terms)
                    score = (title_score, layer_score, frequency_score)
                    found.append((score, _result(entry, data, i)))
    found.sort(key=lambda pair: (*(-v for v in pair[0]), pair[1]['passage_id']))
    return [item for _, item in found[:limit]]


def get_witnesses(passage_id: str | None = None) -> dict:
    """Expose scoped image observations without relabelling the default edition."""
    if passage_id is not None:
        get_passage(passage_id)
    data = _read(Path(__file__).resolve().parents[1] / 'assets/facsimile_witnesses.json')
    witnesses = [w for w in data['witnesses'] if passage_id is None or w['passage_id'] == passage_id]
    editions = {e['id']: e for e in data['editions']}
    for witness in witnesses:
        paragraph = get_passage(witness['passage_id'])
        if hashlib.sha256(paragraph['text'].encode('utf-8')).hexdigest() != witness['passage_sha256']:
            raise ValueError('witness refers to a different frozen paragraph')
        text = re.sub(r'[^\w]', '', paragraph['text'])
        if witness['corpus_text'] not in text:
            raise ValueError('witness corpus excerpt differs from frozen text')
        edition = editions[witness['edition_id']]
        if not 1 <= witness['pdf_page'] <= edition['pdf_pages']:
            raise ValueError('witness page outside source volume')
    used = {w['edition_id'] for w in witnesses}
    return {**{k: data[k] for k in ('schema_version', 'status', 'scope', 'reviewer', 'normalization')},
            'default_corpus_status_changed': False,
            'editions': [e for e in data['editions'] if e['id'] in used], 'records': witnesses}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description='离线检索古籍全文、出处和相邻段落',
                                     epilog='Top-level JSON keys: ok tool version results errors books; errors: error message')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--query')
    mode.add_argument('--passage-id')
    mode.add_argument('--validate', action='store_true')
    mode.add_argument('--list-books', action='store_true')
    mode.add_argument('--witnesses', nargs='?', const='all', metavar='PASSAGE_ID',
                      help='查看全部或指定段落的异版影像短句见证；不升级默认底本状态')
    parser.add_argument('--book')
    parser.add_argument('--chapter')
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args(argv)
    try:
        result: dict = {'ok': True, 'tool': 'classical_search', 'version': __version__,
                        'retrieval_schema_version': '1.0'}
        if args.validate:
            result.update(validate_library())
        elif args.witnesses:
            result['witnesses'] = get_witnesses(None if args.witnesses == 'all' else args.witnesses)
        elif args.list_books:
            result['books'] = [{k: b[k] for k in ('id', 'title', 'edition', 'completeness', 'facsimile_status')}
                               for b in _selected_books(LIBRARY_ROOT, args.book)]
        elif args.passage_id:
            result['results'] = [get_passage(args.passage_id)]
        else:
            result['results'] = search_classics(args.query, args.book, args.chapter, args.limit)
        json_print(result)
        return 0 if result['ok'] else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        json_print(error_envelope('classical_search', 'invalid_input', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
