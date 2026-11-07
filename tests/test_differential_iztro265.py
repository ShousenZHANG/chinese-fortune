"""紫微对 iztro 2.6.5 逐宫差分（冻结样本，跑测试不需要 node）。

iztro 2.6.5 把晚子时（timeIndex 12）的日期归一化为次日，整张盘按次日排；本项目默认子正换日（日不进位），
--sect 1 子初换日与它相同。样本里早子、巳时按默认口径，晚子按 --sect 1，命宫、身宫、五行局、命主身主、
十四主星、六吉禄存羊陀与生年四化逐项一致。
"""
import json
from pathlib import Path

import pytest

DATA = json.loads((Path(__file__).parent / 'data/iztro_265_grid.json').read_text(encoding='utf-8'))
HOUR = {0: 0, 5: 10, 12: 23}


def _ours(row, sect):
    import ziwei_calc
    y, m, d = map(int, row['date'].split('-'))
    args = ziwei_calc.build_parser().parse_args([
        '--year', str(y), '--month', str(m), '--day', str(d), '--hour', str(HOUR[row['timeIndex']]),
        '--gender', 'male' if row['gender'] == '男' else 'female', '--time-standard', 'clock', '--sect', str(sect)])
    chart = ziwei_calc.calculate_ziwei(args)
    assert chart['ok']
    return chart


@pytest.mark.parametrize('row', DATA['charts'], ids=[f"{r['date']}-{r['timeIndex']}" for r in DATA['charts']])
def test_every_field_agrees_with_iztro_265(row):
    ours = _ours(row, 1 if row['timeIndex'] == 12 else 2)
    assert ours['ming_gong']['branch'] == row['ming'] and ours['shen_gong']['branch'] == row['shen']
    assert ours['wuxing_ju']['name'] == row['ju']
    assert (ours['ming_zhu'], ours['shen_zhu']) == (row['soul'], row['body'])
    assert {s: ours['main_stars_positions'][s] for s in row['main']} == row['main']
    aux = {**ours['lucky_stars_positions'], **ours['malefic_stars_positions']}
    assert {s: aux[s] for s in row['aux']} == row['aux']
    assert {h: ours['four_transformations_native'][h] for h in row['mutagen']} == row['mutagen']


def test_the_default_late_zi_convention_is_the_documented_difference():
    late = [r for r in DATA['charts'] if r['timeIndex'] == 12]
    moved = sum(_ours(r, 2)['main_stars_positions'] != r['main'] for r in late)
    assert moved > len(late) // 2       # 子正换日不进位，星曜按当日排，与 iztro 的次日不同
    note = _ours(late[0], 2)['sect']
    assert note['value'] == 2 and 'iztro' in note['reference'] and note['judged_by']
