"""Which flow answers a question: a deterministic table the host can call.

SKILL.md routes by prose; this script routes the common personal questions by
their words, so 「下个月哪天搬家好」 and 「我穿什么颜色旺我」 land on the tool that
computes them instead of on a generic reading. It computes nothing about the
person and never guesses a birth time; it names what the flow still needs.

Order matters, most specific first: 风水 (furniture, rooms) is a specialist
question even when it says 方位; a named method (六爻, 塔罗…) goes to its own
workflow; wearing, colours, numbers, directions and 五行 go to the 调候 answer;
黄历 words go to the almanac; a time or a day word goes to the personal day
grades; the rest are natal, practical (the reference library) or other.
An emergency in progress or a suicidal thought comes before all of it: the
decision flow's first step gives the first action.
"""
from __future__ import annotations

import argparse
import re
import sys

from answer_style import EVENT_KEYWORDS, question_kind
from life_decision import stop_kind
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope
from wuxing_colours import aspects_asked

FENGSHUI_WORDS = ('风水', '朝向', '坐向', '摆放', '床头', '办公桌', '大门', '户型', '摆件')
ALMANAC_WORDS = ('黄历', '皇历', '老黄历', '通书', '宜忌', '宜什么', '忌什么', '黄道吉时')
NATAL_WORDS = ('命局', '八字', '四柱', '命盘', '性格', '一生', '命好不好', '格局', '日主', '适合什么', '适合做',
               '事业', '财运', '婚姻', '感情')
# Asking which day, month or year is good or bad (for the person).
DAY_WORDS = ('哪天', '哪几天', '哪一天', '几号', '日子', '吉日', '好日子', '凶日', '黄道吉日', '运势', '运气',
             '顺不顺', '吉不吉', '好不好', '宜不宜', '旺我', '利我', '对我好', '对我有利', '哪个月', '哪几个月',
             '哪年', '哪一年', '可以吗', '行不行', '合适吗', '适合吗')
# resolve_window's own words, longest first so 「下个月」 wins over 「下月」.
PERIOD_WORDS = ('未来七天', '最近一周', '这两天', '这周末', '下个星期', '这个星期', '下个月', '这个月', '月底前',
                '今天', '明天', '后天', '本周', '这周', '下周', '周末', '本月', '下月', '今年', '明年',
                '年底前', '近期', '最近', '这段时间')
CLOCK = re.compile(r'\d{1,2}[点:：]|上午|下午|晚上|中午|早上|小时|分钟')
DATE = re.compile(r'(?:(\d{4})[年-])?(\d{1,2})[月-](\d{1,2})[日号]?')
# Days named without a month: a weekday, 「15号」, a lunar 「初八」, a festival.
# 「初一」 as a school year (初一学生) is not a day.
NAMED_DAY = re.compile(r'(?:周|星期|礼拜)[一二三四五六日天]|\d{1,2}号|[一二三四五六七八九十廿]{1,3}号'
                       r'|初[一二三四五六七八九十](?![学生中年])|除夕|春节|元旦|元宵|清明|端午|七夕|中秋|重阳|国庆'
                       r'|腊八|小年|五一|劳动节|情人节|圣诞')
# Events the day rules or 相主 are asked about; mapped ones reuse EVENT_KEYWORDS.
OTHER_EVENTS = {'interview': ('面试',), 'exam': ('考试', '高考', '考研', '考证')}
MEDICAL_WORDS = ('手术', '开刀', '住院', '治疗')
# A method the asker named (SKILL.md's own list and the folk ones its
# description names). Its own workflow answers, never 相主 or the reference
# library, whatever else the question mentions. Bare 紫微 is also a place
# name (洛阳紫微城), so only 紫微斗数 / 紫微命盘 / 紫微盘 count.
METHOD_WORDS = ('起卦', '起个卦', '一卦', '卜卦', '占卜', '占卦', '摇卦', '摇个卦', '问卦', '六爻', '周易', '易经',
                '梅花易', '奇门', '六壬', '斗数', '紫微命', '紫微盘', '塔罗', '星座', '测字', '求签', '求个签',
                '抽签', '解签')
