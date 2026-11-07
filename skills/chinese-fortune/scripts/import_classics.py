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
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from utils import UTC, ensure_utf8_stdio

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
    # From knowledge/sources/ or, packed, the repository's corpus/sources.zip (scripts/corpus_archive.py).
    from classical_search import library_bytes
    data = library_bytes(ROOT, 'sources/skchar.json')
    return json.loads(data.decode('utf-8'))['entries'] if data is not None else {}


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
        if 'extraction_version' in page:
            chapter['extraction_version'] = page['extraction_version']
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
    metadata = json.loads((directory / 'capture-metadata.json').read_text(encoding='utf-8'))
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
    book['source_metadata_path'] = f'sources/{book_id}/capture-metadata.json'
    book['source_metadata_sha256'] = write_json(directory / 'capture-metadata.json', metadata)
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
    write_json(directory / 'capture-metadata.json', metadata)


def supplement_passages(raw: str, title: str) -> list[dict]:
    """Preserve historical words and notes; explicitly remove modern editor notes.

    Unknown templates and image references remain visible uncertainty markers.
    This extractor does not assert that unmarked passages are free of later edits.
    """
    if '<onlyinclude>' in raw:
        raw = '\n'.join(re.findall(r'<onlyinclude>(.*?)</onlyinclude>', raw, re.S))
    raw = re.sub(r'\{\{\*\|原劍按[：:].*?\}\}', '', raw, flags=re.S)
    raw = re.sub(r'\{\{\*\|([^{}]*)\}\}', r'〔注文〕\1〔/注文〕', raw)
    raw = re.sub(r'\{\{(?:Header2|Textquality|未排版|Uncategorized|further)\b.*?\}\}',
                 '', raw, flags=re.S | re.I)
    raw = re.sub(r'-\{([^{}]+)\}-', r'\1', raw)
    raw = re.sub(r'\[\[(?:Category|分類|分类):[^\]]+\]\]', '', raw, flags=re.I)
    # These are source display breaks; keep one line per original paragraph.
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.I)
    return paragraphs(raw, title, 'historical_work_transcription')


