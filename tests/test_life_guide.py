"""Runtime lookup of real-world references: mapped, region-gated, never TODO."""
import json
import subprocess
import sys
from pathlib import Path

from life_guide import FOREIGN_NOTE, SCENARIO_ENTRIES, entries_for, get_entry, search

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


def test_the_cli_query_takes_the_users_region():
    proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'life_guide.py'),
                           '--query', '押金', '--current-timezone', 'Australia/Sydney'],
                          capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)['entries']
    assert rows and all(r.get('region_note') == FOREIGN_NOTE for r in rows if r['region'] == '中国大陆')


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
    for key in ((6, 15), (6, 22), (29, 12)):
        assert get_entry(*key, _req('outlook')) is None, key
    assert search('算命', {}) == []


def test_search_gives_the_same_region_note_as_an_explicit_lookup():
    rows = search('押金', _req('outlook'))
    mainland = [r for r in rows if r['region'] == '中国大陆']
    assert mainland and all(r['region_note'] == FOREIGN_NOTE for r in mainland)
    assert all('region_note' not in r for r in search('押金', _req('outlook', current='Asia/Shanghai')))


def test_search_leaves_out_entries_the_book_marks_unverified():
    """21:4 carries a TODO; the book's own rule is not to use those as conclusions."""
    assert (21, 4) not in _ids(search('医疗转运', _req('outlook')))
    assert get_entry(21, 4, _req('outlook'))['todo_note']


def test_a_trip_inside_one_country_gets_no_border_crossing_advice():
    assert entries_for(_req('travel', destination_timezone='Australia/Melbourne')) == []
    assert entries_for(_req('travel', current='Asia/Shanghai', destination_timezone='Asia/Urumqi')) == []
    # Crossing a border still does, from anywhere.
    assert entries_for(_req('travel', current='Asia/Shanghai', destination_timezone='Asia/Singapore'))
    # Where the trip starts is unknown: whether it crosses a border is unknown too.
    assert entries_for(_req('travel', current=None, destination_timezone='Asia/Singapore')) == []


def test_the_certificate_entry_is_only_for_questions_about_certificates():
    """23:8 is about paying for a 考证 course, not about 高考 or 考研."""
    exam = _req('exam', current='Asia/Shanghai')
    assert entries_for({**exam, 'question': '下周高考哪天好'}) == []
    assert _ids(entries_for({**exam, 'question': '下个月考证哪天报名好'})) == [(23, 8)]


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
