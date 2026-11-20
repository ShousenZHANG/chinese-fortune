"""三元男女九宫合卦, 按《选择要略》卷二 (xuanze:c002:p0108-p0132), 连同《协纪辨方书》的驳议.

起宫: 上元甲子男七女五、中元男一女二、下元男四女八; 男逆行、女顺行, 从本宫起甲子
数到生年; 中五宫男寄坤二、女寄艮八 (p0109-p0113)。合卦: 以男宫之卦为本宫,
「一上生气，一中天医，依次变之」(p0113), p0115 两例 (下元戊辰男离、庚午女艮合成
五鬼) 由此复现。p0116-p0131 的数字速查表有转录错 (生气「二八」重出缺「八二」,
「九七」同见于天医与游魂), 只作对照, 不据以计算。

三元按正统九年甲子 (1444) 为下元起推 (p0114 注), 即 1864 上元、1924 中元、1984 下元。
《协纪辨方书》卷三十六 (xieji:c036:p0016) 驳此法: 三元九宫本是年九星入中宫, 不是人的
命宫; 游年变卦是地理家法; 世传九星又误以上元为中元, 「宫已非其宫而卦亦非其卦」。

用户点名《协纪辨方书》时走另一条路 (round 11 FIX-11-15, N10): 卷三十五录《三元經》男命
上元甲子起坎一、中元起巽四、下元起兑七逆行, 女命上元起中五、中元起坤二、下元起艮八顺行
(xieji:c035:p0016); 卷八以康熙二十三年甲子 (1684) 为上元 (xieji:c008:p0024), 与 1864 同一
一百八十年周期。《选择要略》男命的上七中一下四, 正是卷三十五所记俗误「起兑七中元起坎一下元
起巽四」(xieji:c035:p0017; 「上元」二字原文此处没有)。合卦用卷二小游年 (xieji:c002:p0021、p0023): 自上而中而下
而复中次第翻卦, 依次贪狼、巨门、禄存、文曲、廉贞、武曲、破军、辅弼。卷二同段记地理家与选择
家对各星吉凶取法不同, 本书又在卷三十六驳合婚, 所以这条路径不给吉凶等级。落中五宫时卷三十五
没写寄宫, 这条路径就停在那里, 不借《选择要略》的寄坤寄艮补上。
"""
from __future__ import annotations

from utils import DIZHI, TIANGAN

SOURCE_IDS = ('xuanze:c002:p0109', 'xuanze:c002:p0110', 'xuanze:c002:p0111', 'xuanze:c002:p0113',
              'xuanze:c002:p0115', 'xuanze:c002:p0132')
XIEJI_IDS = ('xieji:c035:p0016', 'xieji:c008:p0024', 'xieji:c002:p0021', 'xieji:c002:p0023', 'xieji:c036:p0016')
DISSENT = {'passage_id': 'xieji:c036:p0016',
           'quote': '三元九宫者乃年九星入中宫之一星非謂其年之生命即在是宫也',
           'also': '又以地理家遊年變卦之法兩宫相配以定吉凶……又況世傳九星誤以上元為中元……則宫已非其宫而卦亦非其卦'}
BASE_YEAR = 1864                      # 上元甲子
START = {'xuanze': {'male': (7, 1, 4), 'female': (5, 2, 8)},
         'xieji': {'male': (1, 4, 7), 'female': (5, 2, 8)}}
YUAN = ('上元', '中元', '下元')
# 洛书后天八卦: 宫数 -> 卦, 卦以自下而上三爻 (1 阳 0 阴) 表示。
TRIGRAM = {1: ('坎', (0, 1, 0)), 2: ('坤', (0, 0, 0)), 3: ('震', (1, 0, 0)), 4: ('巽', (0, 1, 1)),
           6: ('乾', (1, 1, 1)), 7: ('兑', (1, 1, 0)), 8: ('艮', (0, 0, 1)), 9: ('离', (1, 0, 1))}
