"""相主: how a day's pillars treat the person's own birth year.

《协纪辨方书》卷三十三 chooses days for a person by the stem and branch of the
year they were born in, not by the day master:
「從來皆論生年不論生日，有論生日者非古法也」(xieji:c033:p0020). Every rule
here is a sentence of that passage; the positional tables (禄, 貴人, 驛馬,
長生, 羊刃) cite the passages that define them. Nothing is scored by number:
each day gets the grade the passage's own words give its strongest factor.

Grades, strongest wording first:
  大凶  天尅地衝                               「天尅地衝最凶」
  凶    天比地衝, the 納音 table, a clash the text calls 凶莫堪, 七煞 twice,
        or an item the text forbids 「多見」 seen in all three pillars
  小凶  a clash the text calls 略輕 / 止主是非
  大吉  命禄, 命貴人, 命食禄 (最吉), 合官 (貴格), 合財 (富格), 干支合命 (上上格)
  吉    比肩, 正印, 長生, 驛馬 (次之), 六合, 三合 (次之), 財官一點 (宜)
The 格 in the passage are whole sets of pillars (「己命見三己四己」 for 比肩上吉);
one day is one point, so 比肩 alone is 吉, not 上吉. A single 七煞 day is at
best 吉 when the year and month are not against the person, 平 otherwise
(「或年月利而干係七煞一㸃可也」).
  平    none of the above
A bad factor outranks any good one: the passage makes 「不衝命尅命」 the
condition for a good day.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from contracts import (
    DayRuleHit,
    Grade,
    PersonalAssessment,
    PersonalDay,
    PersonalFactor,
    PillarContext,
)
from utils import TIANGAN_WUXING, shi_shen

PASSAGE = 'xieji:c033:p0020'
STEMS = '甲乙丙丁戊己庚辛壬癸'
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
CALENDAR_ZONE = timezone(timedelta(hours=8))

# The passage's own sentences, verbatim (㸃 stands for the unencoded glyph the
# transcription marks 〔字形SK3295：㸃〕). tests/test_xiangzhu.py checks each.
QUOTES = {
    'method': '從來皆論生年不論生日有論生日者非古法也',
    'condition': '不衝命尅命而又補龍扶山則上上吉課也',
    'he_guan': '取乙與庚合合官格也',
    'he_cai': '蓋丁與壬合合財格也',
    'he_grade': '合官者貴格也合財者富格也',
    'tiandi_he': '支干合命愈為竒上上格也',
    'yin': '一印綬格宜正印忌梟印如甲命宜四癸乙命宜四壬之類',
    'xiao_yin': '梟印亦能生我多見則忌',
    'shang_shi': '若傷官食神洩氣多見則忌',
    'bi_jian': '比肩上吉如己命見三己四己是也',
    'jie_cai': '劫財凶如己命多見戊字是也',
    'chang_sheng': '一四長生格如壬生人用四申丙生人用四寅是也',
    'qi_sha': '七煞大能尅命忌用',
    'qi_sha_two': '若至二㸃必凶',
    'cai_guan': '不合則無情財與官俱宜一㸃二㸃',
    'lu_gui': '命禄與命貴人最吉馬次之乃病地也',
    'ma_chong': '馬有必不可用者如寅以申為馬四柱若用申字則衝寅命凶',
    'shi_lu': '命食禄最吉能催官禄乃本命食神之禄也',
    'chong': '一本命地支切忌四柱地支衝之若又天干尅命干者名天尅地衝最凶',
    'weight': '一太歳衝命最凶月次之日又次之時為輕',
    'tu_chong': '如辰戌丑未命遇衝不吉但略輕土衝土也',
    'dong_xi': '東衝西不動南衝北不移謂木不能傷金火不能尅水也亦略輕',
    'shi_fei': '如申酉命遇寅夘衝亥子命遇己午衝是也止主是非',
    'severe': '若北衝南命西衝東命則凶莫堪矣',
    'yang_ren': '凡本命羊刃四柱切忌多見如甲命忌夘字之類',
    'liu_he': '但主命喜與八字六合而三合次之',
    'tong_ji': '今選擇家通忌天尅地衝年月日時如甲子忌庚午之類並忌天比地衝年月日時如甲子忌甲午',
    'na_yin': '日納音尅化命納音而地支相衝者',
    'ben_ri': '今人忌本日何歟',
    'sha_condition': '或年月利而干係七煞一',
    'year_tu': '然太嵗衝之亦凶',
    'year_weight': '然亦以太嵗為重月次之',
}
# 选择要略 forbids the 本命日 for some 用事; 協紀 answers 「今人忌本日何歟」.
BEN_MING_RI_OTHER = ('xuanze:c003:p0607', '本命日及本命對衝日')

# 協紀 appends a table of the 納音-clash days «具表扵後»: each 生年 → the one
# day whose 納音 overcomes it and whose branch clashes (夘 normalised to 卯).
NA_YIN_CLASH = {
    '甲子': '戊午', '乙丑': '己未', '丙寅': '甲申', '丁卯': '乙酉', '戊辰': '庚戌', '己巳': '辛亥',
    '庚午': '壬子', '辛未': '癸丑', '壬申': '丙寅', '癸酉': '丁卯', '甲戌': '壬辰', '乙亥': '癸巳',
    '丙子': '庚午', '丁丑': '辛未', '戊寅': '庚申', '己卯': '辛酉', '庚辰': '甲戌', '辛巳': '乙亥',
    '壬午': '甲子', '癸未': '乙丑', '甲申': '戊寅', '乙酉': '己卯', '丙戌': '戊辰', '丁亥': '己巳',
    '戊子': '丙午', '己丑': '丁未', '庚寅': '壬申', '辛卯': '癸酉', '壬辰': '丙戌', '癸巳': '丁亥',
    '甲午': '戊子', '乙未': '己丑', '丙申': '甲寅', '丁酉': '乙卯', '戊戌': '庚辰', '己亥': '辛巳',
    '庚子': '壬午', '辛丑': '癸未', '壬寅': '丙申', '癸卯': '丁酉', '甲辰': '壬戌', '乙巳': '癸亥',
    '丙午': '庚子', '丁未': '辛丑', '戊申': '庚寅', '己酉': '辛卯', '庚戌': '甲辰', '辛亥': '乙巳',
    '壬子': '甲午', '癸丑': '乙未', '甲寅': '戊申', '乙卯': '己酉', '丙辰': '戊戌', '丁巳': '己亥',
    '戊午': '丙子', '己未': '丁丑', '庚申': '壬寅', '辛酉': '癸卯', '壬戌': '丙辰', '癸亥': '丁巳',
}

# Positional tables, each with the passage that states it.
TABLES = {
    # 「甲禄在寅，乙禄在卯，丙戊禄在巳，丁己禄在午，庚禄在申，辛禄在酉，壬禄在亥，癸禄在子。」
    'lu': ('yuanhai:c034:p0003', dict(zip(STEMS, '寅卯巳午巳午申酉亥子', strict=True))),
    # 三命通会「甲戊庚牛羊…六辛逢馬虎」, as reviewed in assets/shensha.json. 庚
    # is read two ways (see GUI_REN_CONTESTED) and is left out of this table.
    'gui_ren': ('sanming:c003:p0008', {'甲': '丑未', '戊': '丑未', '乙': '子申', '己': '子申',
                                       '丙': '亥酉', '丁': '亥酉', '壬': '卯巳', '癸': '卯巳', '辛': '午寅'}),
    # 「申子辰马在寅，寅午戌马在申，巳酉丑马在亥，亥卯未马在巳。」
    'yi_ma': ('yuanhai:c035:p0003', {**dict.fromkeys('申子辰', '寅'), **dict.fromkeys('寅午戌', '申'),
                                     **dict.fromkeys('巳酉丑', '亥'), **dict.fromkeys('亥卯未', '巳')}),
    # 「金生巳，木生亥，火生寅，水土生申」. 協紀 gives only yang examples
    # (壬申、丙寅); a yin stem's 長生 is read two ways, so it is not used.
    'chang_sheng': ('xuanze:c003:p0603', {'甲': '亥', '丙': '寅', '戊': '申', '庚': '巳', '壬': '申'}),
    # 三命通会: 羊刃是禄前一位，「惟甲丙戊庚壬五陽干有刃…陰干無刃」.
    'yang_ren': ('sanming:c005:p0075', {'甲': '卯', '丙': '午', '戊': '午', '庚': '酉', '壬': '子'}),
}
# references/26-precedence.md lists 天乙貴人 as an unresolved dispute: 三命通会
# 「甲戊庚牛羊」 against 渊海 「庚辛逢马虎」. They differ only for 庚, so a 庚
# year's 丑未午寅 days are named, not counted.
GUI_REN_CONTESTED = {'庚': (('sanming:c003:p0008', '丑未', '甲戊庚牛羊'),
                            ('yuanhai:c024:p0004', '午寅', '庚辛逢马虎'))}
# 子平真詮·論刑沖會合: 六沖 斜對, 三會 三方, 六合 並對.
BRANCH_SOURCE = 'ziping:c007:p0001'
LIU_HE = {frozenset(p) for p in ('子丑', '寅亥', '卯戌', '辰酉', '巳申', '午未')}
SAN_HE = ('申子辰', '寅午戌', '巳酉丑', '亥卯未')
WU_HE = {frozenset(p) for p in ('甲己', '乙庚', '丙辛', '丁壬', '戊癸')}
KE = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}

GRADES = ('大吉', '吉', '平', '小凶', '凶', '大凶')
# Where a grade places a surviving candidate; 凶 and 大凶 exclude it instead.
TIER = {'大吉': 1, '吉': 2, '平': 3, '小凶': 4}
LABELS = {
    'tian_ke_di_chong': '天克地冲', 'tian_bi_di_chong': '天比地冲', 'na_yin_chong': '纳音克冲',
    'chong': '冲命', 'chong_light': '冲命略轻', 'qi_sha_two': '七杀重见', 'qi_sha_one': '七杀一点',
    'jie_cai_many': '劫财多见', 'xiao_yin_many': '枭印多见', 'xie_qi_many': '食伤多见',
    'yang_ren_many': '羊刃多见', 'he_guan': '合官', 'he_cai': '合财', 'tian_di_he': '天地合',
    'ming_lu': '命禄', 'ming_gui': '命贵人', 'shi_lu': '食禄', 'bi_jian': '比肩', 'ben_ming_ri': '本命日',
    'zheng_yin': '正印', 'cai_guan': '财官', 'chang_sheng': '长生', 'yi_ma': '驿马', 'liu_he': '六合',
    'san_he': '三合', 'ming_gui_contested': '贵人两说',
}
WHO = {'day': '当天', 'month': '这个月', 'year': '这一年'}


def chong(a: str, b: str) -> bool:
    return (BRANCHES.index(a) - BRANCHES.index(b)) % 12 == 6


def _factor(rule: str, polarity: Any, grade: Grade, plain: str, quote: str, *,
            table: str | None = None, other: str | None = None) -> PersonalFactor:
    factor: PersonalFactor = {'rule': rule, 'label': LABELS[rule], 'polarity': polarity, 'grade': grade,
                              'plain': plain, 'quote': quote, 'passage_id': PASSAGE}
    if table:
        factor['table'] = table
    if other:
        factor['other'] = other
    return factor


def _addressed(factors: list[PersonalFactor], you: str) -> list[PersonalFactor]:
    """Name the person: 「你」 for one reader, their id when several are weighed."""
    if you == '你':
        return factors
    return [{**f, 'plain': f['plain'].replace('你', you)} for f in factors]


def _clash(birth: str, pillar: str, who: str) -> PersonalFactor | None:
    """The one clash factor for this pillar, strongest wording first."""
    y, z, d, b = birth[0], birth[1], pillar[0], pillar[1]
    if not chong(b, z):
        return None
    if KE[TIANGAN_WUXING[d]] == TIANGAN_WUXING[y]:
        return _factor('tian_ke_di_chong', 'bad', '大凶',
                       f'{who}的天干{d}克你出生年的天干{y}，地支{b}又冲你的年支{z}，协纪叫「天克地冲」，最凶',
                       QUOTES['chong'])
    if d == y:
        return _factor('tian_bi_di_chong', 'bad', '凶',
                       f'{who}的天干和你出生年的天干同为{y}，地支{b}却冲你的年支{z}（天比地冲），协纪说这是选择家通忌',
                       QUOTES['tong_ji'])
    if NA_YIN_CLASH.get(birth) == pillar:
        return _factor('na_yin_chong', 'bad', '凶',
                       f'协纪附表写明{birth}年生的人忌{pillar}：纳音克你的纳音，地支又相冲，是选择家通忌',
                       QUOTES['na_yin'])
    if z in '寅卯巳午':
        return _factor('chong', 'bad', '凶',
                       f'{who}的地支{b}冲你出生年的地支{z}；{z}年生的人被这样冲，协纪说「凶莫堪」',
                       QUOTES['severe'])
    why = '土冲土' if z in '辰戌丑未' else ('木伤不了金' if z in '申酉' else '火克不了水')
    return _factor('chong_light', 'bad', '小凶',
                   f'{who}的地支{b}冲你出生年的地支{z}，但{why}，协纪说这种冲略轻，主要是口舌是非',
                   QUOTES['tu_chong'] if z in '辰戌丑未' else QUOTES['shi_fei'])


def pillar_factors(birth: str, pillar: str, who: str = '当天') -> list[PersonalFactor]:
    """What one pillar does to the person born in year ``birth`` (e.g. 丁丑)."""
    y, z, d, b = birth[0], birth[1], pillar[0], pillar[1]
    found: list[PersonalFactor] = []
    clash = _clash(birth, pillar, who)
    if clash:
        found.append(clash)
    god = shi_shen(y, d)
    if frozenset((y, d)) in WU_HE:
        kind = 'he_guan' if god == '正官' else 'he_cai'
        name = '合官' if kind == 'he_guan' else '合财'
        found.append(_factor(kind, 'good', '大吉',
                             f'{who}的天干{d}和你出生年的天干{y}相合，{d}是{y}的{god}，协纪叫「{name}」，'
                             + ('是贵格' if kind == 'he_guan' else '是富格'),
                             QUOTES['he_grade']))
        if frozenset((z, b)) in LIU_HE:
            found.append(_factor('tian_di_he', 'good', '大吉',
                                 f'{who}的干支{pillar}和你的生年{birth}天干地支都相合，协纪说「支干合命愈为奇」，是上上格',
                                 QUOTES['tiandi_he']))
    elif god == '比肩' and not (clash and clash['rule'] == 'tian_bi_di_chong'):
        found.append(_factor('bi_jian', 'good', '吉',
                             f'{who}的天干和你出生年的天干同为{y}（比肩），协纪说比肩吉', QUOTES['bi_jian']))
        if pillar == birth:
            found.append(_factor('ben_ming_ri', 'note', '平',
                                 f'{who}的干支和你的生年同为{birth}（本命日）。《选择要略》有的事项忌本命日，'
                                 '协纪反驳「今人忌本日何歟」，本工具按协纪', QUOTES['ben_ri'],
                                 other=BEN_MING_RI_OTHER[0]))
    elif god == '正印':
        found.append(_factor('zheng_yin', 'good', '吉',
                             f'{who}的天干{d}生你出生年的天干{y}（正印），协纪说印绶宜正印', QUOTES['yin']))
    elif god == '七杀' and not clash:
        found.append(_factor('qi_sha_one', 'note', '平',
                             f'{who}的天干{d}是你出生年天干{y}的七杀，协纪说七杀忌用，只有一点尚可', QUOTES['qi_sha']))
    elif god in ('正官', '正财', '偏财'):
        found.append(_factor('cai_guan', 'good', '吉',
                             f'{who}的天干{d}是你出生年天干{y}的{god}，协纪说财与官一两点都相宜', QUOTES['cai_guan']))
    if clash:
        return found  # a clashing branch brings no 禄、貴人 or 馬 worth having
    lu_id, lu = TABLES['lu']
    if lu[y] == b:
        found.append(_factor('ming_lu', 'good', '大吉',
                             f'{who}的地支{b}是你出生年天干{y}的禄位（{y}禄在{b}），协纪说命禄最吉',
                             QUOTES['lu_gui'], table=lu_id))
    gui_id, gui = TABLES['gui_ren']
    if b in gui.get(y, ''):
        found.append(_factor('ming_gui', 'good', '大吉',
                             f'{who}的地支{b}是你出生年天干{y}的天乙贵人，协纪说命贵人最吉',
                             QUOTES['lu_gui'], table=gui_id))
    elif any(b in branches for _, branches, _ in GUI_REN_CONTESTED.get(y, ())):
        (a_id, a_branches, a_quote), (b_id, b_branches, b_quote) = GUI_REN_CONTESTED[y]
        found.append(_factor('ming_gui_contested', 'note', '平',
                             f'{who}的地支{b}算不算{y}的天乙贵人，两书不同：《三命通会》「{a_quote}」作{a_branches}，'
                             f'《渊海子平》「{b_quote}」作{b_branches}；两说并列，这一条不计入吉凶',
                             QUOTES['lu_gui'], table=a_id, other=b_id))
    food = next(s for s in STEMS if shi_shen(y, s) == '食神')
    if lu[food] == b:
        found.append(_factor('shi_lu', 'good', '大吉',
                             f'{who}的地支{b}是你出生年天干{y}的食神{food}的禄位，协纪说命食禄最吉',
                             QUOTES['shi_lu'], table=lu_id))
    sheng_id, sheng = TABLES['chang_sheng']
    if sheng.get(y) == b:
        found.append(_factor('chang_sheng', 'good', '吉',
                             f'{who}的地支{b}是你出生年天干{y}的长生之地，协纪有「四长生格」',
                             QUOTES['chang_sheng'], table=sheng_id))
    ma_id, ma = TABLES['yi_ma']
    if ma[z] == b:
        found.append(_factor('yi_ma', 'good', '吉',
                             f'{who}的地支{b}是你出生年地支{z}的驿马，协纪说马次于禄和贵人',
                             QUOTES['lu_gui'], table=ma_id))
    if frozenset((z, b)) in LIU_HE and not any(f['rule'] == 'tian_di_he' for f in found):
        found.append(_factor('liu_he', 'good', '吉',
                             f'{who}的地支{b}和你出生年的地支{z}六合，协纪说「主命喜与八字六合」',
                             QUOTES['liu_he'], table=BRANCH_SOURCE))
    elif b != z and any(z in g and b in g for g in SAN_HE):
        found.append(_factor('san_he', 'good', '吉',
                             f'{who}的地支{b}和你出生年的地支{z}三合，协纪说三合次于六合',
                             QUOTES['liu_he'], table=BRANCH_SOURCE))
    return found


def _repeats(birth: str, pillars: dict[str, str]) -> list[PersonalFactor]:
    """Items the passage allows once or twice but forbids when they pile up."""
    y = birth[0]
    stems = [pillars[k][0] for k in ('year', 'month', 'day') if k in pillars]
    branches = [pillars[k][1] for k in ('year', 'month', 'day') if k in pillars]
    gods = [shi_shen(y, s) for s in stems]
    found: list[PersonalFactor] = []
    sha = gods.count('七杀')
    if sha >= 2:
        found.append(_factor('qi_sha_two', 'bad', '凶',
                             f'你出生年天干{y}的七杀在年、月、日的天干里出现了{sha}次，协纪说七杀「若至二点必凶」',
                             QUOTES['qi_sha_two']))
    for rule, names, quote, word in (('jie_cai_many', ('劫财',), QUOTES['jie_cai'], '劫财'),
                                     ('xiao_yin_many', ('偏印',), QUOTES['xiao_yin'], '枭印'),
                                     ('xie_qi_many', ('食神', '伤官'), QUOTES['shang_shi'], '食伤')):
        if sum(g in names for g in gods) >= 3:
            found.append(_factor(rule, 'bad', '凶',
                                 f'年、月、日三个天干都是你的{word}，协纪说这类多见则忌', quote))
    blade = TABLES['yang_ren'][1].get(y)
    if blade and branches.count(blade) >= 3:
        found.append(_factor('yang_ren_many', 'bad', '凶',
                             f'年、月、日三个地支都是你的羊刃{blade}，协纪说本命羊刃切忌多见',
                             QUOTES['yang_ren'], table=TABLES['yang_ren'][0]))
    return found


def grade_of(factors: list[PersonalFactor]) -> Grade:
    bad = [f['grade'] for f in factors if f['polarity'] == 'bad']
    if bad:
        return max(bad, key=GRADES.index)
    good = [f['grade'] for f in factors if f['polarity'] == 'good']
    return min(good, key=GRADES.index) if good else '平'


def assess_day(birth: str, pillars: dict[str, str], you: str = '你') -> PersonalDay:
    """Grade the day pillar for this 生年; year and month are reported beside it.

    ``pillars`` holds 干支 strings for ``year``, ``month`` and ``day``. The
    passage weighs 「太歳衝命最凶，月次之，日又次之」, so the year and month
    keep their own grades in ``context`` instead of being folded into the day's.
    Only the repeat rules (七煞 twice, 多見) count across the three pillars,
    because the passage counts points over the whole set of pillars.
    """
    day = pillars['day']
    factors = pillar_factors(birth, day)
    repeats = _repeats(birth, pillars)
    # A repeat belongs to the day only when the day's own stem or branch is one of them.
    day_repeats = [f for f in repeats if _day_adds(birth, day, f['rule'])]
    if any(f['rule'] == 'qi_sha_two' for f in day_repeats):
        factors = [f for f in factors if f['rule'] != 'qi_sha_one']
    factors += day_repeats
    context: dict[str, PillarContext] = {}
    for key in ('year', 'month'):
        if key in pillars:
            found = pillar_factors(birth, pillars[key], WHO[key])
            if key == 'year':
                found = [_year_clash(f, birth) for f in found]
            context[key] = {'ganzhi': pillars[key], 'grade': grade_of(found), 'factors': found}
    grade = grade_of(factors)
    if any(f['rule'] == 'qi_sha_one' for f in factors):
        # 「或年月利而干係七煞一㸃可也」: one 七煞 is tolerable only beside a good year and month.
        against = any(GRADES.index(c['grade']) > GRADES.index('平') for c in context.values())
        cap: Grade = '平' if against else '吉'
        grade = max(grade, cap, key=GRADES.index)
    for entry in context.values():
        entry['factors'] = _addressed(entry['factors'], you)
    return {'birth_year': birth, 'day_ganzhi': day, 'grade': grade, 'factors': _addressed(factors, you),
            'context': context,
            'repeats_without_day': _addressed([f for f in repeats if f not in day_repeats], you)}


def worst(grades: list[Grade]) -> Grade:
    return max(grades, key=GRADES.index) if grades else '平'


def assess_people(people: list[tuple[str, str]], days: list[dict[str, str]]) -> PersonalAssessment:
    """Grade a span of days for everyone it is chosen for: the worst day, the worst person.

    ``people`` is (participant_id, 生年干支); ``days`` holds each touched day's
    year, month and day pillars. A span is only as good as its worst day,
    and a day chosen for two people must not be against either.
    """
    # One person may stand here twice, once per possible birth year.
    you = (lambda pid: '你') if len({pid for pid, _ in people}) == 1 else (lambda pid: pid)
    rows: list[Any] = [{'participant_id': pid, 'birth_year': birth,
             'days': [assess_day(birth, pillars, you(pid)) for pillars in days]}
            for pid, birth in people]
    grade = worst([d['grade'] for row in rows for d in row['days']])
    return {'grade': grade, 'people': rows}


def prohibitions(assessed: PersonalAssessment) -> list[DayRuleHit]:
    """The factors that exclude a span (凶, 大凶), shaped like the day rules."""
    hits: list[DayRuleHit] = []
    for row in assessed['people']:
        for day in row['days']:
            for f in day['factors']:
                if f['polarity'] == 'bad' and GRADES.index(f['grade']) >= GRADES.index('凶'):
                    single = len({p['participant_id'] for p in assessed['people']}) == 1
                    who = '你' if single else row['participant_id']
                    hits.append({'rule': 'xiangzhu_' + f['rule'], 'kind': f['label'], 'label': f['label'],
                                 'day_ganzhi': day['day_ganzhi'], 'passage_id': f['passage_id'],
                                 'quote': f['quote'], 'reason': f['plain'],
                                 'plain': f"{who}（{row['birth_year']}年生）的{f['label']}日：{f['plain']}",
                                 'participant_id': row['participant_id'], 'birth_year': row['birth_year']})
    return hits


def _year_clash(factor: PersonalFactor, birth: str) -> PersonalFactor:
    """A clash the passage calls light is still 凶 when the year itself makes it."""
    if factor['rule'] != 'chong_light':
        return factor
    quote = QUOTES['year_tu'] if birth[1] in '辰戌丑未' else QUOTES['year_weight']
    return {**factor, 'grade': '凶', 'quote': quote,
            'plain': factor['plain'].replace('协纪说这种冲略轻，主要是口舌是非',
                                             '协纪说这种冲平时略轻，但由太岁来冲仍然是凶')}


def _day_adds(birth: str, day: str, rule: str) -> bool:
    god = shi_shen(birth[0], day[0])
    return {'qi_sha_two': god == '七杀', 'jie_cai_many': god == '劫财', 'xiao_yin_many': god == '偏印',
            'xie_qi_many': god in ('食神', '伤官'),
            'yang_ren_many': TABLES['yang_ren'][1].get(birth[0]) == day[1]}[rule]


def date_pillars(day: date, zone: str) -> dict[str, str]:
    """Year, month and day pillars for a civil date, read at local noon.

    The day pillar follows the local date. Year and month follow the solar-term
    tables, which are fixed in UTC+8, so local noon is converted first. On the
    day a term begins, the morning can still belong to the previous month.
    """
    from lunar_python import Solar  # type: ignore
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=ZoneInfo(zone)).astimezone(CALENDAR_ZONE)
    term = Solar.fromYmdHms(noon.year, noon.month, noon.day, noon.hour, noon.minute, 0).getLunar()
    face = Solar.fromYmdHms(day.year, day.month, day.day, 12, 0, 0).getLunar()
    return {'year': term.getYearInGanZhiExact(), 'month': term.getMonthInGanZhiExact(),
            'day': face.getDayInGanZhiExact()}


def birth_years_of(natal: dict) -> list[str]:
    """The 生年干支 the chart allows: one when settled, the candidates when a
    birth near 立春 lacks the time that decides it, none otherwise."""
    settled = birth_year_of(natal)
    if settled:
        return [settled]
    year = (natal.get('four_pillars') or {}).get('year') or {}
    return [g for g in year.get('candidate_ganzhi') or []
            if isinstance(g, str) and len(g) == 2 and g[0] in STEMS and g[1] in BRANCHES]


def birth_year_of(natal: dict) -> str | None:
    """The person's 生年干支, or None when the year pillar is not settled."""
    year = (natal.get('four_pillars') or {}).get('year') or {}
    stem, branch = year.get('stem'), year.get('branch')
    if not (isinstance(stem, str) and isinstance(branch, str)) or len(stem + branch) != 2:
        return None
    return stem + branch if stem in STEMS and branch in BRANCHES else None


