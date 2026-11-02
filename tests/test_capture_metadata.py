"""Source provenance survives installers that omit files named metadata.json."""
import hashlib
import json
import shutil

import import_classics as importer
from classical_search import validate_library


def test_capture_import_keeps_provenance_through_installer_basename_filter(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    directory = source / 'sources/ziping'
    directory.mkdir(parents=True)
    raw = '<article>八字用神，專求月令。</article>\n'
    (directory / '001.html').write_text(raw, encoding='utf-8')
    (directory / 'directory.html').write_text('<ol>一卷</ol>\n', encoding='utf-8')
    metadata = {'book': '虚构来源边界夹具', 'edition': 'test', 'retrieved_at': '2026-01-01T00:00:00Z',
                'source_url': 'https://example.invalid/frozen', 'licensing': 'test fixture',
                'editorial_policy': 'literal source fixture', 'expected_chapters': 1,
                'chapters': [{'chapter_id': '1', 'title': '夹具', 'status': 'captured', 'file': '001.html',
                              'html_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
                              'source_url': 'https://example.invalid/chapter',
                              'retrieved_at': '2026-01-01T00:00:00Z'}]}
    (directory / 'capture-metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    monkeypatch.setattr(importer, 'ROOT', source)
    book = importer.import_captured_html('ziping')
    manifest = {'schema_version': '2.0', 'distribution_kind': 'source',
                'required_books': ['ziping'], 'books': [book]}
    (source / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    installed = tmp_path / 'installed'
    shutil.copytree(source, installed, ignore=shutil.ignore_patterns('metadata.json'))
    assert validate_library(installed)['ok'] is True
    assert book['source_metadata_path'] == 'sources/ziping/capture-metadata.json'
    retained = installed / book['source_metadata_path']
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == book['source_metadata_sha256']
    retained.unlink()
    failed = validate_library(installed)
    assert failed['ok'] is False and any('capture-metadata.json' in error for error in failed['errors'])
