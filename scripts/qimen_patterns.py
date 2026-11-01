"""奇门格局：照《遁甲演义》卷二（dunjia:c002）原文条件逐条判，分七类。

九遁（p0003–p0015）、吉格（飞鸟跌穴 p0006、青龙返首 p0007、玉女守门 p0008、三奇得使 p0009）、
诈假（p0021）、十干凶格（p0025–p0038）、时日凶格（五不遇时 p0041、三奇入墓 p0042、六仪击刑 p0043）、
伏吟反吟（p0044、p0045）、门迫（p0046）。

只在 qimen_zhuanpan.plate() 的转盘上判。原文「又曰」「一云」并列的说法记为 variant，与正条分开。
原文写不清的条目不判，列在 NOT_COMPUTED。kind 只转述原文给的吉凶方向，不合成总评。
quote 照录四库本原字（含异体），供逐字核对。
"""
from __future__ import annotations

from dataclasses import dataclass

from qimen_tables import PALACE_INFO
from qimen_zhuanpan import RING, _ring, hidden_stem
from utils import WUXING_KE

JI3 = frozenset({'开门', '休门', '生门'})
SAN_QI = frozenset({'乙', '丙', '丁'})
DING_JI_GUI = frozenset({'丁', '己', '癸'})
DOOR_WUXING = {'休门': '水', '生门': '土', '伤门': '木', '杜门': '木', '景门': '火', '死门': '土', '惊门': '金',
               '开门': '金'}
# p0046 举例的吉门被迫为开、休、生、景四门，凶门被迫为伤、杜、死、惊。
GOOD_DOORS = frozenset({'开门', '休门', '生门', '景门'})
WU_BU_YU = {'甲': '庚午', '乙': '辛巳', '丙': '壬辰', '丁': '癸卯', '戊': '甲寅', '己': '乙丑', '庚': '丙子', '辛': '丁酉',
            '壬': '戊申', '癸': '己未'}
TOMB_PALACE = {'乙': 2, '丙': 6, '丁': 8}
TOMB_HOURS = frozenset({'丙戌', '丁丑', '壬辰', '癸未', '戊戌', '己丑'})
XING_PALACE = {'甲子': 3, '甲戌': 2, '甲申': 8, '甲午': 9, '甲辰': 4, '甲寅': 4}
OPPOSITE = 4  # 八宫环上对冲相隔四宫
LABEL = {'year': '年', 'month': '月', 'month_shuo': '月朔', 'day': '日', 'hour': '时'}

NOT_COMPUTED = [
    {'name': '人假', 'passage_id': 'dunjia:c002:p0021',
     'reason': '「惊门合六合下临九天」：六合与九天同为八神，一宫不能并临，文义不明'},
    {'name': '三奇受制', 'passage_id': 'dunjia:c002:p0040', 'reason': '「乙奇临乾惊门庚辛囚死」句读与条件不明'},
    {'name': '天网四张', 'passage_id': 'dunjia:c002:p0046',
     'reason': '「天上六癸所加之下」与「凡六癸之时」两说并列，适用时辰范围不明'},
    {'name': '天三门、地四户、地私门、天马、亭亭白奸', 'passage_id': 'dunjia:c002:p0016',
     'reason': '依月将加时、贵人起例，属六壬式盘方位，不在这张转盘上'},
]


@dataclass(frozen=True)
class Cond:
    heaven: frozenset[str] | None = None
    earth: frozenset[str] | None = None
    doors: frozenset[str] | None = None
    god: str | None = None
    palace: int | None = None


def _c(heaven: str | None = None, earth: str | None = None, doors: frozenset[str] | str | None = None,
       god: str | None = None, palace: int | None = None) -> Cond:
    return Cond(frozenset(heaven) if heaven else None, frozenset(earth) if earth else None,
                frozenset({doors}) if isinstance(doors, str) else doors, god, palace)


