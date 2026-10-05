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
from life_decision import CRISIS, EMERGENCY
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope
from wuxing_colours import aspects_asked

FENGSHUI_WORDS = ('风水', '朝向', '坐向', '摆放', '床头', '办公桌', '大门', '户型', '摆件')
ALMANAC_WORDS = ('黄历', '皇历', '老黄历', '通书', '宜忌', '宜什么', '忌什么', '黄道吉时')
NATAL_WORDS = ('命局', '八字', '命盘', '性格', '一生', '命好不好', '格局', '日主', '适合什么', '适合做',
               '事业', '财运', '婚姻', '感情')
# Asking which day, month or year is good or bad (for the person).
DAY_WORDS = ('哪天', '哪几天', '哪一天', '几号', '日子', '吉日', '好日子', '凶日', '黄道吉日', '运势', '运气',
             '顺不顺', '吉不吉', '好不好', '宜不宜', '旺我', '利我', '对我好', '对我有利', '哪个月', '哪几个月',
             '哪年', '哪一年', '可以吗', '行不行', '合适吗', '适合吗')
# resolve_window's own words, longest first so 「下个月」 wins over 「下月」.
PERIOD_WORDS = ('未来七天', '最近一周', '这两天', '这周末', '下个星期', '这个星期', '下个月', '这个月', '月底前',
                '今天', '明天', '后天', '本周', '这周', '下周', '周末', '本月', '下月', '今年', '明年')
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
              '注意些什么')
# A real-life decision, asked the way the book's own workflow is triggered.
DECISION_WORDS = ('该不该', '值不值', '要不要', '划不划算', '划算吗', '值得吗', '怎么选', '帮我决定', '犯法吗',
                  '犯不犯法', '违法吗', '能领什么', '能领多少', '先做什么', '签不签', '性价比', '怎么赔',
                  '赔多少', '能拿多少')
# DAY_WORDS that only ask yes or no. With a practical word and no date they ask
# whether something is allowed (「押金不退可以吗」), not which day is good.
YES_NO_WORDS = ('可以吗', '行不行', '合适吗', '适合吗', '好不好')


def _event(question: str) -> str | None:
    found = [s for s, words in {**EVENT_KEYWORDS, **OTHER_EVENTS}.items() if any(w in question for w in words)]
    return found[0] if len(found) == 1 else None


def _period(question: str) -> str | None:
    return next((word for word in PERIOD_WORDS if word in question), None)


BIRTH = '出生年月日与出生地（时辰可缺；立春前后出生需有时刻才能定年柱）'


def route(question: str) -> dict:
    """The flow, the command, the request skeleton and what is still needed."""
    text = question.strip()
    kind = question_kind(text)
    stop = 'emergency' if EMERGENCY.search(text) else ('crisis' if CRISIS.search(text) else None)
    if stop:
        return {'flow': 'life_guide', 'stop': stop,
                'why': '正在发生的急症或自伤念头：先给第一个动作（急救或求助电话），不做术数解释、不排性价比',
                'command': 'python scripts/life_guide.py --decide "<原话>" --current-timezone 现居地时区 --markdown',
                'reference': 'references/20-disclaimer.md',
                'needs': ['现居地时区（求助电话按所在地给）']}
    if any(word in text for word in MEDICAL_WORDS):
        return {'flow': 'boundary', 'why': '涉及医疗，先按边界说明提供现实帮助',
                'reference': 'references/20-disclaimer.md', 'needs': []}
    if any(word in text for word in FENGSHUI_WORDS):
        return {'flow': 'specialist', 'why': '问的是房间、家具的朝向或摆放，属风水专项',
                'reference': 'references/24-personalized-forecast.md', 'needs': ['实际布局与测量']}
    if any(word in text for word in METHOD_WORDS):
        return {'flow': 'other', 'why': '点名了某种占法，按 SKILL.md 路由表用那一法的流程', 'needs': []}
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
    if period or dates or day_words:
        slots = bool(CLOCK.search(text))
        request: dict = {'intent': 'selection' if slots else 'period', 'question': text,
                         'event': {'scenario': event or 'outlook'}}
        if period:
            request['period'] = period
        needs = [BIRTH, '现居地时区（current_timezone）']
        if dates and not period:
            needs.append('把原话里的日期换成 period {"start": "YYYY-MM-DD", "end": 次日}')
        elif not period:
            needs.append('时间范围：原话没说就问一次，或用「未来七天」')
        if slots:
            needs.append('候选时段 candidates 与所需时长 duration_minutes')
        if event == 'travel':
            needs.append('出境时给目的地时区 event.destination_timezone（决定是否附出境安全参考）')
        if event in EVENT_KEYWORDS:
            why = '问这件事哪天好：先排这件事的忌日，再按出生年相主给每天分吉凶'
        else:
            why = '问某段时间哪天（哪个月）对本人好坏：按出生年相主给每天分吉凶'
        return {'flow': 'event_slots' if slots else 'personal_days', 'kind': kind, 'why': why,
                'command': 'python scripts/fortune_reading.py --stdin --markdown', 'request': request,
                'needs': needs}
    if any(word in text for word in NATAL_WORDS):
        return {'flow': 'natal', 'why': '问命局本身',
                'command': ('python scripts/bazi_reading.py --year Y --month M --day D [--hour H --minute m] '
                            '--gender G --city 出生地 --current-timezone 现居地时区 --question "<原话>" --markdown'),
                'needs': [BIRTH]}
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
        epilog='Top-level JSON keys: ok tool version flow why needs [aspects command request kind reference]. '
               'flow: wear_advice personal_days event_slots almanac natal specialist boundary life_guide other.')
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
