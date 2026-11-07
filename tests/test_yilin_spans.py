"""Frozen source literals test heading boundaries independently of the importer constants."""
import hashlib
import json
import re
from functools import cache
from pathlib import Path

import import_classics as importer
import pytest
from conftest import corpus_text
from yilin_lookup import lin

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / 'skills/chinese-fortune/knowledge'
FROZEN = json.loads((Path(__file__).parent / 'data/yilin_siku_truncations.json').read_text(encoding='utf-8'))


@cache
def reparsed_siku():
    result = {}
    for number in range(1, 5):
        raw = corpus_text(f'sources/yilin_siku/c{number:03}.wiki')
        body = '\n'.join(re.findall(r'<onlyinclude>(.*?)</onlyinclude>', raw, re.S)) or raw
        passages, _ = importer.siku_lins(importer.clean_wiki(body))
        result.update({p['section']: p['text'] for p in passages if p['layer'] == 'base_text'})
    return result


@pytest.mark.parametrize('ending', ['坤', '屯', '乾', '革', '離'])
@pytest.mark.parametrize('separator', ['\n\u3000\u3000', '\r\n\u3000\u3000', '\n \t\u3000'])
def test_verse_ending_cannot_borrow_the_next_lines_indentation(ending, separator):
    source = f'乾之第一\n　乾　前言後語甲乙丙{ending}{separator}坤　鴻雁南飛隨陽休息\n　屯　君子無憂'
    passages, _ = importer.siku_lins(source)
    verses = {p['section']: p['text'] for p in passages if p['layer'] == 'base_text'}
    assert verses == {'乾之乾': f'前言後語甲乙丙{ending}', '乾之坤': '鴻雁南飛隨陽休息', '乾之屯': '君子無憂'}


def test_inline_headings_and_explicit_notes_keep_separate_source_spans():
    source = '乾之第一乾　甲乙〔注文〕異文一則〔/注文〕丙丁坤　戊己庚辛屯　壬癸甲乙'
    passages, _ = importer.siku_lins(source)
    assert [(p['section'], p['layer'], p['text']) for p in passages] == [
        ('乾之乾', 'base_text', '甲乙丙丁'), ('乾之乾', 'commentary', '異文一則'),
        ('乾之坤', 'base_text', '戊己庚辛'), ('乾之屯', 'base_text', '壬癸甲乙')]
    for passage in passages:
        span = passage['source_span']
        assert span['basis'] == 'clean_wiki_onlyinclude_codepoints'
        body = source[span['start']:span['end']]
        if passage['layer'] == 'base_text':
            assert re.sub(r'〔注文〕.*?〔/注文〕', '', body) == passage['text']
        else:
            assert re.findall(r'〔注文〕(.*?)〔/注文〕', body) == [passage['text']]


@pytest.mark.parametrize('case', FROZEN, ids=lambda case: case['section'])
def test_original_27_frozen_expectations_reach_the_public_lookup(case):
    assert reparsed_siku()[case['section']] == case['expected']
    got = next(v for v in lin(*case['section'].split('之'))['versions'] if v['book'] == 'yilin_siku')
    assert got['text'] == case['expected']
    assert got['sha256'] == hashlib.sha256(case['expected'].encode('utf-8')).hexdigest()


@pytest.mark.parametrize('ben,xun,dui', [
    ('乾', '出門逢惡為患為怨更相擊刺傷我手端', '鷁飛中退舉事不進宋人亂潰'),
    ('否', '杜口結舌言為禍母代伯受患無所禱免', '免冠進賢步出朝門儀體不正賊孽為患'),
    ('大有', '天之奥隅堯舜所居可以存身保我家室', '配合相迎利之四鄉昬以為期與福喜笑'),
    ('蠱', '重譯置之來除我憂喜樂俱居', '南山高岡麟鳯室堂含和履中國無灾殃'),
])
def test_four_frozen_xun_dui_pairs_keep_independent_verses(ben, xun, dui):
    for zhi, expected in (('巽', xun), ('兌', dui)):
        got = next(v for v in lin(ben, zhi)['versions'] if v['book'] == 'yilin_siku')
        assert got['text'] == expected


@pytest.mark.parametrize('zhi,expected', [
    ('鼎', '隂霧作匿不見白日邪徑迷道使君亂惑'),
    ('震', '猿墮髙木不踒手足握珠懐玉還歸我室'),
])
def test_sbck_cross_page_literals_remain_complete(zhi, expected):
    got = next(v for v in lin('復', zhi)['versions'] if v['book'] == 'yilin')
    assert got['text'] == expected and got['notes'] == []


def test_sbck_inline_commentaries_and_unresolved_attribution_survive():
    jian = next(v for v in lin('乾', '蹇')['versions'] if v['book'] == 'yilin')
    assert jian['text'].endswith('經渉虎穴亡羊失羔')
    assert [p['text'] for p in jian['notes']] == ['一本云亡羝失羊']
    jian = next(v for v in lin('渙', '漸')['versions'] if v['book'] == 'yilin')
    assert jian['text'] == '薛篾從靡空無誰是言季子明樂減少觧'
    assert [p['text'] for p in jian['notes']] == ['末句云難逢道理未詳']
    unresolved = next(v for v in lin('豐', '晉')['versions'] if v['book'] == 'yilin')
    assert unresolved['text'] is None and unresolved['unplaced_in_this_ben']


@pytest.mark.parametrize('number', range(1, 5))
def test_all_siku_record_spans_reconstruct_verse_and_commentary(number):
    chapter = json.loads(corpus_text(f'books/yilin_siku/c{number:03}.json'))
    raw = corpus_text(chapter['raw_path'])
    text = importer.clean_wiki('\n'.join(re.findall(r'<onlyinclude>(.*?)</onlyinclude>', raw, re.S)) or raw)
    for passage in chapter['passages']:
        span = passage['source_span']
        body = text[span['start']:span['end']]
        body = re.sub(r'==[^=]*==', '', body).replace('==', '')
        if passage['layer'] == 'base_text':
            expected = re.sub(r'〔注文〕.*?〔/注文〕', '', body, flags=re.S)
            heading_start, heading_end = passage['source_heading_span']
            assert heading_end == span['start'] and heading_start < heading_end
        else:
            expected = '；'.join(note.strip('　') for note in re.findall(r'〔注文〕(.*?)〔/注文〕', body, re.S))
        assert passage['text'] == re.sub(r'[ \t\r\n]+', '', expected).strip('　'), passage['section']


def test_all_4096_siku_verses_have_unique_edition_local_addresses():
    verses = [passage for number in range(1, 5)
              for passage in json.loads(corpus_text(f'books/yilin_siku/c{number:03}.json'))['passages']
              if passage['layer'] == 'base_text']
    assert len(verses) == len({p['section'] for p in verses}) == len({p['passage_id'] for p in verses}) == 4096


def test_unclassified_words_are_retained_with_coordinates():
    source = '未知卷首文字\n乾之第一乾　甲乙丙丁'
    _, problems = importer.siku_lins(source)
    unclassified = next(p for p in problems if p['kind'] == 'unclassified_source_text')
    span = unclassified['source_span']
    assert source[span['start']:span['end']] == unclassified['text'] == '未知卷首文字\n'
