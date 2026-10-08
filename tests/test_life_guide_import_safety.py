"""The importer refuses anything that would let the frozen library drift.

Built on small synthetic ZIPs so it runs without the real snapshot.
"""
from __future__ import annotations

import json
import zipfile

import pytest
from import_life_guide import ARTICLES, COMMIT, build


def _entry(number: int, title: str, note: str = '无') -> str:
    return (f'### {number}. {title}\n'
            '<!-- 成本标签: 钱=0 时间=少 毅力=否 收益=中 口径=金钱 -->\n'
            '- 成本：不花钱\n- 说人话：照做\n- 收益：有\n- 证据等级：A\n- 来源：某文献\n'
            f'- 备注：{note}\n')


README = '\n'.join([
    '# 书', '', '## 这本书想回答的问题', '', '| 问题 | 去哪看 |', '| --- | --- |',
    '| 哪些可以直接不买？ | [6. 反面清单](book/06-反面清单.md) |',
    '| 遭遇打击之后先盯住什么？ | [29. 遭遇重大打击之后](book/29-遭遇重大打击之后.md) |', '',
    '## 四种资源', '', '寿命、时间与精力、金钱、人身自由；第 ④ 档陌生人。', '',
    '## 证据分级', '', 'A 荟萃分析；B；C。', '',
    '## 性价比档', '', '不同口径之间不做比较。', '',
    '## 读懂数字（术语表）', '', '| 术语 | 意思 |', '| --- | --- |', '| HR | 风险比 |', '',
    '## 目录', '', '略', ''])
MIT = 'MIT License\n\nCopyright (c) 2026 eternity4719\n\nPermission is hereby granted...\n'
SIX_INTRO = '本节收的是看起来有效的东西。\n\n**保健品和补剂**：第 1 条。\n\n**花钱买运气和心情**：第 15 条，第 22 条。\n\n'
SIX_ENTRIES = [(1, '普通一条'), (14, '第十四条'), (15, '不要花钱算命的一条'), (16, '第十六条'), (20, '第二十条'),
               (21, '第二十一条'), (22, '不要为了转运买东西'), (23, '第二十三条'), (24, '第二十四条'), (25, '第二十五条')]
NINE_ENTRIES = [(11, '第十一条'), (12, '变故后的头三个月的一条'), (13, '第十三条')]


def _six(extra: str = '', intro: str = SIX_INTRO) -> str:
    return '# 6. 反面清单\n\n' + intro + '\n'.join(_entry(n, t) for n, t in SIX_ENTRIES) + extra


def _files(six: str | None = None, extra29: str = '') -> dict[str, str]:
    """Every file holding an excluded entry, so the exclusion list is satisfied."""
    return {'book/06-反面清单.md': _six() if six is None else six,
            'book/29-遭遇重大打击之后.md': '# 29. 遭遇重大打击之后\n\n导读。\n\n'
            + '\n'.join(_entry(n, t) for n, t in NINE_ENTRIES) + extra29}


def _zip(tmp_path, files: dict[str, str], comment: str = COMMIT, articles: dict[str, str] | None = None,
         readme: str | None = README, code_license: str | None = MIT):
    path = tmp_path / 'hltb.zip'
    docs = {base: f'# {base[:-3]}\n\n正文。\n' for base in ARTICLES} if articles is None else articles
    with zipfile.ZipFile(path, 'w') as archive:
        archive.comment = comment.encode('ascii')
        for name, text in files.items():
            archive.writestr(f'HowToLiveBetter-main/{name}', text)
        for base, text in docs.items():
            archive.writestr(f'HowToLiveBetter-main/docs/{base}', text)
        if readme is not None:
            archive.writestr('HowToLiveBetter-main/README.md', readme)
        if code_license is not None:
            archive.writestr('HowToLiveBetter-main/LICENSE-CODE', code_license)
    return path


def _build(tmp_path, **kwargs):
    return build(_zip(tmp_path, **kwargs), check_reviews=False)


def _with_entry(note: str, section: int = 6) -> dict[str, str]:
    if section == 6:
        return _files(_six('\n' + _entry(30, '另一条', note=note)))
    return _files(extra29='\n' + _entry(30, '另一条', note=note))


def test_a_well_formed_snapshot_drops_exactly_the_excluded_entries(tmp_path):
    data = _build(tmp_path, files=_files())
    kept = [(e['section'], e['number']) for e in data['entries']]
    assert (6, 15) not in kept and (6, 22) not in kept and (29, 12) not in kept
    assert len(kept) == len(SIX_ENTRIES) + len(NINE_ENTRIES) - 3
    text = json.dumps(data, ensure_ascii=False)
    assert '花钱算命' not in text and '转运' not in text and '变故后的头三个月' not in text
    assert '花钱买运气和心情' not in text                   # the overview line that lists them
    assert data['source']['commit'] == COMMIT
    assert len(data['articles']) == len(ARTICLES)
    assert [q['section'] for q in data['guide']['questions']] == [6, 29]
    assert data['guide']['glossary'] == [{'term': 'HR', 'meaning': '风险比'}]


def test_a_zip_from_another_commit_is_refused(tmp_path):
    with pytest.raises(ValueError, match='不是固定的'):
        _build(tmp_path, files=_files(), comment='0' * 40)


def test_a_missing_or_unreviewed_long_article_is_refused(tmp_path):
    some = dict.fromkeys(list(ARTICLES)[:-1], '# x\n')
    with pytest.raises(ValueError, match='没有长文'):
        _build(tmp_path, files=_files(), articles=some)
    extra = {**dict.fromkeys(ARTICLES, '# x\n'), '新长文.md': '# 新长文\n'}
    with pytest.raises(ValueError, match='未审定的长文'):
        _build(tmp_path, files=_files(), articles=extra)


