"""报告的白话与专业写法、离线命盘图、分享预览不残留敏感字段。"""
import re

import pytest
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading, render_facts
from reading_views import write_report
from report_views import pillar_rows, pillar_svg, redact_text

BIRTH = ['--year', '1990', '--month', '5', '--day', '10', '--hour', '14', '--minute', '20', '--gender', 'male',
         '--city', '杭州', '--as-of-year', '2026']
QUESTION = '明年适合换工作吗'


@pytest.fixture(scope='module')
def result():
    return prepare_reading(calculate_bazi(build_parser().parse_args(BIRTH)), QUESTION)


def test_professional_html_has_an_offline_chart_and_tables(result, tmp_path):
    saved = write_report(result, render_facts(result), str(tmp_path / 'pro.html'), style='professional')
    html = (tmp_path / 'pro.html').read_text(encoding='utf-8')
    assert saved['style'] == 'professional' and saved['redacted'] is False
    assert '<svg' in html and html.count('<table') >= 2
    assert not re.search(r'(?:src|href)=["\']?https?:', html)  # 不连网
    for p in result['chart_facts']['four_pillars'].values():
        assert p['stem'] in html and p['branch'] in html


def test_plain_is_the_default_and_markdown_gets_tables_not_svg(result, tmp_path):
    write_report(result, render_facts(result), str(tmp_path / 'plain.html'))
    assert '<svg' not in (tmp_path / 'plain.html').read_text(encoding='utf-8')
    write_report(result, render_facts(result), str(tmp_path / 'pro.md'), style='professional')
    md = (tmp_path / 'pro.md').read_text(encoding='utf-8')
    assert '| 柱 | 十神 |' in md and '<svg' not in md
    with pytest.raises(ValueError):
        write_report(result, '', str(tmp_path / 'x.html'), style='fancy')


@pytest.mark.parametrize('name,style', [('share.html', 'professional'), ('share.md', 'professional'),
                                        ('share-plain.html', 'plain')])
def test_share_preview_leaves_no_identifying_value(result, tmp_path, name, style):
    saved = write_report(result, render_facts(result), str(tmp_path / name), style=style, redact=True)
    text = (tmp_path / name).read_text(encoding='utf-8')
    assert saved['redacted'] is True and saved['removed']
    facts = result['chart_facts']
    banned = [QUESTION, '杭州', '1990', '05-10', '14:20', '120.']
    banned += [p['ganzhi'] for p in facts['four_pillars'].values()]
    banned += [str(row['start_year']) for row in facts.get('da_yun') or []]
    for value in banned:
        assert value not in text, value
    body = text.replace('http://www.w3.org/2000/svg', '')  # SVG 命名空间网址里的 2000 不是年份
    assert not re.search(r'(?<!\d)(?:19|20)\d\d(?!\d)', body), '公历年份可反推出生年'
    assert '"input"' not in text and 'birth_instant' not in text
    assert '十神' in text or '正官' in text  # 关系名称保留


def test_single_stems_are_masked_but_ordinary_words_survive(result):
    out = redact_text('日主是乙，月令巳；这一条还未核，按《子平真诠》取运。', result)
    assert '乙' not in out and '巳' not in out
    assert '还未核' in out and '子平真诠' in out


def test_svg_is_self_contained_and_escapes_text():
    rows = [{'label': '年柱', 'role': '<b>', 'stem': '甲', 'branch': '子', 'hidden': '癸', 'nayin': '海中金'}] * 4
    svg = pillar_svg(rows)
    assert svg.startswith('<svg') and '&lt;b&gt;' in svg and 'http://www.w3.org/2000/svg' in svg
    assert 'href' not in svg


def test_redacted_pillar_rows_hide_stems(result):
    assert {r['stem'] for r in pillar_rows(result, redact=True)} == {'□'}