# 「一上生气，一中天医」依次: 上、中、下、中、上、中、下、中 (变回本宫为归魂)。
STEPS = (('生气', 2), ('天医', 1), ('绝体', 0), ('游魂', 1), ('五鬼', 2), ('福德', 1), ('绝命', 0), ('归魂', 1))
# 《协纪》卷二小游年的星名，与上面八步一一对应 (xieji:c002:p0021)。
STAR = {'生气': '贪狼', '天医': '巨门', '绝体': '禄存', '游魂': '文曲', '五鬼': '廉贞', '福德': '武曲', '绝命': '破军',
        '归魂': '辅弼'}
XIEJI_GRADES = '地理家從龍上起以貪狼巨門武曲廉貞為吉禄存文曲破軍輔弼為凶選擇家從向上起以貪狼巨門武曲文曲為吉禄存廉貞破軍輔弼為凶'
# p0132 原文的分等, 照录。
GRADE = {'生气': '上吉', '天医': '上吉', '福德': '上吉', '绝体': '中平', '游魂': '中平', '归魂': '中平',
         '五鬼': '凶', '绝命': '凶'}
GRADE_QUOTE = {'上吉': '合得生氣，天醫，福德爲上吉', '中平': '如遇絶體，遊魂，歸魂爲中平',
               '凶': '若遇五歸於男，女多生撓境，口舌相連，遇絶命，禍必深重'}
DIGITS = '〇一二三四五六七八九'


def year_of_pillar(year_pillar: str, birth_year: int) -> int:
    """The 立春 year whose 干支 is the year pillar (the birth year or the one before)."""
    for year in (birth_year, birth_year - 1):
        if TIANGAN[(year - 4) % 10] + DIZHI[(year - 4) % 12] == year_pillar:
            return year
    raise ValueError(f'年柱 {year_pillar} 与出生年 {birth_year} 对不上')


def palace(year: int, gender: str, source: str = 'xuanze') -> dict:
    offset = (year - BASE_YEAR) % 180
    yuan, index = offset // 60, offset % 60
    start = START[source][gender][yuan]
    step = -index if gender == 'male' else index
    number = (start - 1 + step) % 9 + 1
    centre = number == 5
    used: int | None = number
    if centre:
        # 《选择要略》中五男寄坤二、女寄艮八; 《协纪》卷三十五没写寄宫 (FIX-11-15)。
        used = (2 if gender == 'male' else 8) if source == 'xuanze' else None
    return {'year': year, 'yuan': YUAN[yuan], 'epoch_year': year - index, 'start_palace': start,
            'direction': '逆' if gender == 'male' else '顺', 'steps': index, 'counted_palace': number,
            'palace': used, 'trigram': TRIGRAM[used][0] if used else None, 'centre_moved': centre}


def derivation(p: dict, who: str, year_pillar: str) -> str:
    """「下元（1984 年甲子起）男从四宫起甲子，逆数 8 步到壬申，落中五宫，寄坤二」: the count a reader can redo by hand."""
    if p['palace'] is None:
        landed = '落中五宫'
    elif p['centre_moved']:
        landed = f"落中五宫，{who}寄{p['trigram']}{DIGITS[p['palace']]}"
    else:
        landed = f"落{p['trigram']}{DIGITS[p['palace']]}宫"
    return (f"{p['yuan']}（{p['epoch_year']} 年甲子起）{who}从{DIGITS[p['start_palace']]}宫起甲子，"
            f"{p['direction']}数 {p['steps']} 步到{year_pillar}，{landed}")


def relation(male_palace: int, female_palace: int) -> str:
    lines = list(TRIGRAM[male_palace][1])
    target = TRIGRAM[female_palace][1]
    for name, line in STEPS:
        lines[line] ^= 1
        if tuple(lines) == target:
            return name
    raise AssertionError('游年变卦八步必回本宫')