def import_supplements(cache: Path) -> list[dict]:
    """Import an explicitly captured API batch; keep existing five book IDs intact."""
    indexes = json.loads((cache / 'indexes.json').read_text(encoding='utf-8'))
    pages = json.loads((cache / 'pages.json').read_text(encoding='utf-8'))
    for title in ('遁甲演義 (四庫全書本)', '六壬大全 (四庫全書本)'):
        indexes.update(json.loads((cache / (title.replace(' ', '_') + '.json')).read_text(encoding='utf-8')))
    specs = [
        ('xieji', '协纪辨方书', '欽定協紀辨方書 (四庫全書本)',
         [f'卷{i:02}' for i in range(1, 37)], '四库全书本网络转录；未逐页校图'),
        ('xuanze', '选择要略', '選擇要略', list('上中下'),
         '维基文库上中下三卷转录；具体印本未确认，朝鲜典籍'),
        ('ziwei', '紫微斗数全书', '紫微斗數全書', ['卷' + x for x in '一二三'],
         '维基文库三卷转录选本；不代表其他四卷或更多卷版本'),
        ('meihua', '梅花易数', '梅花易數', ['卷' + x for x in '一二三'],
         '维基文库三卷转录选本；不代表其他五卷版本'),
        ('liuren', '六壬大全', '六壬大全 (四庫全書本)',
         [f'卷{i:02}' for i in range(1, 13)], '四库全书本网络转录；保留该本方法与异议'),
        ('dunjia', '遁甲演义', '遁甲演義 (四庫全書本)',
         [f'卷{i}' for i in range(1, 5)], '四库全书本四卷网络转录；不同于缺卷界的普通网页本'),
    ]
    books = []
    for bid, title, source, suffixes, edition in specs:
        index = indexes[source]
        chapters = []
        for number, suffix in enumerate(suffixes, 1):
            name = source + '/' + suffix
            if name not in index['raw'] and '[[' + '/' + suffix not in index['raw']:
                raise ValueError('chapter absent from source directory: ' + name)
            page = dict(pages[name])
            page['passages'] = supplement_passages(page['raw'], suffix)
            chapters.append((f'c{number:03}', suffix, page))
        book = make_book(bid, title, edition, index, chapters)
        book['quality_notes'] = ['正文与注释未经全书逐字校勘；图表、缺字和未解析模板逐段标识。',
                                 '目录收齐不代表规则全部实现；不得据历史断语直接预测个人疾病、死亡或交易。']
        books.append(book)

    # The frozen 增删 index embeds volumes 2–4 but transcludes 31 units in volume 1.
    index = indexes['增刪卜易']
    links = re.findall(r'\[\[/([^|\]]+)\|([^\]]+)\]\]', index['raw'])
    if len(links) != 31 or len({x for x, _ in links}) != 31:
        raise ValueError('增删卷一目录变化：需要重新核对')
    chapters = []
    for number, (suffix, title) in enumerate(links, 1):
        page = dict(pages['增刪卜易/' + suffix])
        page['passages'] = supplement_passages(page['raw'], title)
        chapters.append((f'c{number:03}', title, page))
    for number, volume in enumerate('二三四', 32):
        match = re.search(r'== 增刪卜易卷之' + volume + r' ==(.*?)(?=\n== 增刪卜易卷之|\Z)', index['raw'], re.S)
        if match is None:
            raise ValueError('增删缺卷：' + volume)
        title = '卷之' + volume
        page = dict(index)
        # Keep the actual complete source revision, not fabricated raw page bytes.
        page['passages'] = supplement_passages(match.group(1), title)
        page['extraction_kind'] = 'section_of_frozen_revision_excluding_explicit_modern_notes'
        chapters.append((f'c{number:03}', title, page))
    book = make_book('zengshan', '增删卜易',
                     '维基文库四卷网络整理本；明确现代增订已排除，未标记改写仍待校', index, chapters)
    book['quality_notes'] = ['原网页录入者声明参照版本有错漏；不能标为忠实古刻。',
                            '运行正文排除录入者言、原剑增订说明及显式原剑按；原始来源档案保留供复核。',
                            '卷一31个章单元，卷二至四按整卷保存；不是仅收了34章。']
    books.append(book)
    source = '奇門遁甲元靈經'
    index = json.loads((cache / (source + '.json')).read_text(encoding='utf-8'))[source]
    # TOC and正文 have distinct headings; split only the latter.
    parts = list(re.finditer(r'(?m)^(?:==\s*)?奇门遁甲元灵经卷([一二三四五六七八九十]+)(?:\s*==)?\s*$', index['raw']))
    if len(parts) != 24 or len({m.group(1) for m in parts}) != 24:
        raise ValueError('元灵经24卷目录变化：需要重新核对')
    chapters = []
    for number, match in enumerate(parts, 1):
        end = parts[number].start() if number < len(parts) else len(index['raw'])
        title = '卷' + match.group(1)
        page = dict(index)
        page['passages'] = supplement_passages(index['raw'][match.end():end], title)
        page['extraction_kind'] = 'section_of_frozen_revision'
        chapters.append((f'c{number:03}', title, page))
    book = make_book('yuanling', '奇门遁甲元灵经', '维基文库24卷网络转录；具体印本未核', index, chapters)
    book['quality_notes'] = ['沿用已有算法规格所引revision；收录全卷不表示全书算法已经实现。']
    books.append(book)
    return books


# --------------------------------------------------------------------------- #
# 焦氏易林：四部叢刊本（逐页录入）与四库本（卷一至卷四）
# --------------------------------------------------------------------------- #