P = 'dunjia:c002:'
# (名, 类, passage, 原文, variant, 条件)
SPECS: list[tuple[str, str, str, str, bool, Cond]] = [
    ('天遁', '九遁', P + 'p0003', '生門六丙合六丁', False, _c('丙', '丁', '生门')),
    ('地遁', '九遁', P + 'p0004', '開門六乙合六己', False, _c('乙', '己', '开门')),
    ('人遁', '九遁', P + 'p0005', '休門六丁共太隂', False, _c('丁', None, '休门', '太阴')),
    ('神遁', '九遁', P + 'p0010', '天上六丙合九天再合生門', False, _c('丙', None, '生门', '九天')),
    ('鬼遁', '九遁', P + 'p0011', '天上六乙合九地臨於杜門', False, _c('乙', None, '杜门', '九地')),
    ('鬼遁', '九遁', P + 'p0011', '丁竒與休門相合下臨九地之位', True, _c('丁', None, '休门', '九地')),
    ('鬼遁', '九遁', P + 'p0011', '乙竒與開門相合下臨九地之位', True, _c('乙', None, '开门', '九地')),
    ('风遁', '九遁', P + 'p0012', '天上六乙合三門下臨巽宫', False, _c('乙', None, JI3, palace=4)),
    ('风遁', '九遁', P + 'p0012', '丙竒與開門相合下臨巽宫', True, _c('丙', None, '开门', palace=4)),
    ('风遁', '九遁', P + 'p0012', '三吉門臨地盤乙竒', True, _c(None, '乙', JI3)),
    ('风遁', '九遁', P + 'p0012', '開休生三門與六丁星竒相合下臨地下六己', True, _c('丁', '己', JI3)),
    ('风遁', '九遁', P + 'p0012', '辛儀與竒門下臨六乙', True, _c('辛', '乙', JI3)),
    ('风遁', '九遁', P + 'p0012', '丙竒開門相合下臨坤宫', True, _c('丙', None, '开门', palace=2)),
    ('云遁', '九遁', P + 'p0013', '天上六乙合六辛臨三吉門', False, _c('乙', '辛', JI3)),
    ('云遁', '九遁', P + 'p0013', '乙竒與開門合下臨坤宫', True, _c('乙', None, '开门', palace=2)),
    ('龙遁', '九遁', P + 'p0014', '日竒合休於坎宫', False, _c('乙', None, '休门', palace=1)),
    ('龙遁', '九遁', P + 'p0014', '乙竒與休門相合下臨六癸', True, _c('乙', '癸', '休门')),
    ('虎遁', '九遁', P + 'p0015', '天上六乙合六辛臨休到艮', False, _c('乙', '辛', '休门', palace=8)),
    ('虎遁', '九遁', P + 'p0015', '乙竒與生門臨六辛', True, _c('乙', '辛', '生门')),
    ('虎遁', '九遁', P + 'p0015', '辛儀合生臨艮', True, _c('辛', None, '生门', palace=8)),
    ('真诈', '诈假', P + 'p0021', '若三門合三竒下臨太隂宫名曰真詐', False, _c('乙丙丁', None, JI3, '太阴')),
    ('重诈', '诈假', P + 'p0021', '若三門合三竒下臨九地宫名曰重詐', False, _c('乙丙丁', None, JI3, '九地')),
    ('休诈', '诈假', P + 'p0021', '若三門合三竒下臨六合宫名曰休詐', False, _c('乙丙丁', None, JI3, '六合')),
    ('天假', '诈假', P + 'p0021', '若景門合乙丙丁臨九天名曰天假', False, _c('乙丙丁', None, '景门', '九天')),
    ('地假', '诈假', P + 'p0021', '若杜門合丁己癸下臨九地名曰地假', False, _c('丁己癸', None, '杜门', '九地')),
    ('神假', '诈假', P + 'p0021', '若傷門合丁己癸下臨九地名曰神假', False, _c('丁己癸', None, '伤门', '九地')),
    ('鬼假', '诈假', P + 'p0021', '若死門合丁己癸臨九地名曰鬼假', False, _c('丁己癸', None, '死门', '九地')),
    ('青龙逃走', '十干凶格', P + 'p0025', '六乙加辛龍逃走', False, _c('乙', '辛')),
    ('青龙逃走', '十干凶格', P + 'p0025', '又曰乙加庚亦是', True, _c('乙', '庚')),
    ('白虎猖狂', '十干凶格', P + 'p0026', '六辛加乙虎猖狂', False, _c('辛', '乙')),
    ('朱雀投江', '十干凶格', P + 'p0027', '六丁加癸雀入江', False, _c('丁', '癸')),
    ('螣蛇夭矫', '十干凶格', P + 'p0028', '六癸加丁蛇跃蹻', False, _c('癸', '丁')),
    ('大格', '十干凶格', P + 'p0029', '庚加癸兮為大格', False, _c('庚', '癸')),
    ('小格', '十干凶格', P + 'p0030', '六庚加六壬謂之小格', False, _c('庚', '壬')),
    ('刑格', '十干凶格', P + 'p0031', '六庚加六己為刑格', False, _c('庚', '己')),
    ('荧入太白', '十干凶格', P + 'p0033', '六丙加庚熒入白', False, _c('丙', '庚')),
    ('太白入荧', '十干凶格', P + 'p0034', '六庚加丙白入熒', False, _c('庚', '丙')),
]
KIND = {'九遁': '吉', '吉格': '吉', '诈假': '吉', '十干凶格': '凶', '时日凶格': '凶', '伏吟反吟': '凶', '门迫': '凶'}
# p0009：三奇得使与青龙逃走、荧入太白、朱雀投江重合时「尚有微疵」，本旬直符同临方可用。
FLAWED_USE = {('乙', '辛'), ('丙', '庚'), ('丁', '癸')}
USE_PAIRS = [('乙', '己'), ('乙', '辛'), ('丙', '戊'), ('丙', '庚'), ('丁', '壬'), ('丁', '癸')]