# Practical questions the frozen 《高性价比人生指南》 answers. Checked only after
# every divination flow, so a question about a date is never taken by it.
# Topic words follow the book's 34 sections; the day flows' event words
# (结婚, 搬家, 出行, 开业, 面试) are left out so 「结婚可以吗」 keeps its route.
LIFE_WORDS = ('押金', '租房', '房东', '租房合同', '试用期', '加班费', '辞退', '裁员', '被裁', '失业', '工伤', '欠薪',
              '讨薪', '离职', '辞职', '劳动合同', '仲裁', '社保', '医保', '公积金', '养老金', '保险', '领事保护',
              '12308', '借条', '借钱', '网贷', '信用卡', '房贷', '担保', '定金', '订金', '彩礼', '离婚', '家暴',
              '诈骗', '被骗', '旅行保险', '体检', '保健品', '戒烟', '戒酒', '熬夜', '通勤', '理财', '基金', '股票',
              '急救', '心肺复苏', '感冒药', '止痛药', '慢性病', '高血压', '糖尿病', '怀孕', '坐月子', '新生儿',
              '养老院', '遗嘱', '继承', '留学', '残疾', '近视', '职称', '个体户', '营业执照', '要注意什么',
              '注意些什么',
              # The rest of the book's 34 README questions and the everyday ways
              # of asking them (「老板不发工资」「手机丢了」).
              '早死', '折寿', '精力', '拖延', '利息', '费率', '骗局', '兼职', '刑事', '判刑', '坐牢', '追人', '异地恋',
              '领证', '代码', '接单', '账号被盗', '被盗', '手机丢', '刚出生', '使领馆', '大使馆', '出国', 'KTV', 'ktv',
              '网吧', '密室', '压力大', '网站', '服务器', '减肥', '变好看', '上学', '读书', '打工', '十八岁', '工资',
              '拖欠', '赔偿', '不赔', '退款', '噪音', '邻居', '摔倒', '扶不扶', '网暴', '发烧', '退烧', '吃药',
              '重疾险', '律师', '起诉', '打官司', '维权')
# A divination question phrased as a decision (「算一下我该不该辞职」「流年看我该不该
# 离婚」): it stays with the divination methods, before the decision words.
FORTUNE_CUES = ('命里', '命理', '命中', '命格', '命数', '算算', '算一下', '算一算', '帮我算', '测一下', '流年', '大运',
                '偏财', '正财', '紫微', '运程', '卦', '本命年', '太岁', '桃花', '正缘', '姻缘', '贵人', '财位', '发财',
                '解梦', '梦见', '手相', '面相', '取名', '起名', '改名', '名字', '属相', '生肖', '合不合', '合婚',
                '配不配', '五行')
# A real-life decision, asked the way the book's own workflow is triggered.
DECISION_WORDS = ('该不该', '值不值', '要不要', '划不划算', '划算吗', '值得吗', '怎么选', '帮我决定', '犯法吗',
                  '犯不犯法', '违法吗', '能领什么', '能领多少', '先做什么', '签不签', '性价比', '怎么赔',
                  '赔多少', '能拿多少', '怎么办', '第一步', '做什么', '怎么改', '怎么治', '怎么戒', '怎么做')
# DAY_WORDS that only ask yes or no. With a practical word and no date they ask
# whether something is allowed (「押金不退可以吗」), not which day is good.
YES_NO_WORDS = ('可以吗', '行不行', '合适吗', '适合吗', '好不好')
# DAY_WORDS that ask whether a time is good: these keep a question a day question.
LUCK_WORDS = tuple(w for w in DAY_WORDS if w not in YES_NO_WORDS)
# Asking how to do a real thing. With a practical word, a date in the question
# says when it happens (「我明天签租房合同，押金要注意什么」), not which day is good.
HOW_WORDS = ('怎么', '注意', '先做什么', '第一步', '能领', '申请', '要带', '带什么', '流程', '手续', '材料', '检查什么',
             '准备什么', '要不要', '该不该', '值不值')


def _event(question: str) -> str | None:
    found = [s for s, words in {**EVENT_KEYWORDS, **OTHER_EVENTS}.items() if any(w in question for w in words)]
    return found[0] if len(found) == 1 else None


def _period(question: str) -> str | None:
    return next((word for word in PERIOD_WORDS if word in question), None)


