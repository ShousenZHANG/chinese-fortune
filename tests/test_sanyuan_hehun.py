"""R2: 三元男女九宫合卦 as 选择要略 lays it out, with 协纪辨方书's objection beside it."""
import re

from classical_search import get_passage
from sanyuan_hehun import TRIGRAM, match, palace, relation


def test_book_worked_examples():
    # p0115: 下元戊辰男 九宫离；下元庚午女 数到中五寄艮八；合成五鬼（两个方向都是）。
    assert (palace(1448, 'male')['palace'], palace(1450, 'female')['palace']) == (9, 8)
    assert palace(1450, 'female')['centre_moved'] and relation(9, 8) == relation(8, 9) == '五鬼'
    # p0113: 中元癸亥男五宫作二、下元甲子女八宫 -> 生气；中元戊午男一、壬戌女六 -> 游魂；癸亥女七与一宫男 -> 五鬼。
    assert palace(1983, 'male')['palace'] == 2 and palace(1984, 'female')['palace'] == 8 and relation(2, 8) == '生气'
    assert palace(1978, 'male')['palace'] == 1 and palace(1982, 'female')['palace'] == 6 and relation(1, 6) == '游魂'
    assert palace(1983, 'female')['palace'] == 7 and relation(1, 7) == '五鬼'


def test_algorithm_agrees_with_the_quick_table_except_its_typos():
    digits = dict(zip('一二三四六七八九', '12346789'))
    names = {'生氣': '生气', '天醫': '天医', '絶體': '绝体', '遊魂': '游魂', '五鬼': '五鬼', '福德': '福德', '絶命': '绝命',
             '歸魂': '归魂'}
    mismatches = []
    for n in range(116, 132, 2):
        head = get_passage(f'xuanze:c002:p{n:04d}')['text']
        name = names[head[:2]]
        text = head + get_passage(f'xuanze:c002:p{n + 1:04d}')['text']
        for a, b in re.findall('([一二三四六七八九])([一二三四六七八九])', text):
            if relation(int(digits[a]), int(digits[b])) != name:
                mismatches.append((name, a + b))
    # 生气「二八」重出处原应为「八二」；游魂「九七」原应为「九二」。
    assert sorted(mismatches) == [('游魂', '九七')]
    assert all(relation(a, b) == relation(b, a) for a in TRIGRAM for b in TRIGRAM)


def test_match_quotes_the_grade_and_the_dissent():
    out = match({'year_pillar': '己卯', 'birth_year': 2000}, {'year_pillar': '辛巳', 'birth_year': 2001})
    assert out['male']['year'] == 1999 and out['relation'] == '归魂' and out['book_grade'] == '中平'
    assert out['dissent']['passage_id'] == 'xieji:c036:p0016' and '协纪辨方书' in out['say']
    assert out['dissent']['quote'].replace('', '') in get_passage('xieji:c036:p0016')['text']