YILIN_NOTE = re.compile(r'〔注文〕(.*?)〔/注文〕', re.S)
HEX_SYMBOL = re.compile(r'[\u4dc0-\u4dff]')
GLYPH_ONLY = re.compile(r'\u3014\u5b57\u5f62[^\u3015]*\u3015')
# Ben headers carry the trigrams as a double-line note (\u4e7e\u4e0b\u3000\u574e\u4e0a); the hexagram symbol itself is
# sometimes an unencoded glyph, so the note is the reliable mark.
# Unencoded glyphs the transcription uses as zhi labels, identified where every other occurrence sits in
# that zhi's place in order (SK2989 29 times as 恆, SK3089 12 times as 晉, SK3657 once as 觀).
GLYPH_GUA = {'〔字形SK2989：未编码〕': '恆', '〔字形SK3089：未编码〕': '晉', '〔字形SK3657：未编码〕': '觀'}
TRIGRAM_NOTE = re.compile(r'\u3014\u6ce8\u6587\u3015[^\u3014]{1,4}[\u4e0a\u4e0b][\u3000 ]*[^\u3014]{1,4}[\u4e0a\u4e0b]\u3014/\u6ce8\u6587\u3015')


def clean_sbck_page(raw: str) -> str:
    """One proofread page: drop page chrome, keep words and uncertainty markers."""
    raw = re.sub(r'<noinclude>.*?</noinclude>', '', raw, flags=re.S)

    def template(match: re.Match) -> str:
        parts = [x.strip() for x in match.group(1).split('|')]
        name = parts[0]
        if name in ('Vtext2Start', 'SKQS footer'):
            return ''
        if name == '?':
            return '□'
        if name == 'SKchar' and len(parts) > 1:
            value = glyphs().get(parts[1], {})
            return value.get('character') or f"〔字形SK{parts[1]}：{value.get('description') or '未编码'}〕"
        if name == 'SKchar2' and len(parts) > 1:
            return f'〔字形SK2-{parts[1]}：未编码〕'
        if name == 'YL':
            return parts[-1]
        if name == '雙行註文':
            return '〔注文〕' + '　'.join(parts[1:]) + '〔/注文〕'
        return '〔未解析模板:' + match.group(1) + '〕'

    while re.search(r'\{\{[^{}]*\}\}', raw):
        raw = re.sub(r'\{\{([^{}]*)\}\}', template, raw)
    return html.unescape(raw)


def _sequence(ben: str) -> list[str]:
    """One ben's 64 lins in the book's order: its own lin first, then the rest in King Wen order."""
    from yilin_lookup import GUA
    return [ben] + [g for g in GUA if g != ben]


VERSE_LINE = 14


def _width(text: str) -> int:
    return len(GLYPH_ONLY.sub('X', text))


def _ends_verse(verse: list[str]) -> bool:
    """The print sets a verse fourteen characters to the line in four-character phrases: a short last line
    that completes whole phrases ends it. A page break can also leave a short line, but mid-phrase."""
    return bool(verse) and _width(verse[-1]) < VERSE_LINE and _width(''.join(verse)) % 4 == 0


# The anonymous commentary's variant readings often run on from the verse's last line: 「……亡羊失羔一本云亡羝
#失羊」. A marker that falls on a phrase boundary after at least two phrases starts the note.
INLINE_NOTE = re.compile('\u3000|一本|一云|又云|一作|末句|無註|按')


def _inline_note(verse: str) -> tuple[str, str]:
    for mark in INLINE_NOTE.finditer(verse):
        width = _width(verse[:mark.start()])
        if width >= 8 and width % 4 == 0:
            return verse[:mark.start()], verse[mark.start():].strip('\u3000')
    return verse, ''


def _note_line(indent: int, verse_indent: int | None, verse: list[str]) -> bool:
    """Indents in this transcription drift, so only a clear step marks the note: two deeper than the verse's
    first line, or a two-space line after a verse that filled its last line with whole phrases."""
    if verse_indent is None or not verse:
        return False
    full = _width(verse[-1]) == VERSE_LINE and _width(''.join(verse)) % 4 == 0
    return indent >= verse_indent + 2 or (indent >= 2 and full)