BIRTH = '出生年月日、性别与出生地（时辰可缺；立春前后出生需有时刻才能定年柱）'

BAZI_COMMAND = ('python scripts/bazi_reading.py --year Y --month M --day D '
                '[--hour H --minute m] --gender G --city 出生地 --question "<原话>" --view compact '
                '--facts-out <临时目录>/bazi.json')


def _reference_time_needs(text: str) -> list[str]:
    if any(word in text for word in ('大运', '流年', '今年', '明年', '运势', '这几年')):
        return ['参考年份，或现居地时区与本次请求时间；已有的直接复用']
    return []


def _named_methods(text: str) -> list[dict]:
    """Concrete entry points for explicitly requested systems, in mention order."""
    # Avoid known place names without hiding the bare method names in a list.
    text = re.sub(r'紫微(?:城|路|街)|梅花(?:山|糕|鹿|园)', '', text)
    definitions = [
        (('八字', '四柱'), 'bazi', 'bazi_reading.py', '01-bazi.md', BAZI_COMMAND, [BIRTH]),
        (('紫微', '斗数'), 'ziwei', 'ziwei_calc.py', '02-ziwei.md',
         'python scripts/ziwei_calc.py --year Y --month M --day D --hour H --minute m --gender G --city 出生地 --brief-palaces',
         ['出生日期、历法、时分、性别和出生地；时辰未知先比较候选，不补子时']),
        (('梅花',), 'meihua', 'meihua_cast.py', '05-meihua.md',
         'python scripts/meihua_cast.py --current-timezone 现居地时区 --request-time 本次UTC time --question "<原话>"',
         ['起卦方式（时间、数字或字数），复用本次请求时刻与现居地时区']),
        (('六爻',), 'liuyao', 'liuyao_cast.py', '04-liuyao.md',
         'python scripts/liuyao_cast.py coins --current-timezone 现居地时区 --request-time 本次UTC --question "<原话>"',
         ['问题、起卦方式与原始投掷（已有结果不重起），占问时刻和时区']),
        (('周易', '易经'), 'yijing', 'yijing_cast.py', '03-yijing.md',
         'python scripts/yijing_cast.py time --current-timezone 现居地时区 --request-time 本次UTC --question "<原话>"',
         ['问题和起卦方式；时间法复用请求时刻，已有卦象直接复用']),
        (('奇门',), 'qimen', 'qimen_cast.py', '06-qimen.md',
         'python scripts/qimen_cast.py --current-timezone 现居地时区 --request-time 本次UTC',
         ['事件、占问时刻/时区和地点；沿用已确认方法']),
        (('大六壬', '六壬'), 'liuren', 'liuren_cast.py', '07-daliuren.md',
         'python scripts/liuren_cast.py --current-timezone 现居地时区 --request-time 本次UTC',
         ['事件、占问时刻/时区和地点']),
        (('塔罗',), 'tarot', 'tarot_draw.py', '18-tarot.md',
         'python scripts/tarot_draw.py one --question "<原话>"',
         ['问题与牌阵；已有抽牌直接复用，不因展开详情重新抽牌']),
    ]
    found = []
    for words, method, script, reference, command, needs in definitions:
        if method == 'liuren' and '小六壬' in text and '大六壬' not in text:
            continue
        positions = [text.index(word) for word in words if word in text]
        if positions:
            if method in ('bazi', 'ziwei'):
                needs = [*needs, *_reference_time_needs(text)]
            found.append((min(positions), {'method': method, 'script': 'scripts/' + script,
                                          'reference': 'references/' + reference,
                                          'command': command, 'needs': needs}))
    return [item for _, item in sorted(found, key=lambda item: item[0])]