def _dissent_say() -> str:
    return ('《协纪辨方书》卷三十六驳此法：三元九宫本是年九星入中宫、不是人的命宫，世传九星又误以上元为中元'
            '（xieji:c036:p0016）')


def _xieji(male: dict, female: dict, m: dict, f: dict) -> dict:
    counted = (f"男年柱{male['year_pillar']}（{m['year']} 年立春起），{derivation(m, '男', male['year_pillar'])}；"
               f"女年柱{female['year_pillar']}（{f['year']} 年立春起），{derivation(f, '女', female['year_pillar'])}")
    head = '三元九宫合婚（《协纪辨方书》卷三十五所录《三元經》起法，xieji:c035:p0016；上元以康熙二十三年甲子为始，xieji:c008:p0024）：'
    base = {'method': '三元男女九宫合卦', 'source': 'xieji', 'male': m, 'female': f, 'source_ids': list(XIEJI_IDS),
            'dissent': DISSENT}
    if m['palace'] is None or f['palace'] is None:
        who = '、'.join(w for w, p in (('男', m), ('女', f)) if p['palace'] is None)
        reason = f'{who}数到中五宫；卷三十五没写落中五时寄哪一宫，这条路径算不下去，不借《选择要略》的寄坤、寄艮补上。'
        return {**base, 'status': 'unsupported', 'reason': reason,
                'say': f'{head}{counted}。{reason}{_dissent_say()}。'}
    name = relation(m['palace'], f['palace'])
    say = (f"{head}{counted}；按卷二小游年（xieji:c002:p0021、p0023）以男宫之卦为本宫，自上而中而下次第翻卦，"
           f"{m['trigram']}翻到{f['trigram']}在第 {[s for s, _ in STEPS].index(name) + 1} 步，为{STAR[name]}（{name}）。"
           f"卷二同段记地理家、选择家对各星吉凶取法不同，所以不合成吉凶；{_dissent_say()}。"
           "《选择要略》男命上元七、中元一、下元四的起法，正是协纪所说的俗误。"
           "《协纪辨方书》卷三十五原文作「起兑七中元起坎一下元起巽四」（xieji:c035:p0017），两条路径结果可以不同。")
    return {**base, 'status': 'computed', 'relation': name, 'star': STAR[name], 'grades_note': XIEJI_GRADES,
            'say': say}


def match(male: dict, female: dict, source: str = 'xuanze') -> dict:
    """male/female: {'year_pillar', 'birth_year'}; ``source``: 'xuanze' 《选择要略》 or 'xieji' 《协纪辨方书》."""
    m = palace(year_of_pillar(male['year_pillar'], male['birth_year']), 'male', source)
    f = palace(year_of_pillar(female['year_pillar'], female['birth_year']), 'female', source)
    if source == 'xieji':
        return _xieji(male, female, m, f)
    name = relation(m['palace'], f['palace'])
    grade = GRADE[name]
    say = (f"三元九宫合卦（《选择要略》）：男年柱{male['year_pillar']}（{m['year']} 年立春起），"
           f"{derivation(m, '男', male['year_pillar'])}；女年柱{female['year_pillar']}（{f['year']} 年立春起），"
           f"{derivation(f, '女', female['year_pillar'])}；以男宫之卦为本宫变卦，合成{name}，"
           f"原文「{GRADE_QUOTE[grade]}」（xuanze:c002:p0132）。{_dissent_say()}；两说并列，不合成婚配结论。")
    return {'method': '三元男女九宫合卦', 'source': 'xuanze', 'status': 'computed', 'male': m, 'female': f,
            'relation': name, 'book_grade': grade, 'book_quote': GRADE_QUOTE[grade], 'source_ids': list(SOURCE_IDS),
            'dissent': DISSENT, 'say': say,
            'table_note': '原书 p0116-p0131 速查表有转录错（生气「二八」重出、「九七」两见），按 p0113 变卦法计算；'
                          'p0115 两例复现。'}