class _Ben:
    """One ben's progress: which zhi labels have been taken and the furthest position reached."""

    def __init__(self, name: str | None):
        self.name = name
        self.zhi = name
        self.pos = 0
        self.used: set[str] = {name} if name else set()

    def can_take(self, label: str, settled: bool) -> bool:
        """The next three are always taken; any other unused zhi only once the current lin's note
        has been reached, because a lone verse word never comes after the note (pages of the
        transcription are sometimes out of order, so labels can jump)."""
        if self.name is None or label in self.used:
            return False
        index = _sequence(self.name).index(label)
        return self.pos < index <= self.pos + 3 or settled

    def take(self, label: str) -> None:
        self.used.add(label)
        self.pos = max(self.pos, _sequence(self.name).index(label))  # type: ignore[arg-type]
        self.zhi = label

    def missing(self) -> list[str]:
        return [z for z in _sequence(self.name) if z not in self.used] if self.name else []


def sbck_lins(text: str, state: _Ben | None = None) -> tuple[list[dict], list[dict], _Ben]:
    """Split one volume into lins.

    A ben header is the line with the hexagram symbol or the trigram note (乾下　坎上). A line that is
    only a hexagram name (或「之某」, or an unencoded glyph where a label is due) is taken as a zhi
    label per `_Ben.can_take`; any other line is verse or note. 「之某」 marks the first label of a
    ben, so when it arrives late in a ben without a header (header page lost) the next ben in order
    is inferred. Indents are unreliable here: two or more leading spaces, or 「無註」, mark the note.
    `state` carries the open ben across volumes.
    """
    from yilin_lookup import GUA, canon
    passages: list[dict] = []
    problems: list[dict] = []
    ben = state or _Ben(None)
    verse: list[str] = []
    notes: list[str] = []
    # The current lin's attribution note (when its label was inferred) and the indent of its label line:
    # some pages are shifted one space right, and the verse/note split is relative to the label.
    attribution: list[dict | None] = [None]
    verse_indent: list[int | None] = [None]
    note_indent = [2]

    def flush() -> None:
        if ben.name and ben.zhi and verse:
            section = f'{ben.name}之{ben.zhi}'
            text, inline = _inline_note(''.join(verse))
            passage: dict = {'section': section, 'text': text, 'layer': 'base_text'}
            if attribution[0]:
                passage['attribution'] = attribution[0]
            passages.append(passage)
            note = ''.join(n for n in [inline, *notes] if n and n != '無註')
            if note:
                passages.append({'section': section, 'text': note, 'layer': 'commentary'})
        verse.clear()
        notes.clear()

    def close(current: _Ben) -> None:
        problems.extend({'section': f'{current.name}之{z}', 'kind': 'lin_missing_in_transcription'}
                        for z in current.missing())

    for line in text.split('\n'):
        body = line.strip('\u3000 ')
        if not body:
            continue
        indent = len(line) - len(line.lstrip('\u3000 '))
        if indent == 0 and body.startswith('易林卷'):
            continue
        if indent == 0 and (HEX_SYMBOL.search(body) or TRIGRAM_NOTE.search(body)):
            flush()
            named = canon(GLYPH_ONLY.sub('', YILIN_NOTE.sub('', HEX_SYMBOL.sub('', body))))
            if named is None:
                problems.append({'line': body, 'kind': 'ben_unparsed'})
            if ben.name:
                close(ben)
            ben = _Ben(named)
            attribution[0], verse_indent[0] = None, None
            continue
        # A label is never deeper than the current lin's verse; a lone name at note depth (「見需之／兊」)
        # continues the note.
        if verse_indent[0] is None:
            depth = 1
        elif notes:
            # After the note has begun a label sits shallower than the note (「　節」 after a two-space note),
            # while a lone name at the note's own depth continues it.
            depth = min(max(verse_indent[0], 1), note_indent[0] - 1)
        else:
            depth = min(1, verse_indent[0])
        label_depth = indent <= depth
        label = canon(body[1:] if body.startswith('之') else body) if label_depth else None
        if label is None and label_depth and GLYPH_ONLY.fullmatch(body):
            label = GLYPH_GUA.get(body)
        settled = bool(notes)
        if body.startswith('之') and label and ben.name and ben.pos >= 40 and GUA.index(ben.name) + 1 < len(GUA):
            following = GUA[GUA.index(ben.name) + 1]
            if label == _sequence(following)[1]:
                flush()
                close(ben)
                problems.append({'kind': 'ben_inferred_missing_header', 'ben': following,
                                 'after': f'{ben.name}之{ben.zhi}'})
                ben = _Ben(following)
                ben.take(label)
                attribution[0], verse_indent[0] = None, None
                continue
        if ben.name and settled and label_depth and (label in ben.used or (label is None and GLYPH_ONLY.fullmatch(body))):
            # The page names a zhi already taken (pages out of order) or an unknown glyph. The lin is kept, but
            # under an unplaced section: order alone does not prove which zhi it belongs to (R1-YILIN-04).
            flush()
            would = next((z for z in _sequence(ben.name)[ben.pos + 1:] if z not in ben.used), None)
            conflict = {'label_on_page': body, 'label_reads_as': label, 'order_would_give': would,
                        'note': (f"原页这里的标题是「{body}」" + (f"，读作{label}，但本卦的{label}林已在前面" if label else '（未编码字形）')
                                 + f"；按卦序该是{would}，但页序错乱，归属未定")}
            attribution[0] = conflict
            problems.append({'ben': ben.name, 'kind': 'lin_unplaced_label_conflicts_with_order', **conflict})
            from yilin_lookup import UNPLACED
            ben.zhi = UNPLACED
            verse_indent[0] = None
            continue
        if label and ben.can_take(label, settled):
            flush()
            ben.take(label)
            attribution[0] = None
            verse_indent[0] = None
            continue
        if verse_indent[0] is None and body != '無註' and not verse and not notes:
            verse_indent[0] = indent
        if body == '無註' or settled or _ends_verse(verse) or _note_line(indent, verse_indent[0], verse):
            if not notes:
                note_indent[0] = indent
            notes.append(body)
        else:
            verse.append(body)
    flush()
    return passages, problems, ben


