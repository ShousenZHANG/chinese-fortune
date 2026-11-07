"""分享卡片：一张离线 SVG，内容只取同一次计算的工具事实；分享版隐去能反推出生的值，不覆盖已有文件。"""
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading
from reading_views import write_card
from report_views import REPO, share_card_svg

BIRTH = ['--year', '1990', '--month', '5', '--day', '10', '--hour', '14', '--minute', '20', '--gender', 'male',
         '--city', '杭州', '--as-of-year', '2026']
QUESTION = '明年适合换工作吗'
SVG_NS = 'http://www.w3.org/2000/svg'


@pytest.fixture(scope='module')
def result():
    return prepare_reading(calculate_bazi(build_parser().parse_args(BIRTH)), QUESTION)


def _text(svg: str) -> str:
    root = ET.fromstring(svg)
    return ''.join(root.itertext())


def test_card_is_well_formed_offline_svg_built_from_the_tool_facts(result):
    svg = share_card_svg(result)
    assert svg.startswith('<svg') and ET.fromstring(svg).tag == f'{{{SVG_NS}}}svg'
    assert 'href' not in svg and '<script' not in svg and '<image' not in svg and '@import' not in svg
    text = _text(svg)
    for p in result['chart_facts']['four_pillars'].values():
        assert p['stem'] in text and p['branch'] in text
    day = result['chart_facts']['day_master']
    assert f"{day['stem']}{day['wuxing']}" in text
    for route in result['rule_assessment']['routes'][:3]:
        assert route['title'] in text and route['passage_id'] in text
    current = [row for row in result['chart_facts']['da_yun']
               if row['start_year'] <= result['chart_facts']['reference_year'] <= row['end_year']]
    assert current and current[0]['ganzhi'] in text
    assert REPO in text and '不是预测' in text and result['version'] in text
    assert QUESTION not in text  # 问题原话不上卡片


def test_redacted_card_leaves_no_value_that_identifies_the_birth(result):
    text = _text(share_card_svg(result, redact=True))
    facts = result['chart_facts']
    banned = [QUESTION, '杭州', '1990', '05-10', '14:20', '120.']
    banned += [p['ganzhi'] for p in facts['four_pillars'].values()]
    banned += [str(row['start_year']) for row in facts.get('da_yun') or []]
    for value in banned:
        assert value not in text, value
    assert not re.search(r'(?<!\d)(?:19|20)\d\d(?!\d)', text), '公历年份可反推出生年'
    assert not re.search(r'[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]', text.replace(REPO, '').replace('子平', '')), '单个干支也隐去'
    for route in result['rule_assessment']['routes'][:3]:
        assert route['passage_id'] in text  # 段号指公开古籍，不指人
    assert '已隐去' in text


def test_unknown_hour_card_says_undetermined_instead_of_a_placeholder_pillar():
    args = list(BIRTH)
    cut = args.index('--hour')
    del args[cut:cut + 4]
    reading = prepare_reading(calculate_bazi(build_parser().parse_args(args)), '')
    text = _text(share_card_svg(reading))
    assert '未定' in text and '候选' not in text


def test_card_text_is_escaped(result):
    hostile = json.loads(json.dumps(result))
    hostile['rule_assessment']['routes'][0]['title'] = '<script>x</script>'
    svg = share_card_svg(hostile)
    assert '<script>' not in svg and '&lt;script&gt;' in svg
    ET.fromstring(svg)


def test_write_card_refuses_overwrite_wrong_suffix_and_the_skill_folder(result, tmp_path, monkeypatch):
    target = tmp_path / '卡片.svg'
    saved = write_card(result, str(target))
    assert saved == {'path': str(target.resolve()), 'format': 'svg', 'offline': True, 'redacted': False}
    first = target.read_text(encoding='utf-8')
    with pytest.raises(FileExistsError):
        write_card(result, str(target))
    assert target.read_text(encoding='utf-8') == first
    with pytest.raises(ValueError, match='.svg'):
        write_card(result, str(tmp_path / 'card.png'))
    import reading_views
    root = tmp_path / 'skill'
    root.mkdir()
    monkeypatch.setattr(reading_views, 'SKILL_ROOT', root)
    with pytest.raises(ValueError, match='目录之外'):
        write_card(result, str(root / 'card.svg'))
    assert not list(root.iterdir())
    shared = write_card(result, str(tmp_path / 'share.svg'), redact=True)
    assert shared['redacted'] is True and shared['removed']


def test_cli_writes_the_card_from_the_same_reading(tmp_path):
    card = tmp_path / 'share.svg'
    command = [sys.executable, '-X', 'utf8', 'scripts/bazi_reading.py', *BIRTH, '--view', 'compact',
               '--card', str(card), '--card-redact']
    skill = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune'
    done = subprocess.run(command, cwd=skill, capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr or done.stdout
    reading = json.loads(done.stdout)
    assert reading['card']['path'] == str(card.resolve()) and reading['card']['redacted'] is True
    assert reading['chart_facts']['four_pillars']['day']['ganzhi'] not in card.read_text(encoding='utf-8')
    again = subprocess.run(command, cwd=skill, capture_output=True, text=True, encoding='utf-8')
    assert again.returncode != 0 and json.loads(again.stdout)['error'] == 'card_unavailable'
