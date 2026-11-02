"""三元男女九宫合卦, 按《选择要略》卷二 (xuanze:c002:p0108-p0132), 连同《协纪辨方书》的驳议.

起宫: 上元甲子男七女五、中元男一女二、下元男四女八; 男逆行、女顺行, 从本宫起甲子
数到生年; 中五宫男寄坤二、女寄艮八 (p0109-p0113)。合卦: 以男宫之卦为本宫,
「一上生气，一中天医，依次变之」(p0113), p0115 两例 (下元戊辰男离、庚午女艮合成
五鬼) 由此复现。p0116-p0131 的数字速查表有转录错 (生气「二八」重出缺「八二」,
「九七」同见于天医与游魂), 只作对照, 不据以计算。

三元按正统九年甲子 (1444) 为下元起推 (p0114 注), 即 1864 上元、1924 中元、1984 下元。
《协纪辨方书》卷三十六 (xieji:c036:p0016) 驳此法: 三元九宫本是年九星入中宫, 不是人的
命宫; 游年变卦是地理家法; 世传九星又误以上元为中元, 「宫已非其宫而卦亦非其卦」。
"""
from __future__ import annotations

from utils import DIZHI, TIANGAN

SOURCE_IDS = ('xuanze:c002:p0109', 'xuanze:c002:p0110', 'xuanze:c002:p0111', 'xuanze:c002:p0113',
              'xuanze:c002:p0115', 'xuanze:c002:p0132')
DISSENT = {'passage_id': 'xieji:c036:p0016',
           'quote': '三元九宫者乃年九星入中宫之一星非謂其年之生命即在是宫也',
           'also': '又以地理家遊年變卦之法兩宫相配以定吉凶……又況世傳九星誤以上元為中元……則宫已非其宫而卦亦非其卦'}
BASE_YEAR = 1864                      # 上元甲子
START = {'male': (7, 1, 4), 'female': (5, 2, 8)}
YUAN = ('上元', '中元', '下元')
# 洛书后天八卦: 宫数 -> 卦, 卦以自下而上三爻 (1 阳 0 阴) 表示。
TRIGRAM = {1: ('坎', (0, 1, 0)), 2: ('坤', (0, 0, 0)), 3: ('震', (1, 0, 0)), 4: ('巽', (0, 1, 1)),
           6: ('乾', (1, 1, 1)), 7: ('兑', (1, 1, 0)), 8: ('艮', (0, 0, 1)), 9: ('离', (1, 0, 1))}
# 「一上生气，一中天医」依次: 上、中、下、中、上、中、下、中 (变回本宫为归魂)。
STEPS = (('生气', 2), ('天医', 1), ('绝体', 0), ('游魂', 1), ('五鬼', 2), ('福德', 1), ('绝命', 0), ('归魂', 1))
# p0132 原文的分等, 照录。
GRADE = {'生气': '上吉', '天医': '上吉', '福德': '上吉', '绝体': '中平', '游魂': '中平', '归魂': '中平',
         '五鬼': '凶', '绝命': '凶'}
GRADE_QUOTE = {'上吉': '合得生氣，天醫，福德爲上吉', '中平': '如遇絶體，遊魂，歸魂爲中平',
               '凶': '若遇五歸於男，女多生撓境，口舌相連，遇絶命，禍必深重'}


def year_of_pillar(year_pillar: str, birth_year: int) -> int:
    """The 立春 year whose 干支 is the year pillar (the birth year or the one before)."""
    for year in (birth_year, birth_year - 1):
        if TIANGAN[(year - 4) % 10] + DIZHI[(year - 4) % 12] == year_pillar:
            return year
    raise ValueError(f'年柱 {year_pillar} 与出生年 {birth_year} 对不上')


def palace(year: int, gender: str) -> dict:
    offset = (year - BASE_YEAR) % 180
    yuan, index = offset // 60, offset % 60
    start = START[gender][yuan]
    step = -index if gender == 'male' else index
    number = (start - 1 + step) % 9 + 1
    used = number if number != 5 else (2 if gender == 'male' else 8)
    return {'year': year, 'yuan': YUAN[yuan], 'counted_palace': number, 'palace': used,
            'trigram': TRIGRAM[used][0], 'centre_moved': number == 5}


def relation(male_palace: int, female_palace: int) -> str:
    lines = list(TRIGRAM[male_palace][1])
    target = TRIGRAM[female_palace][1]
    for name, line in STEPS:
        lines[line] ^= 1
        if tuple(lines) == target:
            return name
    raise AssertionError('游年变卦八步必回本宫')


def match(male: dict, female: dict) -> dict:
    """male/female: {'year_pillar', 'birth_year'}."""
    m = palace(year_of_pillar(male['year_pillar'], male['birth_year']), 'male')
    f = palace(year_of_pillar(female['year_pillar'], female['birth_year']), 'female')
    name = relation(m['palace'], f['palace'])
    grade = GRADE[name]
    moved = lambda p, who: f"（数到中五宫，{who}寄{p['trigram']}{p['palace']}）" if p['centre_moved'] else ''  # noqa: E731
    say = (f"三元九宫合卦（《选择要略》）：男年柱{male['year_pillar']}（{m['year']} 年立春起），属{m['yuan']}，"
           f"{m['palace']}宫{m['trigram']}{moved(m, '男')}；女年柱{female['year_pillar']}（{f['year']} 年立春起），属{f['yuan']}，"
           f"{f['palace']}宫{f['trigram']}{moved(f, '女')}；合成{name}，"
           f"原文「{GRADE_QUOTE[grade]}」（xuanze:c002:p0132）。《协纪辨方书》卷三十六驳此法："
           f"三元九宫本是年九星入中宫、不是人的命宫，世传九星又误以上元为中元（xieji:c036:p0016）；两说并列，不合成婚配结论。")
    return {'method': '三元男女九宫合卦', 'male': m, 'female': f, 'relation': name, 'book_grade': grade,
            'book_quote': GRADE_QUOTE[grade], 'source_ids': list(SOURCE_IDS), 'dissent': DISSENT, 'say': say,
            'table_note': '原书 p0116-p0131 速查表有转录错（生气「二八」重出、「九七」两见），按 p0113 变卦法计算；'
                          'p0115 两例复现。'}