def _knowledge_only(text: str) -> bool:
    terms = ('正官', '伤官', '十神', '日主', '格局', '用神', '八字', '四柱', '大运', '流年', '透干', '藏干',
             '紫微', '命宫', '身宫', '六爻', '世应', '体用', '梅花', '奇门', '六壬', '塔罗', '周易', '易经')
    definition = ('解释', '什么意思', '是什么', '定义', '区别', '怎么理解', '术语')
    without_person = text.replace('不分析我', '').replace('不用分析我', '')
    without_person = re.sub(r'(?:帮我|给我)(?=解释)', '', without_person)
    # A concrete chart or a possessor requests analysis, not a glossary entry.
    if re.search(r'(?:这|那|该)(?:张|个|份|副)?(?:八字|四柱|命盘)', text):
        return False
    for possessive in re.finditer(r'的(?=八字|四柱|格局|命宫|身宫|命盘)', text):
        if not re.search(r'(?:八字|四柱|紫微斗数|紫微|斗数)$', text[:possessive.start()]):
            return False
    return (any(word in text for word in terms) and any(word in text for word in definition)
            and not re.search(r'\d{4}[-年/]', text)
            and not any(word in without_person for word in ('我', '本人', '我的', '出生', '生日', '孩子', '儿子', '女儿',
                        '父亲', '母亲', '爸爸', '妈妈', '妻子', '丈夫', '男友', '女友', '朋友', '对象', '他的', '她的')))


def _knowledge_route(text: str) -> dict:
    named = _named_methods(text)
    if not named and '小六壬' not in text:
        inferred = ''.join(method for terms, method in (
            (('命宫', '身宫'), '紫微'), (('世应',), '六爻'), (('体用',), '梅花'),
            (('正官', '伤官', '十神', '日主', '格局', '用神', '大运', '流年', '透干', '藏干'), '八字'),
        ) if any(term in text for term in terms))
        named = _named_methods(inferred)
    references = [m['reference'] for m in named] or ['references/21-extended-methods.md']
    books = {'bazi': 'ziping', 'ziwei': 'ziwei', 'meihua': 'meihua',
             'liuyao': 'zengshan', 'qimen': 'yuanling', 'liuren': 'liuren'}
    book = books.get(named[0]['method']) if len(named) == 1 else None
    return {'flow': 'knowledge', 'why': '只解释术语与依据，不需要个人生辰或当前时间',
            'command': 'python scripts/classical_search.py --query "<所问术语>"' + (f' --book {book}' if book else ''),
            'reference': references[0], 'references': references, 'needs': []}


UNSURE_WORDS = ('不确定', '记不清', '拿不准', '说不准', '不太清楚', '也可能是', '还是')
BIRTH_TIME_WORDS = ('出生', '生的', '时辰', '生于')


CORRECTION_WORDS = ('说错了', '给错了', '写错了', '记错了', '搞错了', '更正', '纠正一下', '应该是', '其实是')


def _corrected_birth(text: str) -> bool:
    """「刚才时辰给错了，其实是晚上十点」: the user corrects birth data already given."""
    return any(word in text for word in CORRECTION_WORDS) and (
        any(word in text for word in BIRTH_TIME_WORDS) or any(word in text for word in ('时辰', '农历', '公历', '阴历')))


def _uncertain_birth(text: str) -> bool:
    """「不确定是 5 号晚上还是 6 号凌晨出生」: an unsure birth time, with two moments named."""
    unsure = any(word in text for word in UNSURE_WORDS)
    about_birth = any(word in text for word in BIRTH_TIME_WORDS)
    moments = len(re.findall(r'\d{1,2}\s*[号日点]|凌晨|半夜|深夜|晚上|早上|上午|下午|中午', text))
    return unsure and about_birth and moments >= 2


def _natal_route(text: str) -> dict:
    needs = [BIRTH, *_reference_time_needs(text)]
    return {'flow': 'natal', 'why': '问本命、格局或八字岁运，按相应粒度核对',
            'script': 'scripts/bazi_reading.py', 'reference': 'references/01-bazi.md',
            'command': BAZI_COMMAND, 'needs': needs}


