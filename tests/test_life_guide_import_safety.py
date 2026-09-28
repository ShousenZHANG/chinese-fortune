"""The importer refuses anything that would let the frozen library drift.

Built on small synthetic ZIPs so it runs without the real snapshot.
"""
import zipfile

import pytest
from import_life_guide import COMMIT, build


def _entry(number: int, title: str, note: str = '无') -> str:
    return (f'### {number}. {title}\n'
            '<!-- 成本标签: 钱=0 时间=少 毅力=否 收益=中 口径=金钱 -->\n'
            '- 成本：不花钱\n- 说人话：照做\n- 收益：有\n- 证据等级：A\n- 来源：某文献\n'
            f'- 备注：{note}\n')


def _zip(tmp_path, files: dict[str, str], comment: str = COMMIT):
    path = tmp_path / 'hltb.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.comment = comment.encode('ascii')
        for name, text in files.items():
            archive.writestr(f'HowToLiveBetter-main/book/{name}', text)
    return path


def _six(extra: str = '') -> str:
    return '# 反面清单\n\n' + _entry(1, '普通一条') + '\n' + _entry(15, '被排除的一条') + '\n' \
        + _entry(22, '被排除的另一条') + extra


def test_a_well_formed_snapshot_drops_exactly_the_excluded_entries(tmp_path):
    data = build(_zip(tmp_path, {'06-反面清单.md': _six()}))
    assert [(e['section'], e['number']) for e in data['entries']] == [(6, 1)]
    assert {(x['section'], x['number']) for x in data['excluded']} == {(6, 15), (6, 22)}
    assert data['source']['commit'] == COMMIT and len(data['source']['files']) == 1


def test_a_zip_from_another_commit_is_refused(tmp_path):
    with pytest.raises(ValueError, match='不是固定的'):
        build(_zip(tmp_path, {'06-反面清单.md': _six()}, comment='0' * 40))


def test_a_snapshot_missing_an_excluded_entry_is_refused(tmp_path):
    """If the numbering shifted, the exclusion list would silently guard nothing."""
    text = '# 反面清单\n\n' + _entry(1, '普通一条') + '\n' + _entry(15, '被排除的一条')
    with pytest.raises(ValueError, match='排除清单'):
        build(_zip(tmp_path, {'06-反面清单.md': text}))


def test_a_kept_entry_pointing_at_an_excluded_one_is_refused_until_reviewed(tmp_path):
    extra = '\n' + _entry(30, '另一条', note='理由同本节第 15 条')
    with pytest.raises(ValueError, match='须先人工审定'):
        build(_zip(tmp_path, {'06-反面清单.md': _six(extra)}))


def test_an_entry_missing_a_field_is_refused(tmp_path):
    broken = _six().replace('- 来源：某文献\n', '', 1)
    with pytest.raises(ValueError, match='缺「来源」栏'):
        build(_zip(tmp_path, {'06-反面清单.md': broken}))


def test_a_grade_outside_abc_is_refused(tmp_path):
    broken = _six().replace('- 证据等级：A', '- 证据等级：D', 1)
    with pytest.raises(ValueError, match='不是 A/B/C'):
        build(_zip(tmp_path, {'06-反面清单.md': broken}))
