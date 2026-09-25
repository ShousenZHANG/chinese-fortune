"""Day prohibitions that 《钦定协纪辨方书》 itself says no 吉神 can lift.

卷十「宜忌」 settles most days by weighing 吉神 against 凶煞 in six grades
(xieji:c010:p0110 「餘分為六等」); the settled result lives in the 月表 of
卷二十一至三十二, which the frozen transcription does not carry
(xieji:c021:p0004 「其神煞吉凶用事宜忌具於表」 with no table). So this module
implements no 宜 and no weighed 忌. It keeps only the rules whose own entry
says the prohibition stands even beside 德神 --- 「與併猶忌」「德神不能化解」.

Every rule carries three quotations, each a verbatim substring of its passage
(tests check them): how the day is found (起例), what it forbids (所忌), and
why no 吉神 lifts it. A scenario is affected only when its 用事 name appears in
the 所忌 quotation itself; nothing is mapped by analogy inside this module.
"""
from __future__ import annotations

BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
SEASONS = {'寅': '春', '卯': '春', '辰': '春', '巳': '夏', '午': '夏', '未': '夏',
           '申': '秋', '酉': '秋', '戌': '秋', '亥': '冬', '子': '冬', '丑': '冬'}
MONTH_NAMES = dict(zip('寅卯辰巳午未申酉戌亥子丑',
                       ('正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'), strict=True))

# 用事 name in 卷十 lists for each scenario. 卷十 uses the court list of 卷十一
# (御用六十七事); the common 出行/移徙 are given there as equal to 行幸/般移.
SCENARIO_TERMS = {'travel': '行幸', 'wedding': '嫁娶', 'moving': '般移', 'business': '開市'}
TERM_EQUIVALENCE = {
    'travel': {'passage_id': 'xieji:c011:p0026', 'quote': '出行同',
               'note': '卷十一行幸条注「出行同」；该条忌列末为「巳日」，与卷十「巳日忌出行」相合'},
    'moving': {'passage_id': 'xieji:c011:p0036', 'quote': '移徙同',
               'note': '卷十一般移条注「移徙同」'},
}
EVENT_WORDS = {'travel': '出行', 'wedding': '嫁娶', 'moving': '搬家（原文作般移）', 'business': '开市'}

_YUEPO_AVOID = ('忌祈福求嗣上册進表章頒詔施恩封拜詔命公卿招賢舉正直宣布政事慶賜賞賀宴㑹冠帶行幸遣使'
                '安撫邊境選將訓兵出師上官赴任臨政親民結婚姻納采問名嫁娶進人口般移安牀整容剃頭整手足甲'
                '裁製營建宫室修宫室繕城郭築隄防興造動土豎柱上梁修倉庫鼓鑄經絡醞釀開市立劵交易納財開倉庫'
                '出貨財修置產室開渠穿井安碓磑補垣塞穴修飾垣墻伐木栽種牧養納畜破土安葬啟攢')
_SIFEI_AVOID = ('忌祈福求嗣上册進表章頒詔施恩封拜詔命公卿招賢舉正直宣布政事慶賜賞賀宴㑹冠帶行幸遣使'
                '安撫邊境選將訓兵出師上官赴任臨政親民結婚姻納采問名嫁娶進人口般移安牀解除求醫療病裁製'
                '營建宫室修宫室繕城郭築隄防興造動土豎柱上梁修倉庫鼓鑄經絡醞釀開市立劵交易納財開倉庫'
                '出貨財修置産室開渠穿井安碓磑補垣塞穴修飾垣墻栽種牧養納畜破土安葬啟攢')
_SIJI_AVOID = '忌安撫邊境選將訓兵出師結婚姻納采問名嫁娶安葬'
_SIQIONG_MORE = '四窮又忌進人口修倉庫開市立劵交易納財開倉庫出貨財'
_SIJI_BINDING = '此八日皆以旺極為凶故德神不能化解'


def _source(passage_id: str, quote: str, role: str) -> dict:
    return {'passage_id': passage_id, 'quote': quote, 'role': role}


