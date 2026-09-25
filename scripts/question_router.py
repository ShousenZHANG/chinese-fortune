"""Which flow answers a question: a deterministic table the host can call.

SKILL.md routes by prose; this script routes the common personal questions by
their words, so 「下个月哪天搬家好」 and 「我穿什么颜色旺我」 land on the tool that
computes them instead of on a generic reading. It computes nothing about the
person and never guesses a birth time; it names what the flow still needs.

Order matters, most specific first: 风水 (furniture, rooms) is a specialist
question even when it says 方位; wearing, colours, numbers, directions and 五行
go to the 调候 answer; 黄历 words go to the almanac; a time or a day word goes
to the personal day grades; the rest are natal or other.
"""
from __future__ import annotations

import argparse
import re
import sys

from answer_style import EVENT_KEYWORDS, question_kind
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
# Events the day rules or 相主 are asked about; mapped ones reuse EVENT_KEYWORDS.
OTHER_EVENTS = {'interview': ('面试',), 'exam': ('考试', '高考', '考研', '考证')}
MEDICAL_WORDS = ('手术', '开刀', '住院', '治疗')


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
    if any(word in text for word in MEDICAL_WORDS):
        return {'flow': 'boundary', 'why': '涉及医疗，先按边界说明提供现实帮助',
                'reference': 'references/20-disclaimer.md', 'needs': []}
    if any(word in text for word in FENGSHUI_WORDS):
        return {'flow': 'specialist', 'why': '问的是房间、家具的朝向或摆放，属风水专项',
                'reference': 'references/24-personalized-forecast.md', 'needs': ['实际布局与测量']}
    aspects = aspects_asked(text)
    if aspects:
        return {'flow': 'wear_advice', 'aspects': aspects,
                'why': '问穿戴、颜色、数字、方位或五行喜用：按《穷通宝鉴》调候用神换算',
                'command': ('python scripts/bazi_reading.py --year Y --month M --day D [--hour H --minute m] '
                            '--gender G --city 出生地 --current-timezone 现居地时区 --question "<原话>" --markdown'),
                'needs': [BIRTH]}
    if any(word in text for word in ALMANAC_WORDS):
        return {'flow': 'almanac', 'why': '问黄历宜忌（不针对个人）',
                'command': 'python scripts/huangli_query.py --date YYYY-MM-DD --question "<原话>" --markdown',
                'needs': ['日期']}
    period, dates, event = _period(text), DATE.findall(text), _event(text)
    if period or dates or any(word in text for word in DAY_WORDS):
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
    return {'flow': 'other', 'why': '不是这几类常见个人问题，按 SKILL.md 路由表选工具', 'needs': []}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='把一句问话对到计算流程；只做路由，不算命盘',
        epilog='Top-level JSON keys: ok tool version flow why needs [aspects command request kind reference]. '
               'flow: wear_advice personal_days event_slots almanac natal specialist boundary other.')
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