def _local_dates(start: str, end: str, zone: str) -> list[date]:
    """Civil dates a window covers; an end at local midnight is exclusive."""
    lo = datetime.fromisoformat(start).astimezone(ZoneInfo(zone))
    hi = datetime.fromisoformat(end).astimezone(ZoneInfo(zone))
    last = hi.date() - timedelta(days=1) if hi.time() == datetime.min.time() else hi.date()
    count = (last - lo.date()).days + 1
    return [lo.date() + timedelta(days=i) for i in range(max(count, 0))]


def personal_calendar(people: list[tuple[str, str]], start: str, end: str, zone: str,
                      unit: str = 'day') -> dict:
    """相主 over a period: each date, each solar-term month, or each year.

    ``unit`` follows the question's grain. A month is graded by its own
    month pillar and a year by its own year pillar, as the passage weighs
    「太歳衝命最凶，月次之，日又次之」; days use ``assess_people``.
    """
    dates = _local_dates(start, end, zone)
    if unit == 'year' or len(dates) > 1100:
        unit, dates = 'year', [date(y, 7, 1) for y in sorted({d.year for d in dates})]
    rows = [(d, date_pillars(d, zone)) for d in dates]
    entries: list[dict] = []
    if unit == 'day':
        for d, pillars in rows:
            assessed = assess_people(people, [pillars])
            entries.append({'date': d.isoformat(), 'label': f'{d.month}月{d.day}日', 'ganzhi': pillars['day'],
                            'pillars': pillars, 'grade': assessed['grade'], 'people': assessed['people']})
    else:
        key = 'month' if unit == 'month' else 'year'
        groups: dict[str, list[date]] = {}
        for d, pillars in rows:
            groups.setdefault(pillars[key], []).append(d)
        several_years = len({d.year for d in dates}) > 1
        for ganzhi, members in groups.items():
            per_person: list[dict[str, Any]] = []
            grades: list[Grade] = []
            for pid, birth in people:
                found = pillar_factors(birth, ganzhi, WHO[key])
                if key == 'year':
                    found = [_year_clash(f, birth) for f in found]
                grades.append(grade_of(found))
                per_person.append({'participant_id': pid, 'birth_year': birth, 'grade': grades[-1],
                                   'factors': _addressed(found, '你' if len(people) == 1 else pid)})
            first, last = members[0], members[-1]

            opening = (f'{first.year}年' if several_years else '') + f'{first.month}月{first.day}日'
            closing = (f'{last.year}年' if several_years and last.year != first.year else '') + f'{last.month}月{last.day}日'
            label, span = ((f'{first.year}年', f'{ganzhi}年') if key == 'year' else
                           (f'{ganzhi}月', f'{opening}至{closing}'))
            entries.append({'start': first.isoformat(), 'end': last.isoformat(), 'label': label, 'span': span,
                            'ganzhi': ganzhi, 'grade': worst(grades), 'people': per_person})
    return {'unit': unit, 'timezone': zone, 'entries': entries,
            'people': [{'participant_id': pid, 'birth_year': birth} for pid, birth in people],
            'basis': {'passage_id': PASSAGE, 'quote': QUOTES['method'],
                      'method': '相主：按本人出生年的干支看日子，不按日主'}}
