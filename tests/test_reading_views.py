"""Compact views preserve decisions and uncertainty while avoiding duplicate source text."""
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from bazi_calc import build_parser, calculate_bazi
from bazi_reading import prepare_reading
from reading_views import compact_reading


def test_compact_keeps_every_route_condition_and_source_without_repeating_full_books():
    chart = calculate_bazi(build_parser().parse_args([
        '--year', '2000', '--month', '1', '--day', '15', '--hour', '10',
        '--minute', '30', '--gender', 'male', '--city', '北京', '--as-of-year', '2026']))
    full = prepare_reading(chart, '看八字大运与格局')
    original = deepcopy(full)
    compact = compact_reading(full)
    assert full == original
    assert compact['view'] == 'compact'
    assert compact['chart_facts']['four_pillars'] == full['chart_facts']['four_pillars']
    assert compact['host_notes'] == full['host_notes']
    actual = compact['rule_assessment']
    assert len(actual['routes']) == len(full['rule_assessment']['routes'])
    for route, prior in zip(actual['routes'], full['rule_assessment']['routes']):
        assert route['rule_id'] == prior['rule_id']
        assert route['status'] == prior['status']
        assert [actual['conditions'][key] for key in route['condition_refs']] == [
            {k: v for k, v in condition.items() if k != 'facts'} for condition in prior['conditions']]
    assert set(compact['evidence_index']) == {
        p['passage_id'] for p in full['evidence_bundle']['passages']}
    restored_luck = deepcopy(compact['luck_reading'])
    for reading in restored_luck:
        for scenario in reading['scenarios']:
            metadata = compact['luck_index']['scenarios'][scenario.pop('scenario_ref')]
            scenario.update(deepcopy(metadata))
            for part in ('stem', 'branch'):
                scenario[part]['verdicts'] = [compact['luck_index']['verdicts'][ref]
                                            for ref in scenario[part].pop('verdict_refs')]
    assert restored_luck == full['luck_reading']
    for case, prior in zip(compact['geju_review']['cases'], full['geju_review']['cases']):
        assert [compact['geju_review']['unresolved_conditions'][ref]
                for ref in case['unresolved_conditions_refs']] == prior['unresolved_conditions']
        for observation, original_observation in zip(case['observations'], prior['observations']):
            if 'groups' in original_observation:
                assert [compact['geju_review']['groups'][ref] for ref in observation['groups_refs']] == original_observation['groups']
    # Measure both the payload and the actual CLI serialization (compact has no
    # pretty-print whitespace). Do not conflate these with model token savings.
    assert len(json.dumps(compact, ensure_ascii=False)) < len(json.dumps(full, ensure_ascii=False)) * .5
    assert len(json.dumps(compact, ensure_ascii=False, separators=(',', ':'))) < len(json.dumps(full, ensure_ascii=False, indent=2)) * .4


def test_cli_can_save_an_offline_report_from_the_same_result_without_overwrite(tmp_path):
    report = tmp_path / '核对.html'
    command = [sys.executable, '-X', 'utf8', 'scripts/bazi_reading.py',
               '--year', '2000', '--month', '1', '--day', '15', '--hour', '10',
               '--gender', 'male', '--as-of-year', '2026', '--question', '<script>不是可执行内容</script>',
               '--view', 'compact', '--report', str(report)]
    done = subprocess.run(command, cwd=Path(__file__).resolve().parents[1] / 'skills/chinese-fortune',
                          capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr or done.stdout
    result = json.loads(done.stdout)
    assert result['view'] == 'compact'
    assert result['report']['path'] == str(report.resolve())
    html = report.read_text(encoding='utf-8')
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert '<details>' in html and '<summary>' in html
    assert '<script src=' not in html and '@import' not in html
    assert result['chart_facts']['four_pillars']['day']['ganzhi'] in html
    assert '已可固定的柱' in html.split('<details>', 1)[0]
    again = subprocess.run(command, cwd=Path(__file__).resolve().parents[1] / 'skills/chinese-fortune',
                           capture_output=True, text=True, encoding='utf-8')
    assert again.returncode != 0
    assert json.loads(again.stdout)['error'] == 'report_unavailable'
    assert report.read_text(encoding='utf-8') == html


def test_report_question_is_plain_text_and_cannot_enter_the_skill_package(tmp_path, monkeypatch):
    import pytest
    import reading_views
    from reading_views import write_report
    result = {'version': 'test', 'question': '![核对图片](https://example.invalid/remote-image.png)\n```\n<script>'}
    destination = tmp_path / 'outside.md'
    write_report(result, '只核事实。', str(destination))
    content = destination.read_text(encoding='utf-8')
    assert r'\!\[核对图片\]' in content
    assert '<script>' not in content.split('## 完整计算资料与出处')[0]
    assert '````json' in content
    root = tmp_path / 'skill'
    root.mkdir()
    monkeypatch.setattr(reading_views, 'SKILL_ROOT', root)
    with pytest.raises(ValueError, match='目录之外'):
        write_report(result, '只核事实。', str(root / 'private.html'))
    assert not list(root.iterdir())
