"""Keep the user-facing lookup tables aligned with the selected runtime rules."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(('section', 'name'), [
    ('2.1', '天乙贵人'), ('2.2', '文昌贵人'), ('2.3', '太极贵人'),
    ('2.5', '福星贵人'), ('2.6', '国印贵人'), ('2.10', '天厨贵人'),
    ('2.12', '金舆'), ('3.1', '羊刃'), ('3.6', '红艳煞'),
])
def test_day_stem_reference_tables_match_selected_asset(section: str, name: str) -> None:
    md = (ROOT / 'references/19-shensha.md').read_text(encoding='utf-8')
    body = md.split('### ' + section + ' ', 1)[1].split('\n### ', 1)[0]
    parsed = {}
    for stems, branches in re.findall(
            r'\|\s*([甲乙丙丁戊己庚辛壬癸、]+)\s*\|\s*([子丑寅卯辰巳午未申酉戌亥、]+)\s*\|', body):
        for stem in stems.split('、'):
            assert stem not in parsed, (name, stem)
            parsed[stem] = set(branches.split('、'))
    data = json.loads((ROOT / 'assets/shensha.json').read_text(encoding='utf-8'))
    asset = next(row['qi_fa_table'] for group in ('ji_shen', 'xiong_sha')
                 for row in data[group] if row['name'] == name)
    assert set(parsed) == set('甲乙丙丁戊己庚辛壬癸')
    assert parsed == {key: set(value if isinstance(value, list) else [value])
                      for key, value in asset.items()}
