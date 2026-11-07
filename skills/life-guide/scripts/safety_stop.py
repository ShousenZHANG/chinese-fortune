"""Whether a question describes an emergency, a suicidal thought or a legal process happening now.

Shared verbatim by the life-guide and chinese-fortune skills: a fortune question such as
「我现在胸痛，帮我起一卦」 must stop for the emergency even where life-guide is not installed.
tests/test_skill_split.py keeps the two copies identical. The section 13 entry numbers in
EMERGENCY_ENTRIES belong to 《高性价比人生指南》; chinese-fortune uses only the patterns.
"""
from __future__ import annotations

import re

# What turns those words into something else, within the clause that holds
# them: insurance, prevention, a hypothetical, the past, a forecast
# (「中风险理财」「火灾险」「怎么预防心梗」「去年中风过」「六爻看我会不会中风」).
# 「很危险」 is not insurance.
NOT_NOW = re.compile(r'保险|[灾外疾疗寿]险|险种|投保|理赔|风险|预防|防止|防溺|怎么防|防范|'
                     r'会不会|可能会|以后|将来|如果|万一|假如|要是|假设|'
                     r'去年|前年|上个月|以前|曾经|小时候|后遗症|康复|恢复期|'
                     r'最近|经常|有时|偶尔|老是|总是|一直有|'
                     r'牌子|品牌|哪款|药膏|烫伤膏|急救包|急救箱|'
                     r'八字|命里|命理|命盘|运势|流年|大运|紫微|斗数|六爻|起卦|算一|算算|卦|塔罗|星座|风水')
# A background word in one clause says nothing about the next: 「我有保险」 does
# not cancel 「同事触电昏迷了」, 「如果以后……？但我现在喘不上气」 is now. Not 不过:
# it is inside 「喘不过气」.
CLAUSE = re.compile(r'[，,。!！?？；;、\s]+|但是|可是|而且|但')
# 「没有胸痛」 denies the symptom; 「怕不是心梗」「是不是心梗」 do not.
NEGATED = re.compile(r'(?<![怕莫是])(?:不是|没有|没|并非|不)$')
CRISIS = re.compile(r'自杀|不想活|活不下去|活着没意思|活着没意义|想去死|想死(?!在)|死了算了|不如死了|轻生|结束生命|'
                    r'割腕|跳楼|了结自己')
LEGAL = re.compile(r'被传唤|传唤我|被公安传唤|被拘留|被刑拘|被起诉|收到起诉书|收到了起诉书|起诉状|被抓|被立案|被逮捕|'
                   r'传票|派出所叫我|被派出所叫|叫去问话')
