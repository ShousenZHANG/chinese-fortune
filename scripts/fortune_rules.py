"""Discover actual scenario coverage and source scope before attempting a verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from classical_guidance import research_plan
from classical_search import get_passage
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

SCENARIOS = {
    'outlook': ('阶段运势', 'period', '八字岁运与目标窗口；日时吉凶条款待核'),
    'interview': ('面试', 'selection', '现代面试与古法事项的映射、完整八字及日时优先关系'),
    'work_conversation': ('工作沟通、谈薪、转岗', 'selection', '本事项与个人八字结合的日时条款'),
    'exam': ('学习考试', 'selection', '赴举与现代考试的适用差别、本人条件及完整取舍规则'),
    'relationship_conversation': ('约会、感情沟通', 'selection', '该事项适用的本人命盘及日时规则'),
    'travel': ('出行', 'selection', '出行择时与本人八字的衔接、班次及两地时区'),
    'wedding': ('订婚、领证、婚礼', 'selection', '具体仪式、双方同等考虑及各条禁宜的完整优先关系'),
    'moving': ('搬家、入住', 'selection', '区别修造与入住、宅长、朝向等条件及完整规则'),
    'business': ('开业、产品与作品发布', 'selection', '负责人角色、现代事项映射及个人条件的完整规则'),
    'billing': ('报价、催款', 'selection', '日常事项的个人择时依据，不能借用买卖投资判断'),
    'multiple_events': ('连续行程', 'itinerary', '现实联合可行性已实现；命理排名仍须每项事件各自的完整依据'),
    'compatibility': ('关系匹配', 'specialist', '双方资料；合婚独立规则，不借用择时完成状态'),
    'naming': ('起名改名', 'specialist', '字义、读音和使用限制；独立字词证据'),
    'location': ('城市与场所比较', 'specialist', '实际候选及本人、方位条件的独立依据'),
    'fengshui': ('环境与风水', 'specialist', '实际布局、朝向、测量口径及本法依据'),
    'review': ('复盘纠错', 'specialist', '原始判断、当时输入与版本、已发生事实；不倒改为命中'),
}
SOURCE_FILE = Path(__file__).resolve().parents[1] / 'references' / 'forecast-source-audit.json'
EXAMPLE_HASHES = {
    'ziping:c025:p0006': 'c66eb4f99356afdb9874419f5f184192cc55c1de61b3980de93e7492f19b9025',
    'ziping:c025:p0008': '834ed55cfae21c4fc97cef98f153b3662d880ddebd4bbb2f149c023a99800b19',
}


def capabilities(scenario: str | None = None) -> list[dict]:
    if scenario is not None and scenario not in SCENARIOS:
        raise ValueError('未知 scenario；用 fortune_rules.py --capabilities 查看')
    return [{'scenario': key, 'label': label, 'route': route,
             'status': 'partial' if route != 'specialist' else 'use_specialist_workflow',
             'available': ['confirmed_birth_chart', 'target_calendar', 'personal_relations', 'two_classical_luck_examples']
                          + (['availability_filter'] if route == 'selection' else [])
                          + (['joint_feasibility', 'explicit_travel_buffers', 'shared_natal_catalog'] if route == 'itinerary' else [])
                          if route != 'specialist' else [],
             'personal_ranking': 'not_implemented', 'missing': gap}
            for key, (label, route, gap) in SCENARIOS.items() if scenario is None or key == scenario]


def source_audit() -> list[dict]:
    rows = json.loads(SOURCE_FILE.read_text(encoding='utf-8'))['sources']
    for row in rows:
        if hashlib.sha256(row['text'].encode('utf-8')).hexdigest() != row['sha256']:
            raise ValueError('古籍摘录校验失败：' + row['id'])
        if 'oldid=' + row['revision'] not in row['source_url']:
            raise ValueError('古籍版本指针不匹配：' + row['id'])
    return rows


def evidence(*, full_audit: bool = False) -> dict:
    ids = tuple(f'ziping:c025:p{i:04}' for i in range(1, 15))
    passages = [get_passage(pid) for pid in ids]
    keys = ('passage_id', 'text', 'layer', 'sha256', 'book_title', 'edition',
            'chapter_title', 'source_url', 'revision', 'transcription_status', 'facsimile_status')
    audit = source_audit()
    if not full_audit:
        audit = [{key: row[key] for key in ('id', 'title', 'edition', 'chapter', 'source_url',
                  'scope', 'plain_meaning', 'allowed_use', 'not_supported')} for row in audit]
    return {'principle': [{key: p.get(key) for key in keys} for p in passages[:3]],
            'context_and_exceptions': [{key: p.get(key) for key in ('passage_id', 'text', 'layer', 'sha256')}
                                       for p in passages[3:]],
            'context_review': {'checked_on': '2026-09-12', 'checked': '本章14段与来源页面上下文',
                               'facsimile_checked': False,
                               'unresolved': ['p0009 巳/丑存在版本差别，不能据此自动定支的喜忌',
                                              '喜忌正反例还须结合各格取运章，不能略掉似喜实忌、似忌实喜等后文']},
            'scope': '论行运的总原则及正反例；不能由此自行生成逐日逐时吉凶规则',
            'scope_audit': audit}


def luck_observations(natal: dict, target: dict) -> list[dict]:
    """Two narrowly scoped textual examples, not a total luck or event verdict.

    Read stems and branches separately as the cited examples require. A match
    verifies the stated structural antecedents, not every whole-chart condition.
    """
    pillars = natal['four_pillars']
    day = pillars.get('day', {}).get('stem')
    month = pillars.get('month', {}).get('branch')
    year = pillars.get('year', {})
    result = []
    for index, luck in enumerate(target['luck_catalog']):
        if luck['status'] != 'calculated':
            continue
        stem, branch = luck['ganzhi']
        matches = []
        if (day, month, year.get('branch')) == ('丙', '子', '亥'):
            if stem in ('丙', '丁'):
                matches.append(('ziping-luck-bing-stem', 'ziping:c025:p0006',
                    '这段大运的天干与代表你的丙火属于同类，原文把这项关系称为“帮身”。',
                    ['four_pillars.day.stem', 'four_pillars.month.branch', 'four_pillars.year.branch'],
                    '丙日、子月、亥年；本段大运天干为' + stem))
            if branch in ('巳', '午'):
                counterpart = '出生年支亥' if branch == '巳' else '出生月支子'
                matches.append(('ziping-luck-bing-branch', 'ziping:c025:p0006',
                    f'这段大运的地支{branch}与{counterpart}相冲；它与大运天干是否同类是两项不同的关系。',
                    ['four_pillars.day.stem', 'four_pillars.month.branch', 'four_pillars.year.branch'],
                    f'丙日、子月、亥年；本段大运地支为{branch}'))
        if (day, month, year.get('stem')) == ('丁', '亥', '壬') and stem in ('丙', '丁'):
            detail = ('大运的丙火与代表你的丁火属于同类，原文称为“帮身”。' if stem == '丙' else
                      '大运天干丁与出生年干壬形成相合关系。原文的“合官”在此指这两个字的配合，不是在说获得职位。')
            matches.append(('ziping-luck-ding-stem', 'ziping:c025:p0008', detail,
                            ['four_pillars.day.stem', 'four_pillars.month.branch', 'four_pillars.year.stem'],
                            '丁日、亥月、年干壬；本段大运天干为' + stem))
        for rule, pid, text, paths, application in matches:
            source = get_passage(pid)
            if source['sha256'] != EXAMPLE_HASHES[pid]:
                raise ValueError('行运例式原文已变化，须重新核查规则：' + pid)
            result.append({'rule_id': rule, 'status': 'structural_example_matched',
                'scope': 'active_ten_year_cycle_structure_only', 'luck_ref': index,
                'intervals': [{'start': s['start'], 'end': s['end']} for s in target['segments']
                              if s['facts']['active_luck_ref'] == index],
                'personal_fields': paths, 'target_field': f'luck_catalog.{index}.ganzhi',
                'plain_observation': text, 'personal_application': application,
                'source': {k: source[k] for k in ('passage_id', 'text', 'layer', 'edition', 'source_url', 'sha256')},
                'plain_meaning': '这段古文说明，同属一个五行，也要分清具体天干地支与出生盘的配合，不能一律当好或当坏。',
                'plain_application': (
                    f'你的出生资料换算后，代表自己的字是丁，月份对应亥，年份的天干为壬，符合书中的这组条件。'
                    f'这段运程加入的{stem}' + ('与你同属火这一类，原文所说的同类相助指的就是这项配合。' if stem == '丙' else
                    '与出生年干壬形成古法所说的相合关系，原文的“合官”指的是这项配合。')
                    if pid.endswith('p0008') else
                    '你的出生资料换算后，代表自己的字是丙，月份对应子，年份对应亥，符合书中的这组条件。'
                    + (f'这段运程加入的{stem}也属火，因此出现原文所说的同类相助。' if rule.endswith('stem') else
                       f'这段运程的{branch}，与出生盘里的' + ('亥' if branch == '巳' else '子') +
                       '在传统地支配对中相对，这就是这里“相冲”的意思。')),
                'limit': '这里核实的是书里这组配合关系。判断整体运势还要看其他干支怎样配合；这条依据没有细到每日或小时。'})
    return result


def research_request(scenario: str, granularity: str) -> dict:
    gap = capabilities(scenario)[0]['missing']
    return {'status': 'research_required', 'missing': gap, 'requested_granularity': granularity,
            'classical_research': research_plan(scenario, compact=True),
            'queries': ['八字 ' + gap, '协纪辨方书 ' + SCENARIOS[scenario][0]],
            'required_record': ['作品版本与稳定定位', '原文及前后文', '正文或注文',
                                '个人字段与目标字段', '事件与时间粒度', '前提与例外',
                                '现代解读与原义的区别', '计算是否已经实现并验证'],
            'instruction': '先本地检索，不足再补查可核对的古籍与上下文。当前审计不是全网无此依据的证明。'
                           '新算法先实现验证；查证仍不足时只停止该项判断，保留已核事实。'}


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description='查看场景能力、证据范围和补查缺口',
        epilog='Top-level JSON keys: ok tool version capabilities; --evidence: principle '
               'context_and_exceptions context_review scope scope_audit. Errors: error message. '
               'capabilities[] distinguishes available calculations from unimplemented personal ranking.')
    parser.add_argument('--capabilities', action='store_true')
    parser.add_argument('--scenario', help='场景 id；省略时列出全部')
    parser.add_argument('--evidence', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = evidence(full_audit=True) if args.evidence else {'capabilities': capabilities(args.scenario)}
        json_print(ok_envelope('fortune_rules', result))
        return 0
    except (ValueError, OSError) as exc:
        json_print(error_envelope('fortune_rules', 'invalid_evidence', str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