def _hit(name: str, category: str, passage_id: str, quote: str, palace: int | None, evidence: str,
         variant: bool = False, note: str | None = None) -> dict:
    row = {'name': name, 'category': category, 'kind': KIND[category], 'palace': palace, 'evidence': evidence,
           'passage_id': passage_id, 'quote': quote, 'variant': variant}
    if note:
        row['note'] = note
    return row


def _cell(pl: dict, p: int) -> str:
    return (f"{p}宫 天盘{'、'.join(pl['heaven'][p])} 地盘{'、'.join(pl['earth'][p])} "
            f"{pl['doors'][p]} {pl['gods'][p]}")


def _matches(pl: dict, p: int, c: Cond) -> bool:
    return ((c.heaven is None or bool(c.heaven & set(pl['heaven'][p])))
            and (c.earth is None or bool(c.earth & set(pl['earth'][p])))
            and (c.doors is None or pl['doors'][p] in c.doors)
            and (c.god is None or pl['gods'][p] == c.god)
            and (c.palace is None or c.palace == p))


def _over(pl: dict, top: str, bottom: str) -> list[int]:
    return [p for p in RING if top in pl['heaven'][p] and bottom in pl['earth'][p]]


def _spec_hits(pl: dict) -> list[dict]:
    return [_hit(name, cat, pid, quote, p, _cell(pl, p), variant)
            for name, cat, pid, quote, variant, cond in SPECS for p in RING if _matches(pl, p, cond)]


def _good_hits(pl: dict) -> list[dict]:
    yi, hits = pl['xun_yi'], []
    for p in _over(pl, '丙', yi):
        hits.append(_hit('飞鸟跌穴', '吉格', P + 'p0006', '天盤丙竒加地盤本時甲旬頭也', p, _cell(pl, p)))
    for p in _over(pl, yi, '丙'):
        hits.append(_hit('青龙返首', '吉格', P + 'p0007', '甲加丙兮龍囘首', p, _cell(pl, p)))
    door_palace = pl['zhi_shi']['palace']
    if '丁' in pl['earth'][door_palace]:
        hits.append(_hit('玉女守门', '吉格', P + 'p0008', '玉女守門者謂丁為玉女而㑹天乙直使之門也', door_palace,
                         f"直使{pl['zhi_shi']['door']}临{door_palace}宫地盘丁"))
    for qi, yi_stem in USE_PAIRS:
        for p in _over(pl, qi, yi_stem):
            flawed = (qi, yi_stem) in FLAWED_USE and p != pl['zhi_fu']['palace']
            hits.append(_hit('三奇得使', '吉格', P + 'p0009', '乙為使者乙竒加甲戌甲午丙為使者丙竒加甲子甲申也',
                             p, _cell(pl, p),
                             note='同时成凶格，原文称「尚有㣲疵不吉」，本旬直符未同临' if flawed else None))
    return hits