SIKU_EXTRACTION_VERSION = 'siku-heading-spans-2'


def _siku_text(text: str) -> str:
    return re.sub(r'[ \t\r\n]+', '', text).strip('\u3000')


def siku_lins(text: str) -> tuple[list[dict], list[dict]]:
    """四库本 runs entries together: 「小畜　……並居履　空拳……」. 「X之第N」 starts a ben; a hexagram
    name followed by a full-width space starts a zhi only when it is one of the next three in that ben's
    order (or one passed over), because a verse can end on a hexagram character — 「……安泰　」 must not
    cut 泰 off the verse (R1-YILIN-01)."""
    from yilin_lookup import GUA, SOURCE_SPELLINGS, canon
    names = sorted(set(GUA) | SOURCE_SPELLINGS, key=len, reverse=True)
    token = re.compile(r'(?P<head>(' + '|'.join(map(re.escape, names)) + r')之第[一二三四五六七八九十]+)'
                       r'|(?P<zhi>' + '|'.join(map(re.escape, names)) + r')\u3000')
    passages: list[dict] = []
    problems: list[dict] = []
    # Mask wiki headings without shifting clean_wiki's character coordinates.
    source = re.sub(r'==[^=]*卷[一二三四五六七八九十]+[ \t\r\n\u3000]*==|==',
                    lambda match: ' ' * len(match.group()), text)
    ben = _Ben(None)
    body_from: int | None = None
    heading_span: list[int] | None = None
    pending_from = 0
    siku_attribution: list[dict | None] = [None]

    def close(upto: int) -> None:
        if ben.name is None or ben.zhi is None or body_from is None:
            return
        body = source[body_from:upto]
        section = f'{ben.name}之{ben.zhi}'
        notes = '；'.join(_siku_text(note) for note in YILIN_NOTE.findall(body))
        verse = _siku_text(YILIN_NOTE.sub('', body))
        span = {'basis': 'clean_wiki_onlyinclude_codepoints', 'start': body_from, 'end': upto}
        if not verse:
            problems.append({'section': section, 'kind': 'verse_missing_in_transcription',
                             'source_span': span})
            return
        passage: dict = {'section': section, 'text': verse, 'layer': 'base_text',
                         'source_span': span, 'source_heading_span': heading_span}
        if siku_attribution[0]:
            passage['attribution'] = siku_attribution[0]
        passages.append(passage)
        if notes:
            passages.append({'section': section, 'text': notes, 'layer': 'commentary',
                             'source_span': span})

    def unclassified(start: int, end: int) -> None:
        if source[start:end].strip():
            problems.append({'kind': 'unclassified_source_text', 'text': source[start:end],
                             'source_span': {'basis': 'clean_wiki_onlyinclude_codepoints',
                                             'start': start, 'end': end}})

    marks = list(token.finditer(source))
    for i, match in enumerate(marks):
        if match.group('head'):
            close(match.start())
            if body_from is None:
                unclassified(pending_from, match.start())
            if ben.name:
                problems.extend({'section': f'{ben.name}之{z}', 'kind': 'lin_missing_in_transcription'}
                                for z in ben.missing())
            ben, body_from = _Ben(canon(match.group(2))), None
            ben.zhi = None
            pending_from = match.end()
            continue
        zhi = canon(match.group('zhi'))
        if zhi is None or ben.name is None:
            continue
        first = body_from is None and zhi == ben.name
        mislabel = None
        if not first and not ben.can_take(zhi, settled=False):
            # Out of order. A hexagram character ending a verse is followed straight by the next label
            # (「……安泰　遯　」); a mislabeled lin (「小過」 where 小畜 is due) is followed by a whole verse.
            following = marks[i + 1].start() if i + 1 < len(marks) else len(source)
            due = next((z for z in _sequence(ben.name)[ben.pos + 1:ben.pos + 2] if z not in ben.used), None)
            if zhi in ben.used or due is None or len(_siku_text(YILIN_NOTE.sub('', source[match.end():following]))) < 8:
                continue
            mislabel = {'label_on_page': match.group('zhi'), 'label_reads_as': zhi, 'attributed_by_order': due,
                        'note': (f"原页这里的标题是「{match.group('zhi')}」，但位置正是{due}该在处，{zhi}林另在本卦后面；"
                                 f"按卦序推定归{due}，原本标题与位置不合")}
            problems.append({'section': f'{ben.name}之{due}', 'kind': 'attribution_inferred_from_order', **mislabel})
            zhi = due
        close(match.start())
        if first:
            unclassified(pending_from, match.start())
            ben.zhi = zhi
        else:
            ben.take(zhi)
        siku_attribution[0] = mislabel
        body_from = match.end()
        heading_span = [match.start(), match.end()]
    close(len(source))
    if body_from is None:
        unclassified(pending_from, len(source))
    if ben.name:
        problems.extend({'section': f'{ben.name}之{z}', 'kind': 'lin_missing_in_transcription'} for z in ben.missing())
    return passages, problems