RULES: tuple[dict, ...] = (
    {'rule': 'yue_po', 'label': '月破',
     'qili': _source('xieji:c004:p0029', '月破者月建所衝之日也', '起例'),
     'avoid': (_source('xieji:c010:p0108', _YUEPO_AVOID, '所忌'),),
     'binding': _source('xieji:c010:p0109', '德神臨此失力不能為福故與併猶忌', '吉神不能化解')},
    {'rule': 'si_fei', 'label': '四廢',
     'qili': _source('xieji:c005:p0033', '春庚申辛酉夏壬子癸亥秋甲寅乙卯冬丙午丁巳', '起例'),
     'avoid': (_source('xieji:c010:p0139', _SIFEI_AVOID, '所忌'),),
     'binding': _source('xieji:c010:p0139', '與德合併猶忌與月破併諸事皆忌', '吉神不能化解')},
    {'rule': 'si_ji', 'label': '四忌',
     'qili': _source('xieji:c005:p0033', '四忌春甲子夏丙子秋庚子冬壬子', '起例'),
     'avoid': (_source('xieji:c010:p0139', _SIJI_AVOID, '所忌'),),
     'binding': _source('xieji:c010:p0139', _SIJI_BINDING, '吉神不能化解')},
    {'rule': 'si_qiong', 'label': '四窮',
     'qili': _source('xieji:c005:p0033', '春乙亥夏丁亥秋辛亥冬癸亥', '起例'),
     'avoid': (_source('xieji:c010:p0139', _SIJI_AVOID, '所忌'),
               _source('xieji:c010:p0139', _SIQIONG_MORE, '所忌')),
     'binding': _source('xieji:c010:p0139', _SIJI_BINDING, '吉神不能化解'),
     'exception': _source('xieji:c010:p0139', '惟正月乙亥與天願併止忌安撫邊境選將訓兵出師餘皆不忌', '例外')},
    {'rule': 'wang_wang', 'label': '往亡',
     'qili': _source('xieji:c006:p0059', '徃亡者正月在寅二月在巳三月在申四月在亥五月在夘六月在午'
                                         '七月在酉八月在子九月在辰十月在未十一月在戌十二月在丑', '起例'),
     'avoid': (_source('xieji:c010:p0154', '忌上册進表章頒詔詔命公卿招賢宣政事行幸遣使安撫邊境選將訓兵'
                                           '出師上官赴任臨政親民嫁娶進人口般移求醫療病捕捉畋獵取魚', '所忌'),),
     'binding': _source('xieji:c010:p0155', '雖值德合赦願不能無疑故與併猶忌', '吉神不能化解')},
    {'rule': 'gui_ji', 'label': '歸忌',
     'qili': _source('xieji:c006:p0058', '孟月丑仲月寅季月子', '起例'),
     # The header of this entry was lost in transcription; 卷十一般移条
     # (xieji:c011:p0036) lists 歸忌 among its 忌, which places it.
     'avoid': (_source('xieji:c010:p0152', '忌般移逺廻', '所忌'),),
     'binding': _source('xieji:c010:p0147', '土符地囊歸忌血忌倣此', '吉神不能化解')},
)

_SI_DAYS = {  # (四廢, 四忌, 四窮) per season, from the 起例 quoted in RULES.
    '春': (('庚申', '辛酉'), ('甲子',), ('乙亥',)),
    '夏': (('壬子', '癸亥'), ('丙子',), ('丁亥',)),
    '秋': (('甲寅', '乙卯'), ('庚子',), ('辛亥',)),
    '冬': (('丙午', '丁巳'), ('壬子',), ('癸亥',)),
}
_WANG_WANG = dict(zip('寅卯辰巳午未申酉戌亥子丑', '寅巳申亥卯午酉子辰未戌丑', strict=True))
_GUI_JI = {**dict.fromkeys('寅巳申亥', '丑'), **dict.fromkeys('卯午酉子', '寅'),
           **dict.fromkeys('辰未戌丑', '子')}


def _derivation(rule: str, day: str, month_branch: str) -> str | None:
    """Why ``day`` in the month of ``month_branch`` is this rule's day, or None."""
    season = SEASONS[month_branch]
    month = MONTH_NAMES[month_branch] + '月'
    if rule == 'yue_po':
        clash = BRANCHES[(BRANCHES.index(month_branch) + 6) % 12]
        return f'{month}月建在{month_branch}，所衝為{clash}' if day[1] == clash else None
    if rule in ('si_fei', 'si_ji', 'si_qiong'):
        days = _SI_DAYS[season][('si_fei', 'si_ji', 'si_qiong').index(rule)]
        return f"{season}季{'、'.join(days)}" if day in days else None
    if rule == 'wang_wang':
        return f'{month}往亡在{_WANG_WANG[month_branch]}' if day[1] == _WANG_WANG[month_branch] else None
    if rule == 'gui_ji':
        order = '孟仲季'['寅卯辰巳午未申酉戌亥子丑'.index(month_branch) % 3]
        return f'{order}月歸忌在{_GUI_JI[month_branch]}' if day[1] == _GUI_JI[month_branch] else None
    raise ValueError(rule)


def prohibitions(scenario: str, day: str, month_branch: str) -> list[dict]:
    """The rules above that forbid ``scenario`` on day pillar ``day``.

    ``month_branch`` is the solar-term month (月建), as the 起例 are counted
    from it; a day that a term cuts in two is judged per part by the caller.
    """
    term = SCENARIO_TERMS.get(scenario)
    if term is None:
        return []
    hits = []
    for rule in RULES:
        quotes = [a for a in rule['avoid'] if term in a['quote']]
        if not quotes:
            continue
        derivation = _derivation(rule['rule'], day, month_branch)
        if derivation is None:
            continue
        if rule['rule'] == 'si_qiong' and month_branch == '寅' and day == '乙亥':
            continue  # 正月乙亥 is 天願 and the entry lifts everything but war.
        fragment = quotes[-1]['quote']
        at = fragment.index(term)
        hits.append({
            'rule': 'xieji_' + rule['rule'], 'kind': rule['label'], 'label': rule['label'],
            'term': term, 'day_ganzhi': day,
            'passage_id': quotes[-1]['passage_id'],
            'quote': fragment[max(0, at - 8):at + len(term) + 8],
            'derivation': derivation,
            'sources': [rule['qili'], *quotes, rule['binding']],
            'reason': f'{derivation}；本日{day}为{rule["label"]}，所忌含「{term}」，与吉神并仍忌',
            'plain': (f"{rule['label']}日（{derivation}），《协纪辨方书》说这天忌{EVENT_WORDS[scenario]}，"
                      '遇到吉神也照样忌'),
        })
    return hits


def rule_sources(scenario: str) -> list[str]:
    """The 所忌 passages that can exclude a day for ``scenario``."""
    term = SCENARIO_TERMS.get(scenario)
    return list(dict.fromkeys(a['passage_id'] for rule in RULES for a in rule['avoid']
                              if term and term in a['quote']))
