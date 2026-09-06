"""Maintainer-only importer for frozen public-domain transcriptions.

Not part of the runtime skill. Network retrieval is explicit; normal search is
offline. Raw source, revision, chapter inventory and transcription caveats are
kept so acquiring every declared chapter never implies facsimile verification.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'knowledge'
API = 'https://zh.wikisource.org/w/api.php'
AGENT = 'ChineseFortuneClassicalLibrary/2.1 (public-domain transcription archive)'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, data: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    path.write_bytes(content)
    return digest(content)


def wiki_pages(titles: list[str]) -> dict[str, dict]:
    """Retrieve raw revisions, without trusting mutable expanded transclusions."""
    result = {}
    for start in range(0, len(titles), 15):
        query = {'action': 'query', 'titles': '|'.join(titles[start:start + 15]),
                 'prop': 'revisions', 'rvprop': 'ids|timestamp|content',
                 'rvslots': 'main', 'format': 'json'}
        request = urllib.request.Request(API + '?' + urllib.parse.urlencode(query),
                                         headers={'User-Agent': AGENT})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2)
        for page in payload['query']['pages'].values():
            if 'missing' in page:
                raise ValueError('source page missing: ' + page['title'])
            revision = page['revisions'][0]
            result[page['title']] = {'title': page['title'], 'revision': str(revision['revid']),
                                     'timestamp': revision['timestamp'],
                                     'raw': revision['slots']['main']['*']}
    return result


def wiki_url(title: str, revision: str) -> str:
    return 'https://zh.wikisource.org/w/index.php?' + urllib.parse.urlencode(
        {'title': title, 'oldid': revision})


@lru_cache(maxsize=1)
def glyphs() -> dict:
    path = ROOT / 'sources' / 'skchar.json'
    return json.loads(path.read_text(encoding='utf-8'))['entries'] if path.exists() else {}


def clean_wiki(raw: str) -> str:
    """Keep source words; remove display templates, never synthesize missing text."""
    raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    if '<onlyinclude>' in raw:
        raw = '\n'.join(re.findall(r'<onlyinclude>(.*?)</onlyinclude>', raw, re.S))

    def template(match: re.Match) -> str:
        parts = match.group(1).split('|')
        name = parts[0].strip().lower()
        if name == 'sk anchor':
            return '\n== ' + '|'.join(parts[1:]) + ' ==\n'
        if name == 'sk notes':
            return '〔注文〕' + '|'.join(parts[1:]) + '〔/注文〕'
        if name == 'skchar' and len(parts) > 1:
            value = glyphs().get(parts[1], {})
            return value.get('character') or f"〔字形SK{parts[1]}：{value.get('description') or '未编码'}〕"
        if name in ('+', 'lang', 'color', '字', 'yl'):
            return parts[-1] if len(parts) > 1 else ''
        if name in ('header', 'novel', 'novel-f', 'footer', 'pd-old', '明朝作品',
                    'wwc', 'no source', '傳統漢字化', 'skqs header', 'skqs footer'):
            return ''
        # Unrecognized markup is retained for inspection instead of deleted.
        return '〔未解析模板:' + match.group(1) + '〕'

    while re.search(r'\{\{[^{}]*\}\}', raw):
        raw = re.sub(r'\{\{([^{}]*)\}\}', template, raw)
    raw = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', raw)
    raw = re.sub(r'\[\[([^\]]+)\]\]', r'\1', raw)
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.I)
    raw = re.sub(r'<[^>]*>', '', raw)
    raw = re.sub(r'__\w+__', '', raw)
    return html.unescape(raw.replace("'''", '').replace("''", ''))


def paragraphs(raw: str, default_title: str, default_layer: str) -> list[dict]:
    section = default_title
    result = []
    for block in re.split(r'\n\s*\n|(?=^==)', clean_wiki(raw), flags=re.M):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        pending: list[str] = []
        for line in lines:
            heading = re.fullmatch(r'=+\s*(.*?)\s*=+', line.strip())
            if heading:
                if pending:
                    result.append({'section': section, 'text': '\n'.join(pending), 'layer': default_layer})
                    pending = []
                section = heading.group(1)
            elif line.strip():
                pending.append(line.strip())
        if pending:
            text = '\n'.join(pending)
            layer = default_layer
            if text.startswith(':'):
                text = re.sub(r'^:+[\s\u3000]*', '', text, flags=re.M)
                layer = 'commentary'
            elif '〔注文〕' in text:
                layer = 'base_text_with_commentary'
            result.append({'section': section, 'text': text, 'layer': layer})
    return result


def make_book(book_id: str, title: str, edition: str, index: dict,
              chapters: list[tuple[str, str, dict]], *, source_flags: list[str] | None = None) -> dict:
    """Write chapter bytes and their fixed source manifests."""
    book = {'id': book_id, 'title': title, 'edition': edition,
            'source_url': index.get('source_url') or wiki_url(index['title'], index['revision']),
            'revision': index['revision'], 'source_timestamp': index['timestamp'],
            'license': index.get('license') or {'original': 'Public domain: historical work',
                        'transcription': 'Wikisource attribution retained; CC BY-SA 4.0 where applicable',
                        'url': 'https://creativecommons.org/licenses/by-sa/4.0/'},
            'layer': 'historical_work_transcription',
            'facsimile_status': 'not_checked',
            'transcription_status': 'acquired_not_collated',
            'source_flags': source_flags or [],
            'expected_chapters': [c[0] for c in chapters], 'chapters': []}
    raw_dir = ROOT / 'sources' / book_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_index = index['raw'].encode('utf-8')
    extension = index.get('format', 'wiki')
    (raw_dir / ('_index.' + extension)).write_bytes(raw_index)
    book['index_path'] = f'sources/{book_id}/_index.{extension}'
    book['index_sha256'] = digest(raw_index)
    for chapter_id, chapter_title, page in chapters:
        url = page.get('source_url') or wiki_url(page['title'], page['revision'])
        raw_bytes = page['raw'].encode('utf-8')
        raw_path = f"sources/{book_id}/{chapter_id}.{page.get('format', 'wiki')}"
        (ROOT / raw_path).write_bytes(raw_bytes)
        items = page.get('passages') or paragraphs(page['raw'], chapter_title, 'base_text')
        for position, item in enumerate(items, 1):
            item.update({'passage_id': f'{book_id}:{chapter_id}:p{position:04}',
                         'sha256': digest(item['text'].encode('utf-8'))})
        issues = [{'passage_id': item['passage_id'], 'kind': 'source_uncertainty_marker'}
                  for item in items if re.search(r'[□�]|未解析模板|字形SK', item['text'])]
        issues.extend({'passage_id': item['passage_id'], 'kind': 'commentary_boundary_unresolved'}
                      for item in items if item.get('layer_status') in
                      ('explicit_marker_open_boundary', 'commentary_boundary_uncertain'))
        chapter = {'book_id': book_id, 'chapter_id': chapter_id, 'title': chapter_title,
                   'source_url': url, 'revision': page['revision'],
                   'source_timestamp': page['timestamp'], 'layer': 'historical_work_transcription',
                   'facsimile_status': 'not_checked', 'transcription_status': 'acquired_not_collated',
                   'raw_path': raw_path, 'raw_sha256': digest(raw_bytes),
                   'raw_kind': page.get('raw_kind', 'source_wikitext'),
                   'extraction_kind': page.get('extraction_kind', 'frozen_mediawiki_revision'),
                   'issues': issues, 'passages': items}
        path = f'books/{book_id}/{chapter_id}.json'
        sha = write_json(ROOT / path, chapter)
        book['chapters'].append({'id': chapter_id, 'title': chapter_title, 'path': path,
                                 'sha256': sha, 'source_url': url, 'revision': page['revision'],
                                 'passage_count': len(items), 'issue_count': len(issues)})
    book['completeness'] = {'acquisition': 'complete' if all(c['passage_count'] for c in book['chapters'])
                            and not book['source_flags'] else 'incomplete_or_source_uncertain',
                            'scope': 'declared source edition and frozen chapter inventory only',
                            'expected_count': len(chapters), 'acquired_count': len(book['chapters']),
                            'missing_chapters': [], 'missing_facsimile_pages': 'not_assessed',
                            'historical_edition_verified': False}
    return book


def import_wikisource() -> list[dict]:
    index_titles = ['滴天髓', '三命通會 (四庫全書本)']
    indexes = wiki_pages(index_titles)
    ditian_names = re.findall(r'==\[\[滴天髓/(\d+)\|([^\]]+)\]\]==', indexes['滴天髓']['raw'])
    if len(ditian_names) != 42:
        raise ValueError('滴天髓 frozen edition must have 42 sections')
    names = [f'滴天髓/{number}' for number, _ in ditian_names]
    names += [f'三命通會 (四庫全書本)/卷{i:02}' for i in range(1, 13)]
    pages = wiki_pages(names)
    books = [make_book('ditian', '滴天髓', '滴天髓輯要，维基文库逐章转录', indexes['滴天髓'],
                      [(f'c{int(n):03}', title, pages[f'滴天髓/{n}']) for n, title in ditian_names])]
    sanming = indexes['三命通會 (四庫全書本)']
    sanming['passages'] = paragraphs(sanming['raw'], '提要', 'paratext')
    books.append(make_book('sanming', '三命通会', '文渊阁四库全书本，维基文库转录', sanming,
                          [('c000', '提要', sanming)] +
                          [(f'c{i:03}', f'卷{i:02}', pages[f'三命通會 (四庫全書本)/卷{i:02}'])
                           for i in range(1, 13)]))
    return books


def historical_commentary_layer(text: str, default_layer: str) -> dict:
    """Mark explicit notes without guessing the authorship of unmarked text.

    Offsets refer to unchanged Python string positions. An unclosed note stops
    at this source paragraph; following paragraphs remain unclassified rather
    than being silently promoted to either original text or commentary.
    """
    marker = re.compile(r'(?:【)?(?:眉批|原[注註]|[夾夹][注註])(?:】)?[：:]')
    matches = list(marker.finditer(text))
    if not matches:
        return {'layer': default_layer}
    spans: list[dict] = []
    for match in matches:
        if spans and match.start() < spans[-1]['end']:
            continue
        prefix = text[:match.start()].rstrip()
        start = match.start()
        end = len(text)
        closed = False
        if not prefix:
            closed = True  # A standalone labelled paragraph is wholly a note.
        elif prefix[-1] in '(（':
            start = len(prefix) - 1
            depth = 1
            for position in range(match.end(), len(text)):
                if text[position] in '(（':
                    depth += 1
                elif text[position] in ')）':
                    depth -= 1
                    if depth == 0:
                        end, closed = position + 1, True
                        break
        else:
            # A mentioned label without an observed boundary is not enough.
            return {'layer': 'historical_work_transcription',
                    'layer_status': 'commentary_boundary_uncertain'}
        spans.append({'start': start, 'end': end, 'layer': 'historical_commentary',
                      'marker': match.group(0), 'boundary_closed': closed})
    outside = text
    for span in reversed(spans):
        outside = outside[:span['start']] + outside[span['end']:]
    mixed = bool(outside.strip(' \t\r\n。；;，,、：:'))
    return {'layer': 'historical_work_transcription_with_commentary' if mixed else 'historical_commentary',
            'commentary_spans': spans,
            'layer_status': 'explicit_marker_not_collated' if all(s['boundary_closed'] for s in spans)
                            else 'explicit_marker_open_boundary'}


def html_paragraphs(raw: str, title: str, default_layer: str = 'base_text') -> list[dict]:
    """Read frozen source paragraph boundaries without including site chrome."""
    items = []
    section = title
    for match in re.finditer(r'<(p|h[1-6])\b[^>]*>(.*?)</\1>', raw, re.S | re.I):
        text = html.unescape(re.sub(r'<[^>]+>', '', match.group(2))).strip()
        if not text:
            continue
        if match.group(1).lower().startswith('h'):
            section = text
        else:
            heading = re.match(r'^(?:三[春夏秋冬][甲乙丙丁戊己庚辛壬癸][木火土金水](?:总论)?'
                               r'|(?:正|十[一二]?|[一二三四五六七八九])月[甲乙丙丁戊己庚辛壬癸][木火土金水]'
                               r'|[春夏秋冬]月之[木火土金水])', text)
            if heading:
                section = title + ' / ' + heading.group(0)
            items.append({'section': section, 'text': text,
                          **historical_commentary_layer(text, default_layer)})
    return items


def import_captured_html(book_id: str) -> dict:
    directory = ROOT / 'sources' / book_id
    metadata = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
    raw_index = (directory / metadata.get('index_file', 'directory.html')).read_text(encoding='utf-8')
    index = {'title': metadata['book'], 'revision': 'sha256:' + digest(raw_index.encode('utf-8')),
             'timestamp': metadata['retrieved_at'], 'raw': raw_index, 'format': 'html',
             'source_url': metadata['source_url'],
             'license': {'original': 'Public domain historical text only',
                         'transcription': metadata['licensing'],
                         'attribution': metadata.get('attribution', metadata['source_url'])}}
    chapters = []
    for row in metadata['chapters']:
        if row['status'] != 'captured':
            continue
        raw = (directory / row['file']).read_text(encoding='utf-8')
        content_hash = digest(raw.encode('utf-8'))
        if row['html_sha256'] != content_hash:
            raise ValueError('captured source hash mismatch: ' + row['file'])
        default_layer = ('historical_work_transcription' if book_id == 'yuanhai'
                         else row.get('layer', 'base_text'))
        if default_layer == 'historical_preface':
            default_layer = 'paratext'
        page = {'title': row['title'], 'source_url': row['source_url'],
                'revision': 'sha256:' + content_hash, 'timestamp': row['retrieved_at'],
                'raw': raw, 'format': 'html', 'passages': html_paragraphs(raw, row['title'], default_layer),
                'raw_kind': 'cleaned_original_transcription_not_complete_http_response',
                'extraction_kind': row.get('extraction_kind', metadata.get('extraction_kind',
                                                                         'selected_original_html_node'))}
        chapters.append(('c' + row['chapter_id'].zfill(3), row['title'], page))
    if len(chapters) != metadata['expected_chapters']:
        raise ValueError('captured chapter count differs from independent source inventory')
    book = make_book(book_id, metadata['book'], metadata['edition'], index, chapters)
    book['editorial_policy'] = metadata['editorial_policy']
    book['known_quality_issues'] = metadata.get('known_quality_issues', [])
    book['extraction_kind'] = metadata.get('extraction_kind', 'selected_original_html_node')
    book['extraction_note'] = metadata.get('extraction_note', metadata.get('selection', ''))
    if book_id == 'yuanhai':
        book['layer_policy'] = ('Explicit labelled notes are historical_commentary; paragraphs containing '
                                'other text are historical_work_transcription_with_commentary. Unmarked '
                                'paragraphs remain historical_work_transcription. Open note boundaries '
                                'do not establish the layer of following paragraphs; image collation pending.')
    metadata['index_file'] = '_index.html'
    for row in metadata['chapters']:
        row['file'] = 'c' + row['chapter_id'].zfill(3) + '.html'
    book['source_metadata_path'] = f'sources/{book_id}/metadata.json'
    book['source_metadata_sha256'] = write_json(directory / 'metadata.json', metadata)
    return book


def capture_qiongtong() -> None:
    """The Wikisource page omits the general metal section; use one six-volume source."""
    url = 'https://www.gushiwen.cn/guwen/book_112f16f9deeb.aspx'
    directory = ROOT / 'sources' / 'qiongtong'
    directory.mkdir(parents=True, exist_ok=True)

    def fetch(address: str) -> str:
        request = urllib.request.Request(address, headers={'User-Agent': AGENT})
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.read().decode('utf-8')

    raw = fetch(url)
    links = re.findall(r'<a[^>]+href="(/guwen/bookv_[^"]+)"[^>]*>(卷[一二三四五六]·[^<]+)</a>', raw)
    links = sorted(set(links), key=lambda row: '一二三四五六'.index(row[1][1]))
    if len(links) != 6:
        raise ValueError('qiongtong source must list six volumes')
    # Retain a minimal source-derived directory, not contemporary site prose.
    index = '<ol>' + ''.join(f'<li><a href="https://www.gushiwen.cn{link}">{title}</a></li>'
                            for link, title in links) + '</ol>\n'
    (directory / 'directory.html').write_text(index, encoding='utf-8')
    metadata: dict = {'book': '穷通宝鉴', 'edition': '古文岛六卷网络转录，具体印本未注明',
                'source_url': url, 'expected_chapters': 6, 'captured_chapters': 0,
                'verification': 'network_transcription_not_facsimile_collated',
                'licensing': 'Public-domain historical original text only; modern translation and commentary excluded',
                'attribution': '古文岛/古诗文网，各卷附原始来源地址',
                'editorial_policy': '保留网络转录原字、疑字和句读，不静默修正。',
                'known_quality_issues': ['具体印本未注明；网络转录不等于原刻影像已校。'],
                'retrieved_at': datetime.now(UTC).isoformat(), 'chapters': []}
    for i, (link, title) in enumerate(links, 1):
        address = 'https://www.gushiwen.cn' + link
        content = fetch(address)
        match = re.search(r'<div\s+class="contson"[^>]*>(.*?)</div>', content, re.S)
        if not match:
            raise ValueError('original content node missing: ' + address)
        original = '<article>' + match.group(1) + '</article>\n'
        path = f'{i:03}.html'
        (directory / path).write_text(original, encoding='utf-8')
        metadata['chapters'].append({'chapter_id': f'{i:03}', 'title': title,
                                    'source_url': address, 'status': 'captured', 'file': path,
                                    'html_sha256': digest(original.encode('utf-8')),
                                    'retrieved_at': datetime.now(UTC).isoformat()})
    metadata['captured_chapters'] = len(metadata['chapters'])
    write_json(directory / 'metadata.json', metadata)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog='Top-level JSON keys: books')
    parser.add_argument('--wikisource', action='store_true')
    parser.add_argument('--capture-qiongtong', action='store_true')
    parser.add_argument('--captured-html', choices=['ziping', 'qiongtong', 'yuanhai'], action='append', default=[])
    args = parser.parse_args()
    if not (args.wikisource or args.capture_qiongtong or args.captured_html):
        parser.error('choose a retrieval/import operation')
    if args.capture_qiongtong:
        capture_qiongtong()
    books = import_wikisource() if args.wikisource else []
    books += [import_captured_html(book_id) for book_id in args.captured_html]
    manifest_path = ROOT / 'manifest.json'
    existing = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    replaced = {book['id'] for book in books}
    books += [b for b in existing.get('books', []) if b['id'] not in replaced]
    manifest = {'schema_version': '1.0', 'library_id': 'bazi-five-classics-v1',
                'required_books': ['ziping', 'ditian', 'qiongtong', 'sanming', 'yuanhai'],
                'retrieval_policy': 'offline; preserve original words; historical text is not personal advice',
                'books': sorted(books, key=lambda b: b['id'])}
    glyph_path = ROOT / 'sources' / 'skchar.json'
    if glyph_path.exists():
        source = json.loads(glyph_path.read_text(encoding='utf-8'))
        manifest['supporting_sources'] = [{'path': 'sources/skchar.json',
                                          'sha256': digest(glyph_path.read_bytes()),
                                          **{key: source[key] for key in ('source_url', 'revision', 'license')}}]
    write_json(manifest_path, manifest)
    print(json.dumps({'books': [(b['id'], len(b['chapters'])) for b in books]}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
