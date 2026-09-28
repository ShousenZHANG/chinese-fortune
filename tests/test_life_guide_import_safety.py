"""The importer refuses anything that would let the frozen library drift.

Built on small synthetic ZIPs so it runs without the real snapshot.
"""
import json
import zipfile

import pytest
from import_life_guide import COMMIT, build


def _entry(number: int, title: str, note: str = '无') -> str:
    return (f'### {number}. {title}\n'
            '<!-- 成本标签: 钱=0 时间=少 毅力=否 收益=中 口径=金钱 -->\n'
            '- 成本：不花钱\n- 说人话：照做\n- 收益：有\n- 证据等级：A\n- 来源：某文献\n'
            f'- 备注：{note}\n')


ARTICLE = '# 一篇长文\n\n正文。\n'


def _zip(tmp_path, files: dict[str, str], comment: str = COMMIT, article: str | None = ARTICLE):
    path = tmp_path / 'hltb.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.comment = comment.encode('ascii')
        for name, text in files.items():
            archive.writestr(f'HowToLiveBetter-main/book/{name}', text)
        if article is not None:
            archive.writestr('HowToLiveBetter-main/docs/结婚划不划算.md', article)
    return path


def _six(extra: str = '') -> str:
    return '# 反面清单\n\n' + _entry(1, '普通一条') + '\n' + _entry(15, '被排除的一条') + '\n' \
        + _entry(22, '被排除的另一条') + extra


def _files(six: str | None = None, extra29: str = '') -> dict[str, str]:
    """Every file holding an excluded entry, so the exclusion list is satisfied."""
    return {'06-反面清单.md': _six() if six is None else six,
            '29-变故.md': '# 变故\n\n' + _entry(12, '被排除的第三条') + extra29}


def test_a_well_formed_snapshot_drops_exactly_the_excluded_entries(tmp_path):
    data = build(_zip(tmp_path, _files()))
    assert [(e['section'], e['number']) for e in data['entries']] == [(6, 1)]
    assert '被排除' not in json.dumps(data, ensure_ascii=False)     # not even the titles
    assert data['source']['commit'] == COMMIT and len(data['source']['files']) == 3
    assert data['articles'][0]['title'] == '一篇长文'


def test_a_snapshot_without_the_long_article_is_refused(tmp_path):
    with pytest.raises(ValueError, match='没有长文'):
        build(_zip(tmp_path, _files(), article=None))


def test_the_long_article_goes_through_the_same_checks(tmp_path):
    with pytest.raises(ValueError, match='须先人工审定'):
        build(_zip(tmp_path, _files(), article='# 一篇长文\n\n见第 6 节第 15 条。\n'))


@pytest.mark.parametrize('note,dispute', [
    ('争议。另一派认为正好相反。其余不论。', '争议。另一派认为正好相反。'),
    ('前文。争议在于：样本太小。', '争议在于：样本太小。'),
    ('按劳动争议走仲裁。', None),
    ('这件事本身没有争议。', None),
])
def test_a_dispute_is_read_from_the_books_mark_only(tmp_path, note, dispute):
    six = _six('\n' + _entry(30, '另一条', note=note))
    entry = next(e for e in build(_zip(tmp_path, _files(six)))['entries'] if e['number'] == 30)
    assert entry['dispute'] == dispute and entry['disputed'] is (dispute is not None)


def test_a_zip_from_another_commit_is_refused(tmp_path):
    with pytest.raises(ValueError, match='不是固定的'):
        build(_zip(tmp_path, _files(), comment='0' * 40))


def test_a_snapshot_missing_an_excluded_entry_is_refused(tmp_path):
    """If the numbering shifted, the exclusion list would silently guard nothing."""
    text = '# 反面清单\n\n' + _entry(1, '普通一条') + '\n' + _entry(15, '被排除的一条')
    with pytest.raises(ValueError, match='排除清单'):
        build(_zip(tmp_path, _files(text)))


def test_a_kept_entry_pointing_at_an_excluded_one_is_refused_until_reviewed(tmp_path):
    extra = '\n' + _entry(30, '另一条', note='理由同本节第 15 条')
    with pytest.raises(ValueError, match='须先人工审定'):
        build(_zip(tmp_path, _files(_six(extra))))


@pytest.mark.parametrize('note', ['常见骗局见第 6 节（算命）', '同类问题见第 29 节', '理由同第 22 条'])
def test_a_reference_to_a_whole_section_or_a_bare_entry_number_is_caught_too(tmp_path, note):
    """「第 6 节」 with no entry number points at a section that holds excluded
    entries; 「第 22 条」 with no section is this section's entry 22."""
    extra = '\n' + _entry(30, '另一条', note=note)
    with pytest.raises(ValueError, match='须先人工审定'):
        build(_zip(tmp_path, _files(_six(extra))))


@pytest.mark.parametrize('six_note,note29', [
    ('见本节第 14、15 条', None),          # a list
    ('见第 20 到 22 条', None),            # a range
    ('见第 6 节第 14—16 条', None),
    (None, '见第 11 到 13 条'),
    (None, '同「被排除的第三条」那条'),     # by title
])
def test_listed_ranged_and_titled_references_are_caught(tmp_path, six_note, note29):
    six = _six('\n' + _entry(30, '另一条', note=six_note)) if six_note else None
    extra29 = '\n' + _entry(30, '另一条', note=note29) if note29 else ''
    with pytest.raises(ValueError, match='须先人工审定'):
        build(_zip(tmp_path, _files(six, extra29)))


def test_a_list_that_misses_the_excluded_numbers_passes(tmp_path):
    extra = '\n' + _entry(30, '另一条', note='见本节第 1、16 条和第 23 到 25 条')
    build(_zip(tmp_path, _files(_six(extra))))


@pytest.mark.parametrize('word', ['算命', '塔罗', '风水'])
def test_a_kept_entry_that_mentions_divination_is_refused_until_reviewed(tmp_path, word):
    """The product decision: nothing that passes judgement on divination is shipped."""
    extra = '\n' + _entry(30, '另一条', note=f'针对老人的骗局包括{word}')
    with pytest.raises(ValueError, match='须先人工审定'):
        build(_zip(tmp_path, _files(_six(extra))))


def test_an_entry_missing_a_field_is_refused(tmp_path):
    broken = _six().replace('- 来源：某文献\n', '', 1)
    with pytest.raises(ValueError, match='缺「来源」栏'):
        build(_zip(tmp_path, _files(broken)))


def test_a_grade_outside_abc_is_refused(tmp_path):
    broken = _six().replace('- 证据等级：A', '- 证据等级：D', 1)
    with pytest.raises(ValueError, match='不是 A/B/C'):
        build(_zip(tmp_path, _files(broken)))