def test_a_snapshot_without_the_readme_is_refused(tmp_path):
    with pytest.raises(ValueError, match='README'):
        _build(tmp_path, files=_files(), readme=None)


def test_the_mit_notice_of_the_ported_code_ships_with_the_data(tmp_path):
    detail = _build(tmp_path, files=_files())['source']['license_detail']
    assert detail['code_notice'].startswith('MIT License')
    assert 'eternity4719' in detail['code_notice']
    assert detail['text'] == 'CC BY 4.0' and detail['text_url'].startswith('https://creativecommons.org/')


@pytest.mark.parametrize('code_license, message', [(None, 'LICENSE-CODE'), ('Apache License 2.0\n', '不再是 MIT')])
def test_a_snapshot_without_the_mit_code_license_is_refused(tmp_path, code_license, message):
    with pytest.raises(ValueError, match=message):
        _build(tmp_path, files=_files(), code_license=code_license)


def test_the_readme_texts_go_through_the_same_checks(tmp_path):
    readme = README.replace('| HR | 风险比 |', '| HR | 风险比，和算命无关 |')
    with pytest.raises(ValueError, match='README 含「算命」'):
        _build(tmp_path, files=_files(), readme=readme)


def test_the_long_articles_go_through_the_same_checks(tmp_path):
    docs = dict.fromkeys(ARTICLES, '# x\n')
    docs['被裁了之后先做什么.md'] = '# 被裁\n\n见第 6 节第 15 条。\n'
    with pytest.raises(ValueError, match='须先人工审定'):
        _build(tmp_path, files=_files(), articles=docs)


def test_a_renumbered_exclusion_is_refused(tmp_path):
    """If 6:15 no longer says 不要花钱算命, the number now names another entry."""
    six = _six().replace('不要花钱算命的一条', '别的一条')
    with pytest.raises(ValueError, match='编号可能已变化'):
        _build(tmp_path, files=_files(six))


def test_the_excluded_overview_paragraph_must_still_be_there(tmp_path):
    six = _six(intro='本节导读。\n\n')
    with pytest.raises(ValueError, match='找不到唯一一段'):
        _build(tmp_path, files=_files(six))


def test_a_review_whose_title_is_gone_fails_the_real_import(tmp_path):
    with pytest.raises(ValueError, match='审定数据里的标题'):
        build(_zip(tmp_path, files=_files()))


@pytest.mark.parametrize('note,dispute', [
    ('争议。另一派认为正好相反。其余不论。', '争议。另一派认为正好相反。'),
    ('争议在于：样本太小。', '争议在于：样本太小。'),
    ('前文。争议在于：样本太小。', None),        # the book's badge needs the 备注 to open with it
    ('按劳动争议走仲裁。', None),
    ('这件事本身没有争议。', None),
])
def test_a_dispute_is_read_from_the_books_mark_only(tmp_path, note, dispute):
    entry = next(e for e in _build(tmp_path, files=_with_entry(note))['entries'] if e['number'] == 30)
    assert entry['dispute'] == dispute and entry['disputed'] is (dispute is not None)


@pytest.mark.parametrize('note,section', [
    ('理由同本节第 15 条', 6),
    ('见本节第 14、15 条', 6),                  # a list
    ('见第 20 到 22 条', 6),                    # a range
    ('见第 6 节第 22 条', 29),                  # across sections
    ('见第 11 到 13 条', 29),
    ('同「变故后的头三个月」那条', 29),           # by title
    ('常见骗局见第 6 节（算命）', 29),            # a divination word and a whole section
    ('同类问题见第 29 节', 6),                  # a whole section that holds an excluded entry
])
def test_any_reference_to_an_excluded_entry_needs_review(tmp_path, note, section):
    with pytest.raises(ValueError, match='须先人工审定'):
        _build(tmp_path, files=_with_entry(note, section))


def test_a_list_that_misses_the_excluded_numbers_passes(tmp_path):
    data = _build(tmp_path, files=_with_entry('见本节第 1、16 条和第 23 到 25 条'))
    entry = next(e for e in data['entries'] if e['number'] == 30)
    assert entry['refs'] == [[6, 1], [6, 16], [6, 23], [6, 24], [6, 25]]


def test_a_reference_to_a_missing_entry_is_refused(tmp_path):
    with pytest.raises(ValueError, match='交叉引用有问题'):
        _build(tmp_path, files=_with_entry('见本节第 99 条'))


@pytest.mark.parametrize('word', ['算命', '塔罗', '风水'])
def test_a_kept_entry_that_mentions_divination_is_refused_until_reviewed(tmp_path, word):
    """The product decision: nothing that passes judgement on divination is shipped."""
    with pytest.raises(ValueError, match='须先人工审定'):
        _build(tmp_path, files=_with_entry(f'针对老人的骗局包括{word}'))


def test_an_entry_missing_a_field_is_refused(tmp_path):
    broken = _six().replace('- 来源：某文献\n', '', 1)
    with pytest.raises(ValueError, match='缺「来源」栏'):
        _build(tmp_path, files=_files(broken))


def test_a_grade_outside_abc_is_refused(tmp_path):
    broken = _six().replace('- 证据等级：A', '- 证据等级：D', 1)
    with pytest.raises(ValueError, match='不是 A/B/C'):
        _build(tmp_path, files=_files(broken))