def _stem_targets(pl: dict, gz: dict) -> list[dict]:
    """庚加年、月朔、日、时干；丙加年月日时干；日干加庚；庚加直符；直符加庚。"""
    hits = []
    targets = [('岁格', 'year', P + 'p0030', '六庚加當年太歲之干名曰歲格'),
               ('月格', 'month_shuo', P + 'p0030', '六庚加月朔格為凶時也'),
               ('伏干格', 'day', P + 'p0035', '庚加日干為伏干'),
               ('时格', 'hour', P + 'p0030', '六庚加本時干者為時格')]
    for name, key, pid, quote in targets:
        if not gz.get(key):
            continue
        stem = hidden_stem(gz[key])
        for p in _over(pl, '庚', stem):
            note = '原文 p0030 又名日干格' if name == '伏干格' else None
            hits.append(_hit(name, '十干凶格', pid, quote, p, f"天盘庚加{LABEL[key]}干{stem}：{_cell(pl, p)}", note=note))
    for key in ('year', 'month', 'day', 'hour'):
        if gz.get(key):
            stem = hidden_stem(gz[key])
            for p in _over(pl, '丙', stem):
                hits.append(_hit('勃格', '十干凶格', P + 'p0032', '天上六丙加年月日時之干', p,
                                 f"天盘丙加{LABEL[key]}干{stem}：{_cell(pl, p)}"))
    if gz.get('day'):
        for p in _over(pl, hidden_stem(gz['day']), '庚'):
            hits.append(_hit('飞干格', '十干凶格', P + 'p0036', '日干加庚飛干格', p, _cell(pl, p)))
    home = _ring(pl['zhi_fu']['origin_palace'])
    if '庚' in pl['heaven'][home]:
        hits.append(_hit('天乙伏宫格', '十干凶格', P + 'p0037', '六庚加直符名為天乙伏宫格', home,
                         f"天盘庚临地盘直符{home}宫"))
    zf = pl['zhi_fu']['palace']
    if '庚' in pl['earth'][zf]:
        hits.append(_hit('天乙飞宫格', '十干凶格', P + 'p0038', '直符加六庚名天乙飛宫格', zf,
                         f"值符{pl['zhi_fu']['star']}临{zf}宫地盘庚"))
    return hits


def _time_hits(pl: dict, gz: dict) -> list[dict]:
    hits = []
    hour, day = gz.get('hour'), gz.get('day')
    if day and hour and WU_BU_YU[day[0]] == hour:
        hits.append(_hit('五不遇时', '时日凶格', P + 'p0041', '時干尅日干陽尅陽干隂尅隂干', None, f"{day[0]}日{hour}时"))
    for qi, tomb in TOMB_PALACE.items():
        if qi in pl['heaven'][tomb]:
            hits.append(_hit('三奇入墓', '时日凶格', P + 'p0042', '六乙日竒下臨二宫六丙月竒到六宫六丁星竒下臨八宫',
                             tomb, f"天盘{qi}临{tomb}宫"))
    if hour in TOMB_HOURS:
        hits.append(_hit('时干入墓', '时日凶格', P + 'p0042', '前六時干辰入墓亦不可用', None, f"{hour}时"))
    if XING_PALACE[pl['xun_head']] == pl['zhi_fu']['palace']:
        hits.append(_hit('六仪击刑', '时日凶格', P + 'p0043',
                         '甲子直符加三宫甲戌直符加二宫甲申直符加八宫甲午直符加九宫甲辰直符臨四宫甲寅直符臨四宫',
                         pl['zhi_fu']['palace'], f"{pl['xun_head']}直符临{pl['zhi_fu']['palace']}宫"))
    return hits


def _yin_hits(pl: dict) -> list[dict]:
    if pl['star_shift'] == 0:
        both = '，门亦伏吟（门符皆伏吟）' if pl['door_shift'] == 0 else ''
        return [_hit('伏吟', '伏吟反吟', P + 'p0044', '九星仍在本宫不動謂之伏吟', None, '九星各在本宫' + both)]
    if pl['star_shift'] == OPPOSITE:
        return [_hit('反吟', '伏吟反吟', P + 'p0045', '凡星符對沖皆反吟', None, '九星各临对冲之宫')]
    return []


def _door_hits(pl: dict) -> list[dict]:
    hits = []
    for p in RING:
        door = pl['doors'][p]
        if WUXING_KE[DOOR_WUXING[door]] == PALACE_INFO[p]['wuxing']:
            side = '吉门被迫，吉事不成' if door in GOOD_DOORS else '凶门被迫，凶事尤甚'
            hits.append(_hit('门迫', '门迫', P + 'p0046', '門制其宫是迫雄', p,
                             f"{door}（{DOOR_WUXING[door]}）克{p}宫（{PALACE_INFO[p]['wuxing']}）：{side}"))
    return hits


def detect(pl: dict, ganzhi: dict) -> list[dict]:
    """ganzhi: year/month/day/hour 干支，month_shuo 为本农历月初一日干支（缺则不判月格）。"""
    return (_spec_hits(pl) + _good_hits(pl) + _stem_targets(pl, ganzhi) + _time_hits(pl, ganzhi)
            + _yin_hits(pl) + _door_hits(pl))