def rebuild_yilin_siku(source: Path, destination: Path) -> dict:
    """Rebuild only this edition from its frozen source files, without retrieval."""
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    book = next(b for b in manifest['books'] if b['id'] == 'yilin_siku')
    all_passages: list[dict] = []
    all_problems: list[dict] = []
    for entry in book['chapters']:
        if entry['id'] == 'c000':
            continue
        chapter = json.loads((source / entry['path']).read_text(encoding='utf-8'))
        raw_bytes = (source / chapter['raw_path']).read_bytes()
        if digest(raw_bytes) != chapter['raw_sha256']:
            raise ValueError(f"frozen raw hash mismatch: {chapter['raw_path']}")
        raw = raw_bytes.decode('utf-8')
        body = '\n'.join(re.findall(r'<onlyinclude>(.*?)</onlyinclude>', raw, re.S)) or raw
        passages, problems = siku_lins(clean_wiki(body))
        for position, item in enumerate(passages, 1):
            item.update({'passage_id': f"yilin_siku:{chapter['chapter_id']}:p{position:04}",
                         'sha256': digest(item['text'].encode('utf-8'))})
        chapter['passages'] = passages
        chapter['extraction_version'] = SIKU_EXTRACTION_VERSION
        entry['sha256'] = write_json(destination / entry['path'], chapter)
        entry['passage_count'] = len(passages)
        all_passages.extend(passages)
        all_problems.extend(dict(problem, chapter_id=chapter['chapter_id']) for problem in problems)
    from yilin_lookup import GUA
    book['completeness']['lins'] = _completeness(all_passages, list(GUA))
    book['split_problems'] = all_problems
    book['extraction_version'] = SIKU_EXTRACTION_VERSION
    write_json(destination / 'manifest.json', manifest)
    return book


