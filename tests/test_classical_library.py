"""Verify real retrieval and fail-closed integrity/completeness boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from classical_search import (
    get_passage,
    get_witnesses,
    normalized,
    search_classics,
    validate_library,
)
from import_classics import clean_wiki, html_paragraphs


def _write(path: Path, value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def mini_library(tmp_path: Path) -> Path:
    (tmp_path / 'source.txt').write_text('原始来源', encoding='utf-8')
    raw_sha = hashlib.sha256((tmp_path / 'source.txt').read_bytes()).hexdigest()
    passage = {'passage_id': 'ziping:c008:p0001', 'text': '八字用神，專求月令。',
               'section': '论用神', 'layer': 'base_text',
               'sha256': hashlib.sha256('八字用神，專求月令。'.encode()).hexdigest()}
    chapter = {'book_id': 'ziping', 'chapter_id': 'c008', 'title': '论用神',
               'source_url': 'https://example.invalid/frozen', 'revision': 'test-revision',
               'facsimile_status': 'not_checked', 'transcription_status': 'acquired_not_collated',
               'raw_path': 'source.txt', 'raw_sha256': raw_sha, 'passages': [passage]}
    sha = _write(tmp_path / 'chapter.json', chapter)
    book = {'id': 'ziping', 'title': '子平真诠', 'edition': 'test fixture',
            'license': {'original': 'test'}, 'expected_chapters': ['c008'],
            'source_flags': [], 'index_path': 'source.txt', 'index_sha256': raw_sha,
            'facsimile_status': 'not_checked', 'transcription_status': 'acquired_not_collated',
            'completeness': {'acquisition': 'complete', 'missing_facsimile_pages': 'not_assessed'},
            'chapters': [{'id': 'c008', 'title': '论用神', 'path': 'chapter.json',
                          'sha256': sha, 'passage_count': 1}]}
    _write(tmp_path / 'manifest.json', {'schema_version': '2.0', 'distribution_kind': 'source', 'required_books': ['ziping'], 'books': [book]})
    return tmp_path


def test_acquisition_does_not_imply_image_collation(mini_library: Path) -> None:
    result = validate_library(mini_library)
    assert result['ok'] and result['books'][0]['complete_acquisition']
    assert result['books'][0]['facsimile_verified'] is False


@pytest.mark.parametrize('damage', ['missing_chapter', 'bad_hash', 'missing_inventory', 'missing_page', 'declared_missing_chapter', 'source_gap'])
def test_missing_or_damaged_material_cannot_claim_complete(mini_library: Path, damage: str) -> None:
    manifest_path = mini_library / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if damage == 'missing_chapter':
        (mini_library / 'chapter.json').unlink()
    elif damage == 'bad_hash':
        (mini_library / 'chapter.json').write_text('{}', encoding='utf-8')
    elif damage == 'missing_inventory':
        manifest['books'][0]['expected_chapters'].append('c009')
    elif damage == 'missing_page':
        manifest['books'][0]['completeness']['missing_facsimile_pages'] = [3]
    elif damage == 'declared_missing_chapter':
        manifest['books'][0]['completeness']['missing_chapters'] = ['unknown-original-leaf']
    else:
        manifest['books'][0]['source_flags'] = ['source is incomplete']
    _write(manifest_path, manifest)
    result = validate_library(mini_library)
    assert result['ok'] is False
    assert result['errors']
    assert not result['books'] or not result['books'][0]['complete_acquisition']


def test_text_mutation_cannot_be_searched_as_frozen_original(mini_library: Path) -> None:
    path = mini_library / 'chapter.json'
    chapter = json.loads(path.read_text(encoding='utf-8'))
    chapter['passages'][0]['text'] = '伪造内容'
    _write(path, chapter)
    with pytest.raises(ValueError, match='hash mismatch'):
        search_classics('伪造', library_root=mini_library)


def test_simplified_query_preserves_original_text_and_attribution(mini_library: Path) -> None:
    result = search_classics('专求月令', book='子平真詮', library_root=mini_library)
    assert result[0]['text'] == '八字用神，專求月令。'
    assert result[0]['source_url'] and result[0]['revision']
    assert result[0]['context'][0]['passage_id'] == result[0]['passage_id']


def test_common_technical_aliases() -> None:
    assert normalized('傷官 調候 成敗救應 財官 氣候') == normalized('伤官 调候 成败救应 财官 气候')


def test_image_witness_lookup_preserves_default_edition_status() -> None:
    before = get_passage('ziping:c031:p0004')['facsimile_status']
    result = get_witnesses()
    assert len(result['records']) == 5
    assert result['default_corpus_status_changed'] is False
    assert all(e['default_corpus_same_edition'] is False for e in result['editions'])
    selected = get_witnesses('ziping:c031:p0004')
    assert selected['records'][0]['comparison'] == 'variant_recorded_no_emendation'
    assert get_passage('ziping:c031:p0004')['facsimile_status'] == before
    assert get_witnesses('ziping:c031:p0001')['records'] == []
    with pytest.raises(ValueError):
        get_witnesses('ziping:c000:p0000')


def test_source_glyph_mapping_never_guesses_unencoded_characters() -> None:
    assert clean_wiki('{{SKchar|269}}') == '𣷉'
    assert clean_wiki('{{SKchar|2636}}') == '〔字形SK2636：未编码〕'


def test_supporting_source_hash_is_checked(mini_library: Path) -> None:
    path = mini_library / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['supporting_sources'] = [{'path': 'source.txt', 'sha256': 'wrong'}]
    _write(path, manifest)
    assert validate_library(mini_library)['ok'] is False


def test_unknown_book_passage_and_invalid_limit_are_explicit(mini_library: Path) -> None:
    with pytest.raises(ValueError, match='unknown book'):
        search_classics('用神', book='not-a-book', library_root=mini_library)
    with pytest.raises(ValueError, match='unknown passage'):
        get_passage('ziping:c008:p9999', mini_library)
    with pytest.raises(ValueError, match='limit'):
        search_classics('用神', limit=0, library_root=mini_library)


def test_path_escape_is_rejected(mini_library: Path) -> None:
    path = mini_library / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['books'][0]['chapters'][0]['path'] = '../outside.json'
    _write(path, manifest)
    assert validate_library(mini_library)['ok'] is False


def test_actual_five_classics_have_frozen_source_complete_inventories() -> None:
    result = validate_library()
    assert result['ok'], result['errors']
    assert {b['id'] for b in result['books']} == {'ziping', 'ditian', 'qiongtong', 'sanming', 'yuanhai'}
    assert all(b['complete_acquisition'] and not b['facsimile_verified'] for b in result['books'])
    assert all(b['passages'] > 20 for b in result['books'])
    counts = {b['id']: b['chapters'] for b in result['books']}
    assert counts['ditian'] == 42 and counts['sanming'] == 13 and counts['yuanhai'] == 304
    assert counts['qiongtong'] == 6 and counts['ziping'] >= 47


def test_real_original_and_commentary_have_separate_stable_ids() -> None:
    original = get_passage('ditian:c006:p0007')
    commentary = get_passage('ditian:c006:p0008')
    assert original['text'] == '傷官見官果難辨，可見不可見。'
    assert original['layer'] == 'base_text'
    assert commentary['layer'] == 'commentary'
    assert '身弱而傷官旺' in commentary['text']
    assert original['revision'] == commentary['revision'] == '844363'


def test_real_ziping_query_returns_whole_paragraph_not_isolated_verdict() -> None:
    found = search_classics('专求月令', book='子平真诠', chapter='用神')
    assert found
    assert any('順用' in row['text'] and '逆用' in row['text'] for row in found)
    assert all(row['context'] for row in found)


def test_exact_chapter_and_body_rank_ahead_of_wordy_prefaces() -> None:
    result = search_classics('用神', book='ziping', limit=2)
    assert result[0]['passage_id'] == 'ziping:c008:p0001'
    assert all(row['layer'] == 'base_text' for row in result)
    assert get_passage('ziping:c048:p0001')['layer'] == 'paratext'


def test_query_matches_chapter_title_even_when_opening_paragraph_uses_different_words() -> None:
    result = search_classics('用神成败救应', book='ziping', limit=1)
    assert result[0]['passage_id'] == 'ziping:c009:p0001'
    assert search_classics('用神变化', book='ziping', limit=1)[0]['chapter_id'] == 'c010'


def test_real_yuanhai_marginal_notes_are_not_original_text() -> None:
    note = get_passage('yuanhai:c096:p0005')
    mixed = get_passage('yuanhai:c111:p0007')
    original = get_passage('yuanhai:c096:p0003')
    assert note['text'].startswith('眉批：')
    assert note['layer'] == 'historical_commentary'
    assert mixed['layer'] == 'historical_work_transcription_with_commentary'
    span = mixed['commentary_spans'][0]
    assert mixed['text'][span['start']:span['end']].startswith('(眉批：')
    assert span['boundary_closed']
    assert original['text'] == '夫金神者，只有三时，癸酉、己巳、乙丑。'
    assert original['layer'] == 'historical_work_transcription'
    assert note['context'][0]['layer'] == 'historical_work_transcription'


def test_open_note_does_not_guess_the_layer_of_later_paragraphs() -> None:
    paragraphs = html_paragraphs('<p>古文。(眉批：注语未闭</p><p>后段层次待校。</p>',
                                 '测试章', 'historical_work_transcription')
    assert paragraphs[0]['layer'] == 'historical_work_transcription_with_commentary'
    assert paragraphs[0]['layer_status'] == 'explicit_marker_open_boundary'
    assert paragraphs[1]['layer'] == 'historical_work_transcription'


@pytest.mark.parametrize("damage", ["raw_missing", "schema_missing", "kind_missing", "kind_unknown"])
def test_source_mode_never_falls_back_when_raw_sources_are_absent(mini_library, damage):
    path = mini_library / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if damage == "raw_missing":
        (mini_library / "source.txt").unlink()
    elif damage == "schema_missing":
        del manifest["schema_version"]
    elif damage == "kind_missing":
        del manifest["distribution_kind"]
    else:
        manifest["distribution_kind"] = "auto"
    _write(path, manifest)
    assert not validate_library(mini_library)["ok"]
