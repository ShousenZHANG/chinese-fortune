"""Check complete source retrieval, scope and reproducibility of added materials."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import classical_guidance as guidance
import import_classics as importer
import pytest
from classical_search import get_chapter, get_passage, search_classics, validate_library
from fortune_rules import SCENARIOS, research_request

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'xieji': 36, 'xuanze': 3, 'ziwei': 3, 'meihua': 3,
            'liuren': 12, 'dunjia': 4, 'zengshan': 34, 'yuanling': 24}


def test_new_inventory_and_every_scenario_route_are_real() -> None:
    report = validate_library()
    assert report['ok'], report['errors']
    assert {b['id']: b['chapters'] for b in report['books'] if b['id'] in EXPECTED} == EXPECTED
    assert sum(b['passages'] for b in report['books']) == 18982
    assert guidance.audit_guidance()['ok']
    assert set(guidance._catalog()['scenarios']) == set(SCENARIOS)
    for scenario in SCENARIOS:
        plan = research_request(scenario, 'hour')['classical_research']
        assert scenario in plan['command']
        assert plan['personal_ranking'] == 'not_certified_by_source_inventory'


def test_exam_search_keeps_both_permission_and_prohibition() -> None:
    result = search_classics('赴举', book='xuanze', limit=1)[0]
    assert result['passage_id'] == 'xuanze:c003:p0022'
    context = {p['passage_id']: p['text'] for p in result['context']}
    assert context['xuanze:c003:p0023'].startswith('宜')
    assert context['xuanze:c003:p0024'].startswith('忌')
    assert result['chapter_locator'] == 'xuanze:c003'
    assert result['quality_notes']


def test_pagination_keeps_later_exception_and_never_claims_first_page_complete() -> None:
    first = get_chapter('ziping:c026', limit=2)
    assert first['next_offset'] == 2 and not first['chapter_complete_in_this_response']
    middle = get_chapter('ziping:c026', offset=2, limit=2)
    last = get_chapter('ziping:c026', offset=4, limit=2)
    assert '不忌' in last['results'][0]['text']
    assert last['next_offset'] is None and not last['chapter_complete_in_this_response']
    all_ids = [p['passage_id'] for r in (first, middle, last) for p in r['results']]
    assert all_ids == [f'ziping:c026:p{i:04}' for i in range(1, 7)]
    assert get_chapter('ziping:c026', limit=10)['chapter_complete_in_this_response']


@pytest.mark.parametrize('chapter,offset,limit', [('bad', 0, 5), ('ziping:missing', 0, 5),
    ('ziping:c026', -1, 5), ('ziping:c026', 1000, 5), ('ziping:c026', 0, 21)])
def test_bad_chapter_requests_are_not_silently_truncated(chapter: str, offset: int, limit: int) -> None:
    with pytest.raises(ValueError):
        get_chapter(chapter, offset=offset, limit=limit)


@pytest.mark.parametrize('family', ['正官', '财', '印', '食神', '七杀', '伤官', '阳刃', '禄劫'])
def test_each_family_returns_complete_exceptions_without_claiming_personal_match(family: str) -> None:
    result = guidance.luck_family(family)
    assert result['status'] == 'requires_personal_condition_review'
    assert len(result['evidence']) == len(result['passage_hashes'])
    assert '不自动扩展' in result['temporal_scope']
    assert result['condition_checklist'] and result['plain_meaning']
    assert all(source['source_url'] for source in result['evidence'])


def test_later_exception_and_personal_year_scope_remain_visible() -> None:
    result = guidance.luck_family('印')
    assert '印輕者' in result['evidence'][-1]['text']
    plan = guidance.research_plan('interview')
    assert '分开' in plan['boundary']
    assert guidance.research_plan('naming')['source_status'] == 'separate_sources_or_records_required'
    assert '本命行年' in get_passage('dunjia:c001:p0016')['text']
    interview = guidance.research_sources('interview', limit=1)
    arrival = next(g for g in interview['groups'] if g['book'] == 'xuanze')['results'][0]
    assert arrival['passage_id'] == 'xuanze:c003:p0003'
    assert any('前二條俱忌' in p['text'] for p in arrival['context'])


def test_source_change_cannot_keep_reviewed_family_status(monkeypatch: pytest.MonkeyPatch) -> None:
    data = guidance._catalog()
    data['luck_families']['印']['passage_hashes']['ziping:c036:p0009'] = '0' * 64
    monkeypatch.setattr(guidance, '_catalog', lambda: data)
    with pytest.raises(ValueError, match='版本变化'):
        guidance.luck_family('印')
    assert not guidance.audit_guidance()['ok']


def test_extractor_preserves_unknowns_and_separates_explicit_modern_notes() -> None:
    rows = importer.supplement_passages(
        '<onlyinclude>古文{{*|古注}}\n\n{{*|原劍按：现代补写。}}\n\n{{未知|缺字}}\n\n-{乾}-</onlyinclude>', '章')
    text = '\n'.join(row['text'] for row in rows)
    assert '古注' in text and '〔注文〕' in text
    assert '现代补写' not in text and '未解析模板' in text and '乾' in text


def test_frozen_source_archive_can_rebuild_added_chapters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reconstruct API capture from tracked provenance, with no network/cache dependency."""
    manifest = json.loads((ROOT / 'knowledge/manifest.json').read_text(encoding='utf-8'))
    indexes, pages = {}, {}
    for book in manifest['books']:
        if book['id'] not in EXPECTED:
            continue
        title = parse_qs(urlsplit(book['source_url']).query)['title'][0]
        indexes[title] = {'title': title, 'revision': book['revision'], 'timestamp': book['source_timestamp'],
                          'raw': (ROOT / 'knowledge' / book['index_path']).read_text(encoding='utf-8')}
        for row in book['chapters']:
            ch = json.loads((ROOT / 'knowledge' / row['path']).read_text(encoding='utf-8'))
            page_title = parse_qs(urlsplit(ch['source_url']).query)['title'][0]
            pages[page_title] = {'title': page_title, 'revision': ch['revision'], 'timestamp': ch['source_timestamp'],
                                'raw': (ROOT / 'knowledge' / ch['raw_path']).read_text(encoding='utf-8')}
    (tmp_path / 'indexes.json').write_text(json.dumps(indexes, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'pages.json').write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
    for title in ['遁甲演義 (四庫全書本)', '六壬大全 (四庫全書本)', '奇門遁甲元靈經']:
        (tmp_path / (title.replace(' ', '_') + '.json')).write_text(
            json.dumps({title: indexes[title]}, ensure_ascii=False), encoding='utf-8')
    # Keep the same frozen glyph map, then write only into a temporary library.
    glyph_map = importer.glyphs()
    monkeypatch.setattr(importer, 'glyphs', lambda: glyph_map)
    monkeypatch.setattr(importer, 'ROOT', tmp_path / 'rebuilt')
    books = importer.import_supplements(tmp_path)
    assert {b['id']: len(b['chapters']) for b in books} == EXPECTED
    for book in books:
        for chapter in book['chapters']:
            assert (tmp_path / 'rebuilt' / chapter['path']).read_bytes() == (ROOT / 'knowledge' / chapter['path']).read_bytes()


def test_cli_errors_are_machine_readable(capsys: pytest.CaptureFixture) -> None:
    assert guidance.main(['--family', '不存在']) == 1
    assert json.loads(capsys.readouterr().out)['ok'] is False
    assert guidance.main(['--scenario', 'interview', '--retrieve', '--limit', '4']) == 1
    assert json.loads(capsys.readouterr().out)['ok'] is False