def _completeness(passages: list[dict], bens: list[str]) -> dict:
    from yilin_lookup import GUA
    pairs = {f'{b}之{z}' for b in bens for z in GUA}
    have = {p['section'] for p in passages if p['layer'] == 'base_text'} & pairs
    missing = [f'{b}之{z}' for b in bens for z in GUA if f'{b}之{z}' not in have]
    return {'expected_lins': 64 * len(bens), 'found_lins': len(have), 'missing': missing}


def import_yilin(cache: Path) -> list[dict]:
    from yilin_lookup import GUA
    heads = json.loads((cache / 'sbck_heads.json').read_text(encoding='utf-8'))
    plan = json.loads((cache / 'sbck_plan.json').read_text(encoding='utf-8'))
    pages = json.loads((cache / 'sbck_pages.json').read_text(encoding='utf-8'))
    source = '焦氏易林 (四部叢刊本)'
    index = dict(heads[source])
    chapters = []
    order = ['序'] + [v for v in plan if v != '序']
    state: _Ben | None = None
    for number, volume in enumerate(order):
        names = [name for span in plan[volume] for name in span['pages']]
        revisions = [{'title': n, 'revision': pages[n]['revision'], 'raw': pages[n]['raw']} for n in names]
        text = '\n'.join(clean_sbck_page(r['raw']) for r in revisions)
        page = dict(heads[f'{source}/{volume}'])
        page.update({'raw': json.dumps(revisions, ensure_ascii=False), 'format': 'json',
                     'raw_kind': 'proofread_page_revisions_for_this_volume',
                     'extraction_kind': 'volume_assembled_from_frozen_page_revisions'})
        if volume == '序':
            page['passages'] = paragraphs(text, volume, 'paratext')
        else:
            page['passages'], page['split_problems'], state = sbck_lins(text, state)
        chapters.append((f'c{number:03}', volume, page))
    sbck = make_book('yilin', '焦氏易林', '四部叢刊景北京圖書館藏元刊本，十六卷附闕名注；维基文库逐页录入，校对等级多为1（未校对）',
                     index, chapters)
    lins = [p for _, _, page in chapters[1:] for p in page['passages']]
    sbck['completeness']['lins'] = _completeness(lins, list(GUA))
    sbck['split_problems'] = [x for _, _, page in chapters[1:] for x in page.get('split_problems', [])]
    sbck['quality_notes'] = ['维基文库四部叢刊扫描页校对等级：2329页为1（未校对）、3页为3、4页为空白；文本未经本项目对图校核。',
                             '「無註」标记不收为注文段；□为原录入标记的不可辨字。',
                             '每林按本卦、之卦切分；版本缺页或切分不出的林列在 completeness.lins.missing。']

    siku = json.loads((cache / 'siku.json').read_text(encoding='utf-8'))
    sindex = dict(siku['易林 (四庫全書本)'])
    sindex['passages'] = supplement_passages(sindex['raw'], '提要')
    schapters = [('c000', '提要', sindex)]
    for i in range(1, 5):
        page = dict(siku[f'易林 (四庫全書本)/卷{i}'])
        body = page['raw']
        if '<onlyinclude>' in body:
            body = '\n'.join(re.findall(r'<onlyinclude>(.*?)</onlyinclude>', body, re.S))
        text = clean_wiki(body.replace('{{SK notes|', '{{sk notes|'))
        page['passages'], page['split_problems'] = siku_lins(text)
        page['extraction_version'] = SIKU_EXTRACTION_VERSION
        schapters.append((f'c{i:03}', f'卷{i}', page))
    sk = make_book('yilin_siku', '焦氏易林（四库本）', '文淵閣四庫全書本，维基文库分四卷录入，六十四卦齐全；未逐页校图',
                   sindex, schapters)
    slins = [p for _, _, page in schapters[1:] for p in page['passages']]
    sk['completeness']['lins'] = _completeness(slins, list(GUA))
    sk['split_problems'] = [dict(x, chapter_id=cid) for cid, _, page in schapters[1:]
                            for x in page.get('split_problems', [])]
    sk['extraction_version'] = SIKU_EXTRACTION_VERSION
    sk['quality_notes'] = ['维基文库把全书分四卷录入，六十四卦都在；个别林转录缺失，见 completeness.lins.missing。',
                           '四库本录文把多林连写，按「卦名＋全角空格」切分。']
    return [sbck, sk]


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, epilog='Top-level JSON keys: books')
    parser.add_argument('--wikisource', action='store_true')
    parser.add_argument('--capture-qiongtong', action='store_true')
    parser.add_argument('--captured-html', choices=['ziping', 'qiongtong', 'yuanhai'], action='append', default=[])
    parser.add_argument('--supplements-from', type=Path, help='显式导入已捕获的补充书目 API 批次')
    parser.add_argument('--yilin-from', type=Path, help='显式导入已捕获的焦氏易林两版本 API 批次')
    parser.add_argument('--yilin-siku-frozen-from', type=Path,
                        help='仅从指定 knowledge 目录的冻结四库 raw 重建；核对原始哈希，不联网')
    parser.add_argument('--output-dir', type=Path,
                        help='四库冻结重建的独立输出目录；与 --yilin-siku-frozen-from 同用')
    args = parser.parse_args()
    if (ROOT / 'books.zip').is_file() or (ROOT.parents[2] / 'corpus' / 'sources.zip').is_file() \
            or (ROOT / 'sources.zip').is_file():
        # Writing loose files beside the archives would leave two diverging copies of the corpus.
        parser.error('语料是打包状态：先运行 python scripts/corpus_archive.py unpack，导入并审核后再 pack')
    if args.yilin_siku_frozen_from:
        if not args.output_dir or any((args.wikisource, args.capture_qiongtong, args.captured_html,
                                       args.supplements_from, args.yilin_from)):
            parser.error('frozen siku rebuild requires --output-dir and cannot mix other imports')
        if args.output_dir.resolve() == args.yilin_siku_frozen_from.resolve():
            parser.error('frozen siku rebuild requires a separate output directory for review')
        book = rebuild_yilin_siku(args.yilin_siku_frozen_from, args.output_dir)
        print(json.dumps({'books': [(book['id'], len(book['chapters']))]}, ensure_ascii=False))
        return 0
    if args.output_dir:
        parser.error('--output-dir requires --yilin-siku-frozen-from')
    if not (args.wikisource or args.capture_qiongtong or args.captured_html or args.supplements_from
            or args.yilin_from):
        parser.error('choose a retrieval/import operation')
    if args.capture_qiongtong:
        capture_qiongtong()
    books = import_wikisource() if args.wikisource else []
    books += [import_captured_html(book_id) for book_id in args.captured_html]
    if args.supplements_from:
        supplements = import_supplements(args.supplements_from)
        for book in supplements:
            book['retrieval_context_radius'] = 2
        books += supplements
    if args.yilin_from:
        books += import_yilin(args.yilin_from)
    manifest_path = ROOT / 'manifest.json'
    existing = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    replaced = {book['id'] for book in books}
    books += [b for b in existing.get('books', []) if b['id'] not in replaced]
    manifest = {'schema_version': '2.0', 'distribution_kind': 'source',
                'library_id': 'chinese-classics-v2' if args.supplements_from else existing.get('library_id', 'bazi-five-classics-v1'),
                'required_books': sorted({'ziping', 'ditian', 'qiongtong', 'sanming', 'yuanhai'} | {b['id'] for b in books}),
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