def route(question: str) -> dict:
    """The flow, the command, the request skeleton and what is still needed."""
    text = question.strip()
    kind = question_kind(text)
    stop = stop_kind(text)
    if stop:
        return {'flow': 'life_guide', 'stop': stop,
                'why': '正在发生的急症、自伤念头或法律程序：先给第一个动作，不做术数解释、不排性价比',
                'command': 'python scripts/life_guide.py --decide "<原话>" --current-timezone 现居地时区 --markdown',
                'reference': 'references/20-disclaimer.md',
                'needs': ['现居地时区（求助电话和法律口径按所在地给）']}
    if any(word in text for word in MEDICAL_WORDS):
        return {'flow': 'boundary', 'why': '涉及医疗，先按边界说明提供现实帮助',
                'reference': 'references/20-disclaimer.md', 'needs': []}
    if _knowledge_only(text):
        return _knowledge_route(text)
    if any(word in text for word in FENGSHUI_WORDS):
        return {'flow': 'specialist', 'why': '问的是房间、家具的朝向或摆放，属风水专项',
                'reference': 'references/08-fengshui.md', 'needs': ['实际布局与测量']}
    if any(w in text for w in ('反查', '反推', '倒推', '推出生日')) and any(w in text for w in ('四柱', '八字', '生日', '出生')):
        return {'flow': 'pillars_to_dates', 'why': '由四柱反查历法上可能的出生日期与真太阳时窗口',
                'command': 'python scripts/pillars_to_dates.py --year-pillar 年柱 --month-pillar 月柱 '
                           '--day-pillar 日柱 [--hour-pillar 时柱] [--from-year 1900 --to-year 2100]',
                'reference': 'references/00-intake.md', 'needs': ['年月日柱（时柱可缺）']}
    if _corrected_birth(text):
        return {'flow': 'birth_correction',
                'why': '更正出生资料：先列改了哪项、哪几柱跟着变、哪些旧结论作废，再用新资料重新解读',
                'command': 'python scripts/birth_correction.py --stdin',
                'stdin': '{"before": {原出生资料}, "after": {更正后的出生资料}}',
                'reference': 'references/22-output-contract.md', 'needs': ['原资料与更正后的资料（已给的直接复用）']}
    if _uncertain_birth(text):
        return {'flow': 'birth_candidates',
                'why': '出生时间拿不准、可能跨日期：先列各候选哪几柱不变、哪几柱会变，再按候选分别解读',
                'command': 'python scripts/birth_candidates.py --stdin',
                'stdin': '{"birth": {"gender", "timezone", "longitude"|"city"}, '
                         '"range": {"start": "YYYY-MM-DDTHH:MM", "end": ...} 或 "candidates": [...]}',
                'reference': 'references/00-intake.md', 'needs': ['性别、出生地、候选时间或时间范围']}
    methods = _named_methods(text)
    relationship = any(word in text for word in ('合婚', '合盘', '亲子关系', '姐妹关系'))
    if relationship and (not methods or all(m['method'] in ('bazi', 'ziwei') for m in methods)):
        chosen = methods or _named_methods('八字' + text)
        return {'flow': 'compatibility', 'why': '分别核两方事实，各体系独立核跨盘条款，不混盘或给成功率',
                'reference': 'references/14-hehun.md', 'combine_verdicts': False,
                'subjects': ['A', 'B'],
                'steps': [{'subject': subject, **method} for subject in ('A', 'B') for method in chosen],
                **({'pair_facts': {'command': 'python scripts/pair_facts.py --stdin',
                                   'stdin': '{"a": {A 出生资料}, "b": {B 出生资料}}',
                                   'why': '两人逐柱合冲刑害与日主互见十神，只列事实不打分'}}
                   if any(m['method'] == 'bazi' for m in chosen) else {}),
                'needs': ['两方各自已确认的出生资料（各自保留未知时刻）', '关系类型与具体问题',
                          *_reference_time_needs(text)]}
    if len(methods) > 1:
        return {'flow': 'multi_method', 'why': '各方法分别计算和解释，共用已确认资料，不合成命运分数',
                'steps': methods, 'combine_verdicts': False,
                'needs': list(dict.fromkeys(need for step in methods for need in step['needs']))}
    if methods and methods[0]['method'] != 'bazi':
        return {'flow': 'method', 'why': '按明确点名的方法计算，已有资料复用，只补必要缺项',
                **methods[0]}
    if any(word in text for word in METHOD_WORDS):
        return {'flow': 'other', 'why': '点名了某种占法，按 SKILL.md 路由表用那一法的流程', 'needs': []}
    if any(word in text for word in ('大运', '流年', '成格', '变格', '格局', '四柱', '日主')):
        return _natal_route(text)
    aspects = aspects_asked(text)
    if aspects:
        return {'flow': 'wear_advice', 'aspects': aspects,
                'why': '问穿戴、颜色、数字、方位或五行喜用：按《穷通宝鉴》这一格调候的一般取法换算（例外未逐盘核对）',
                'command': ('python scripts/bazi_reading.py --year Y --month M --day D [--hour H --minute m] '
                            '--gender G --city 出生地 --current-timezone 现居地时区 --question "<原话>" --markdown'),
                'needs': [BIRTH]}
    if any(word in text for word in ALMANAC_WORDS):
        return {'flow': 'almanac', 'why': '问黄历宜忌（不针对个人）',
                'command': 'python scripts/huangli_query.py --date YYYY-MM-DD --question "<原话>" --markdown',
                'needs': ['日期']}
    period, event = _period(text), _event(text)
    dates = DATE.findall(text) + NAMED_DAY.findall(text)
    practical = any(word in text for word in LIFE_WORDS)
    day_words = [w for w in DAY_WORDS if w in text and not (practical and w in YES_NO_WORDS)]
    # 「我今天被裁了，怎么申请失业保险金」 asks how, not whether today is good.
    happens_then = (practical and any(w in text for w in HOW_WORDS)
                    and not any(w in text for w in LUCK_WORDS))
    if (period or dates or day_words) and not happens_then:
        slots = bool(CLOCK.search(text))
        request: dict = {'intent': 'selection' if slots else 'period', 'question': text,
                         'event': {'scenario': event or 'outlook'}}
        if period:
            request['period'] = period
        needs = [BIRTH, '现居地时区（current_timezone）']
        if dates and not period:
            needs.append('把原话里的日期换成 period {"start": "YYYY-MM-DD", "end": 次日}')
        elif not period:
            needs.append('时间范围：原话没说也不要追问，用 period "近期"（今天到年底，剩不到一个月时算一个月），'
                         '回答开头说明这是暂按的范围')
        if slots:
            needs.append('候选时段 candidates 与所需时长 duration_minutes')
        if event == 'travel':
            needs.append('出境时给目的地时区 event.destination_timezone（决定是否附出境安全参考）')
        if event in EVENT_KEYWORDS:
            why = '问这件事哪天好：先排这件事的忌日，再按出生年相主给每天分吉凶'
        else:
            why = '问某段时间哪天（哪个月）对本人好坏：按出生年相主给每天分吉凶'
        return {'flow': 'event_slots' if slots else 'personal_days', 'kind': kind, 'why': why,
                'command': 'python scripts/fortune_reading.py --stdin --facts-out <临时目录>/fortune.json',
                'request': request,
                'needs': needs}
    if any(word in text for word in NATAL_WORDS):
        return _natal_route(text)
    if any(word in text for word in FORTUNE_CUES):
        return {'flow': 'other', 'why': '带命理说法的问题，按 SKILL.md 路由表选术数方法；现实决策流程不接', 'needs': []}
    if practical or any(word in text for word in DECISION_WORDS):
        return {'flow': 'life_guide',
                'why': '问现实层面怎么做：按《高性价比人生指南》的决策流程查条目、按性价比和证据等级排序，'
                       '分先做和别做，每条注明出处',
                'command': 'python scripts/life_guide.py --decide "<原话>" --current-timezone 现居地时区 --markdown',
                'reference': 'references/29-life-decision.md',
                'needs': ['现居地时区（决定适用哪里的规定；事情发生在别处时另给那里的时区）']}
    return {'flow': 'other', 'why': '不是这几类常见个人问题，按 SKILL.md 路由表选工具', 'needs': []}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='把一句问话对到计算流程；只做路由，不算命盘',
        epilog='Top-level JSON keys: ok tool version flow why needs [aspects command request kind reference method steps]. '
               'flow: wear_advice personal_days event_slots almanac natal method multi_method knowledge '
               'compatibility specialist boundary life_guide other.')
    parser.add_argument('--question', required=True, help='用户原话')
    args = parser.parse_args(argv)
    if not args.question.strip() or len(args.question) > 2000:
        # A route for nothing (or for a pasted document) would be a guess.
        json_print(error_envelope('question_router', 'invalid_question', '问句须为 1–2000 字符的文本'))
        return 1
    json_print(ok_envelope('question_router', {'question': args.question, **route(args.question)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
