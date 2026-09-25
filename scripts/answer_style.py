"""Shared first-sentence rules for the plain-language renderers.

references/27-direct-answer.md: the first sentence follows the kind of
question -- a verdict, an action, or yes/no -- and no renderer may open with a
table, a pillar string or a version. Kept here so every ``--markdown`` output
classifies a question the same way.
"""
from __future__ import annotations

import re

# 27-direct-answer.md 甲类: wrong anywhere; deleting them loses nothing.
CLASS_A = ('仅供参考', '只能当参考', '参考而已', '姑且听之', '信不信由你',
           '要说清楚的是', '必须说清', '先说清楚', '说句实在的', '老实说', '说点真的',
           '好不等于', '不等于保证', '不会自己变好', '不会改变什么', '我理解你想听什么')
CLASS_A_PATTERN = re.compile(r'我看到的不是[^。！？]{0,24}[，,]\s*是')
# 乙类: informative, but only in layer 2 (after the first blank line).
CLASS_B = ('两书相反', '起法分歧', '两说并列', 'passage_id', 'precedence_version',
           'transcription_status', 'facsimile_status')
# 乙类 that may stand in the summary only when the reason follows at once.
CLASS_B_NEEDS_REASON = ('给不了', '答不上', '排不出来', '算不了')


def style_violations(text: str) -> list[str]:
    """Words 27-direct-answer.md forbids where they appear in ``text``."""
    summary = text.split('\n\n', 1)[0]
    found = [word for word in CLASS_A if word in text]
    found += [match.group(0) for match in CLASS_A_PATTERN.finditer(text)]
    found += [word for word in CLASS_B if word in summary]
    found += [word for word in CLASS_B_NEEDS_REASON
              if re.search(re.escape(word) + r'(?!因为)', summary)]
    return found


# 用户说法 -> scenario whose 用事 the day rules know (see xieji_days). Only
# plain everyday words for the same act; 订婚 (納采問名) and 领证 are other 用事.
EVENT_KEYWORDS = {
    'travel': ('出行', '出门', '出远门', '旅行', '远行', '出发'),
    'wedding': ('结婚', '婚礼', '嫁娶', '办婚', '娶亲', '出嫁'),
    'moving': ('搬家', '乔迁', '移徙'),
    'business': ('开业', '开张', '开市', '开店'),
}


def question_kind(question: str) -> str:
    """``choice``, ``yes_no`` or ``verdict`` by the words that ask."""
    if any(word in question for word in ('哪天', '哪个', '几点')):
        return 'choice'
    if any(word in question for word in ('吗', '嗎', '行不行', '可以吗', '是不是', '有没有', '能不能')):
        return 'yes_no'
    return 'verdict'


def event_of(question: str) -> str | None:
    """The scenario a question names, or None when it names none or several."""
    found = [scenario for scenario, words in EVENT_KEYWORDS.items()
             if any(word in question for word in words)]
    return found[0] if len(found) == 1 else None


def rule_detail(hit: dict) -> str:
    """One day rule with its passages: the layer-2 form of ``hit['plain']``."""
    if 'sources' not in hit:  # 天地转杀
        return f"{hit['plain']}（{hit['passage_id']}）"
    qili, *_, binding = hit['sources']
    return (f"{hit['label']}，{hit['derivation']}（起例 {qili['passage_id']}）；"
            f"所忌作「……{hit['quote']}……」（{hit['passage_id']}）；"
            f"「{binding['quote']}」（{binding['passage_id']}）")
