"""--facts-out keeps the screen short and hands answer_check a file (round 5 S18 timeout)."""
import json
import subprocess
import sys

from conftest import SCRIPTS

BIRTH = ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--minute', '30', '--gender', 'male',
         '--timezone', 'Asia/Shanghai', '--longitude', '116.4']


def run(script, *args, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], input=stdin, capture_output=True,
                          text=True, encoding='utf-8')


def test_bazi_reading_writes_the_view_and_prints_the_draft(tmp_path):
    out = tmp_path / 'bazi.json'
    done = run('bazi_reading.py', *BIRTH, '--question', '八字格局与大运', '--request-time', '2026-10-24T04:00:00Z',
               '--current-timezone', 'Asia/Shanghai', '--view', 'compact', '--facts-out', str(out))
    assert done.returncode == 0, done.stdout
    assert len(done.stdout) < 6000 and str(out.resolve()) in done.stdout
    saved = json.loads(out.read_text(encoding='utf-8'))
    assert saved['view'] == 'compact' and saved['chart_facts']['four_pillars']['day']['ganzhi'] == '壬申'
    check = run('answer_check.py', '--answer', '-', '--facts', str(out), stdin='日柱甲子。')
    assert [f['code'] for f in json.loads(check.stdout)['findings']] == ['pillar_mismatch']
    again = run('bazi_reading.py', *BIRTH, '--facts-out', str(out))   # replacing its own file is fine
    assert again.returncode == 0


def test_facts_out_refuses_other_files_and_non_json_paths(tmp_path):
    files = {'notes.json': '[1, 2]', 'export.json': '{"tool":"foreign_export","keep":"preserve"}',
             'doctor.json': '{"ok":true,"tool":"doctor"}'}
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding='utf-8')
    for path in [tmp_path / name for name in files] + [tmp_path / 'draft.txt']:
        done = run('bazi_reading.py', *BIRTH, '--facts-out', str(path))
        assert done.returncode == 1 and json.loads(done.stdout)['error'] == 'facts_unavailable', path
    assert {name: (tmp_path / name).read_text(encoding='utf-8') for name in files} == files


def test_a_facts_file_from_another_tool_is_not_replaced(tmp_path):
    out = tmp_path / 'facts.json'
    assert run('bazi_reading.py', *BIRTH, '--facts-out', str(out)).returncode == 0
    before = out.read_bytes()
    request = {'intent': 'natal', 'participants': [{'id': 'me', 'confirmed': True, 'person': {
        'birth': {'year': 2000, 'month': 1, 'day': 15, 'hour': 10, 'minute': 30, 'gender': 'male',
                  'timezone': 'Asia/Shanghai', 'longitude': 116.4}, 'time_certainty': 'exact'}}],
               'current_timezone': 'Asia/Shanghai', 'request_time': '2026-11-01T10:00:00+08:00'}
    done = run('fortune_reading.py', '--stdin', '--facts-out', str(out), stdin=json.dumps(request))
    assert done.returncode == 1 and out.read_bytes() == before


def test_fortune_reading_facts_out(tmp_path):
    request = {'intent': 'period', 'question': '最近事业运势', 'event': {'scenario': 'outlook'},
               'current_timezone': 'Asia/Shanghai', 'request_time': '2026-11-01T10:00:00+08:00', 'period': '月底前',
               'participants': [{'id': 'me', 'confirmed': True, 'person': {
                   'birth': {'year': 1990, 'month': 5, 'day': 10, 'hour': 14, 'minute': 0, 'gender': 'male',
                             'timezone': 'Asia/Shanghai', 'longitude': 116.4}, 'time_certainty': 'exact'}}]}
    out = tmp_path / 'period.json'
    done = run('fortune_reading.py', '--stdin', '--facts-out', str(out), stdin=json.dumps(request))
    assert done.returncode == 0, done.stdout
    assert '回答按这个顺序：先说这段时间指 2026-11-01 至 2026-11-30' in done.stdout
    assert '2026年（丙午）' in done.stdout          # 阶段运势 lists the year layer even for a month
    assert json.loads(out.read_text(encoding='utf-8'))['host_notes']
