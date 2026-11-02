"""焦氏易林两版本：从冻结原始修订重切分可复现、查林两本并列、卦名简繁通用。"""
import json
import re
from pathlib import Path

import import_classics as importer
import pytest
from conftest import run_cli
from yilin_lookup import GUA, canon, lin

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / 'skills/chinese-fortune/knowledge'


def _chapter(book: str, cid: str) -> dict:
    return json.loads((KNOWLEDGE / 'books' / book / f'{cid}.json').read_text(encoding='utf-8'))


def _strip(passages: list[dict]) -> list[tuple]:
    return [(p['section'], p['text'], p['layer']) for p in passages]


def test_sbck_volumes_resplit_from_the_frozen_page_revisions():
    state = None
    for i in range(1, 17):
        chapter = _chapter('yilin', f'c{i:03}')
        revisions = json.loads((KNOWLEDGE / chapter['raw_path']).read_text(encoding='utf-8'))
        text = '\n'.join(importer.clean_sbck_page(r['raw']) for r in revisions)
        passages, _, state = importer.sbck_lins(text, state)
        assert _strip(passages) == _strip(chapter['passages']), chapter['chapter_id']


def test_siku_volumes_resplit_from_the_frozen_revision():
    for i in range(1, 5):
        chapter = _chapter('yilin_siku', f'c{i:03}')
        raw = (KNOWLEDGE / chapter['raw_path']).read_text(encoding='utf-8')
        body = '\n'.join(re.findall(r'<onlyinclude>(.*?)</onlyinclude>', raw, re.S)) or raw
        passages, _ = importer.siku_lins(importer.clean_wiki(body))
        assert _strip(passages) == _strip(chapter['passages']), chapter['chapter_id']


def test_coverage_is_recorded_and_nearly_complete():
    books = {b['id']: b for b in json.loads((KNOWLEDGE / 'manifest.json').read_text(encoding='utf-8'))['books']}
    for book, floor in (('yilin', 4081), ('yilin_siku', 4096)):
        lins = books[book]['completeness']['lins']
        assert lins['expected_lins'] == 4096 and lins['found_lins'] >= floor
        assert lins['found_lins'] + len(lins['missing']) == 4096
    verses = [p['text'] for i in range(1, 17) for p in _chapter('yilin', f'c{i:03}')['passages']
              if p['layer'] == 'base_text']
    lengths = [len(re.sub(r'〔[^〕]*〕', 'X', v)) for v in verses]
    # 林辞是四言韵语：切分对了，绝大多数林的字数是 4 的倍数。
    assert sum(n % 4 == 0 for n in lengths) / len(lengths) > 0.94


def test_lookup_shows_both_editions_side_by_side():
    got = lin('乾', '坤')
    texts = {v['book']: v['text'] for v in got['versions']}
    assert texts['yilin'].startswith('招禍') and texts['yilin_siku'].startswith('招殃')
    assert got['same_text'] is False
    assert all(v['passage_id'].startswith(v['book'] + ':') for v in got['versions'])


@pytest.mark.parametrize('typed,expected', [('既济', '既濟'), ('小过', '小過'), ('无妄', '無妄'), ('颐', '頤'),
                                            ('兑', '兌'), ('乹', '乾'), ('归妹', '歸妹'), ('天王', None)])
def test_names_fold_simplified_and_source_spellings(typed, expected):
    assert canon(typed) == expected


def test_cli_lists_sixty_four_lins_and_refuses_unknown_names():
    got = run_cli('yilin_lookup.py', '--from', '乾')
    assert [x['zhi'] for x in got['lins']] == list(GUA)
    assert run_cli('yilin_lookup.py', '--from', '天王', expect_rc=1)['error_class'] == 'input'


def test_router_sends_yilin_questions_to_the_lookup():
    from question_router import route
    got = route('焦氏易林里乾之坤那一林是怎么说的')
    assert 'yilin_lookup.py' in got.get('command', '')