# An emergency in progress, the way people describe it, with the book's section
# 13 entries for it and the first action they give: 'call' (120; 119 for a
# fire), 'do' (the first aid itself: cool a burn, keep a fracture still),
# 'gas' (out first, 13:19), 'assault' (somewhere safe, then 110, 13:42).
# One list makes both the detector and the entries, so they cannot drift
# apart. Tests check each number still holds the expected title.
GAS_LEAK = r'(?:燃气|煤气|天然气|液化气)\S{0,4}?(?:泄漏|漏气|漏了)|闻到(?:煤气|燃气|天然气)|(?:煤气|燃气)味'
EMERGENCY_ENTRIES: list[tuple[re.Pattern, list[tuple[int, int]], str]] = [
    (re.compile(r'被性侵|被强奸|遭到性侵'), [(13, 42)], 'assault'),
    (re.compile(GAS_LEAK), [(13, 19)], 'gas'),
    (re.compile(r'一氧化碳'), [(13, 19)], 'gas'),
    (re.compile(r'着火|火灾|失火|起火'), [(13, 24)], 'call'),
    (re.compile(r'(?:婴儿|宝宝|不满 ?1 岁)\S{0,8}?噎'), [(13, 43)], 'call'),
    (re.compile(r'(?:婴儿|宝宝|不满 ?1 岁)\S{0,8}?(?:没反应|没呼吸|没有呼吸)'), [(13, 44)], 'call'),
    (re.compile(r'嘴歪|一侧没劲|一边没劲|半边身子|半身不能动|说话说不清|中风|卒中|天旋地转|看东西成双'),
     [(13, 3), (13, 4)], 'call'),
    (re.compile(r'眼睛突然\S{0,3}黑|一只眼\S{0,4}黑掉'), [(13, 5)], 'call'),
    (re.compile(r'胸口压着疼|胸口剧痛|胸痛|心梗|胸口很闷|胸口闷|胸闷|胸口发紧'), [(13, 7), (13, 8)], 'call'),
    (re.compile(r'最疼的头痛|头痛欲裂|剧烈头痛'), [(13, 9)], 'call'),
    (re.compile(r'大出血|血止不住|止不住血|流血不止|血流不止|血一直流|一直在流血|流了很多血'), [(13, 12)], 'call'),
    (re.compile(r'扎进|插进身体|刺进身体'), [(13, 40)], 'call'),
    (re.compile(r'溺水|落水|掉(?:进|到)?(?:河|水|湖|海|池塘|水库)里?'), [(13, 25)], 'call'),
    (re.compile(r'触电'), [(13, 18)], 'call'),
    (re.compile(r'中毒|误服|误吞|误食|喝了农药|吃错药|吞了电池|吞了纽扣电池'), [(13, 20)], 'call'),
    (re.compile(r'噎住|卡住喉咙|卡在喉咙'), [(13, 26), (13, 43)], 'call'),
    (re.compile(r'过敏性休克|全身起疹'), [(13, 15)], 'call'),
    (re.compile(r'抽搐'), [(13, 16)], 'call'),
    (re.compile(r'喘不上气|喘不过气|上不来气|透不过气|呼吸困难'), [(13, 15), (13, 11)], 'call'),
    (re.compile(r'倒地|没呼吸|没有呼吸|心跳停|心脏骤停|昏迷|叫不醒|晕倒|昏倒|晕过去|不省人事|没有意识|没意识|'
                r'(?:叫|喊|拍)\S{0,3}?没反应|人没反应'), [(13, 1), (13, 2)], 'call'),
    (re.compile(r'中暑|热射病'), [(13, 22), (13, 23)], 'call'),
    (re.compile(r'被蛇咬|蛇咬'), [(13, 29)], 'call'),
    (re.compile(r'烫伤|烧伤'), [(13, 14)], 'do'),
    (re.compile(r'骨折'), [(13, 41)], 'do'),
    (re.compile(r'溅到(?:眼睛|身上|皮肤)|[酸碱]溅'), [(13, 21)], 'do'),
]
EMERGENCY = re.compile('|'.join(f'(?:{pattern.pattern})' for pattern, _, _ in EMERGENCY_ENTRIES))
def _states(clause: str, pattern: re.Pattern) -> bool:
    """Whether the clause says the thing is so, not that it is not."""
    for m in pattern.finditer(clause):
        if m.group(0).startswith('没'):
            # 「没有呼吸困难」 denies a symptom; 「他没有呼吸了」 is one.
            if not re.match(r'困难|急促|不畅|问题', clause[m.end():]):
                return True
        elif not NEGATED.search(clause[max(0, m.start() - 4):m.start()]):
            return True
    return False


def _now(question: str, pattern: re.Pattern) -> list[str]:
    """The clauses that describe the thing as happening now."""
    return [c for c in CLAUSE.split(question) if c and not NOT_NOW.search(c) and _states(c, pattern)]


def stop_kind(question: str) -> str | None:
    """'crisis', 'emergency' or 'legal' when the question describes one now.

    A suicidal thought always counts. An emergency or a legal process counts
    when some clause states it as happening: a clause about insurance,
    prevention, a hypothetical, the past or a forecast does not (「火灾险」
    「会不会被起诉」「六爻看我会不会中风」), and it does not cancel another clause
    that does (「同事触电昏迷了，我有保险」「我现在胸痛，帮我起一卦」).
    """
    if CRISIS.search(question):
        return 'crisis'
    if _now(question, EMERGENCY):
        return 'emergency'
    if _now(question, LEGAL):
        return 'legal'
    return None
