"""Runtime lookup of real-world references: mapped, region-gated, never TODO."""
import json
import subprocess
import sys
from pathlib import Path

from life_guide import SCENARIO_ENTRIES, entries_for, get_entry, search

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'assets' / 'life_guide.json').read_text(encoding='utf-8'))
PRESENT = {(e['section'], e['number']) for e in DATA['entries']}


def _ids(rows):
    return [(r['section'], r['number']) for r in rows]


def _req(scenario, current='Australia/Sydney', **event):
    return {'current_timezone': current, 'event': {'scenario': scenario, **event}}


def test_every_mapped_entry_exists_in_the_snapshot():
    for scenario, ids in SCENARIO_ENTRIES.items():
        for key in ids:
            assert key in PRESENT, (scenario, key)


def test_mainland_rental_rules_are_not_attached_in_sydney():
    assert entries_for(_req('moving')) == []


def test_they_are_attached_when_the_flat_is_on_the_mainland():
    rows = entries_for(_req('moving', timezone='Asia/Shanghai'))
    assert rows and {r['section'] for r in rows} == {15}


def test_travel_abroad_gets_section_21_minus_todo_entries_capped_at_three():
    rows = entries_for(_req('travel', destination_timezone='Asia/Singapore'))
    assert _ids(rows)[:2] == [(21, 1), (21, 2)]
    assert (21, 4) not in _ids(rows)          # 备注 TODO（待核实）
    assert len(rows) <= 3


def test_travel_without_a_destination_or_into_the_mainland_gets_nothing():
    assert entries_for(_req('travel')) == []
    assert entries_for(_req('travel', destination_timezone='Asia/Shanghai')) == []
    assert entries_for(_req('travel', destination_timezone='Asia/Hong_Kong')) == []


def test_an_unknown_region_attaches_nothing_region_bound():
    assert entries_for(_req('moving', current='UTC', timezone='Etc/UTC')) == []


def test_unmapped_scenarios_attach_nothing():
    assert entries_for(_req('outlook', current='Asia/Shanghai')) == []
    assert entries_for(_req('讨论社团活动', current='Asia/Shanghai')) == []


def test_an_explicit_lookup_says_when_the_rules_are_not_the_users():
    row = get_entry(15, 1, _req('moving'))
    assert row['fields']['说人话']
    assert row['region_note'] == '这是中国大陆的规定；你所在地的规定可能不同'


def test_the_excluded_entries_cannot_be_reached_by_any_route():
    assert get_entry(6, 15, _req('outlook')) is None
    assert get_entry(6, 22, _req('outlook')) is None
    hits = _ids(search('算命'))
    assert (6, 15) not in hits and (6, 22) not in hits


def test_the_cli_returns_an_envelope_with_whole_entries():
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'life_guide.py'),
                           '--scenario', 'travel', '--current-timezone', 'Australia/Sydney',
                           '--destination-timezone', 'Asia/Singapore'],
                          capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data['ok'] and data['region']['region'] == '境外'
    assert data['source']['commit'].startswith('8276caec')
    assert all(set(r['fields']) >= {'说人话', '备注', '来源'} for r in data['entries'])
