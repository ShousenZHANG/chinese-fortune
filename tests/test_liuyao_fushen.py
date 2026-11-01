"""伏神 as 增删卜易 places it: 日月 first, then the palace's pure hexagram (c032:p0049, p0063, p0070)."""
import subprocess
import sys

import pytest
from conftest import SCRIPTS, run_cli


def cast(lines, date, question):
    return run_cli('liuyao_cast.py', 'coins', '--lines', lines, '--date', date, '--time', '10:00',
                   '--target-timezone', 'Asia/Shanghai', '--current-timezone', 'Asia/Shanghai', '--question', question)


def test_book_example_gou_wealth_hides_under_hai():
    """p0063: 姤卦无财, 乾为天二爻寅木伏于姤二爻亥水之下, 飞来生伏."""
    row = cast('8,7,7,7,7,7', '2026-11-20', '求财')['fu_shen'][0]
    assert row['relative'] == '妻财' and row['status'] == 'hidden' and row['pure_hexagram'] == 1
    assert [(f['position'], f['stem'] + f['branch'], f['fei_shen']['branch'], f['relation'])
            for f in row['fu_shen']] == [(2, '甲寅', '亥', '飞神生伏神')]


def test_book_example_dun_children_hides_under_chen():
    """p0070: 遁卦子孙不现, 乾为天初爻子水伏于遁初爻辰土之下, 飞克."""
    row = cast('8,8,7,7,7,7', '2026-09-21', '求子')['fu_shen'][0]
    assert [(f['position'], f['stem'] + f['branch'], f['fei_shen']['branch'], f['relation'])
            for f in row['fu_shen']] == [(1, '甲子', '辰', '飞神克伏神')]


def test_calendar_comes_before_the_hidden_spirit():
    """p0070: 倘在亥子月日占者, 卽以月日为用神."""
    row = cast('8,8,7,7,7,7', '2026-11-20', '求子')['fu_shen'][0]
    assert row['status'] == 'taken_from_calendar' and row['fu_shen'] == [] and row['calendar']


@pytest.mark.parametrize('lines,question', [('7,8,9,6,7,7', '下周的面试能不能通过'), ('8,7,7,7,7,7', '求财')])
def test_markdown_states_the_rule_and_the_dissent(lines, question):
    text = subprocess.run([sys.executable, str(SCRIPTS / 'liuyao_cast.py'), 'coins', '--lines', lines,
                           '--date', '2026-09-21', '--time', '10:00', '--target-timezone', 'Asia/Shanghai',
                           '--current-timezone', 'Asia/Shanghai', '--question', question, '--markdown'],
                          capture_output=True, text=True, encoding='utf-8', check=True).stdout
    assert '伏神本工具尚未计算' not in text
    assert 'zengshan:c032:p0049' in text


def test_present_relative_needs_no_hidden_spirit():
    assert cast('7,7,7,7,7,7', '2026-09-21', '求财')['fu_shen'] == []
