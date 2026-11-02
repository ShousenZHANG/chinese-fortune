"""出生资料更正: 改了哪一项、哪几柱跟着变、哪些旧结论作废、哪些保留、新盘是什么.

用户说「刚才时辰给错了」「其实是农历」时, 先跑这里再重新解读。只比较两份资料
算出的盘面事实; 旧回答里具体写了什么由宿主对照 invalidated 去改。
"""
from __future__ import annotations

import argparse
import json
import sys

from bazi_calc import calculate_bazi
from birth_candidates import (
    AFFECTS,
    BIRTH_FIELDS,
    NAMES,
    PILLARS,
    BirthInputError,
    birth_arguments,
    calculation_context,
    canonical_birth,
)
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

FIELDS = BIRTH_FIELDS
FIELD_NAMES = {'year': '年', 'month': '月', 'day': '日', 'hour': '时', 'minute': '分', 'gender': '性别',
               'lunar': '农历/公历', 'leap': '闰月', 'timezone': '出生地时区', 'longitude': '经度', 'city': '出生地',
               'time_standard': '时间口径', 'sect': '晚子时取法', 'fold': '重复钟点'}
GENDER_AFFECTS = ['大运顺逆（阳男阴女顺、阴男阳女逆）', '大运干支序列与起运岁数']
SHOWN = {'male': '男', 'female': '女', True: '是', False: '否', None: '未给'}


def _shown(value: object) -> str:
    return SHOWN.get(value, str(value)) if isinstance(value, (str, bool)) or value is None else str(value)


def _chart(args: argparse.Namespace, field: str) -> dict:
    chart = calculate_bazi(args)
    if not chart.get('ok'):
        raise BirthInputError(field, f"排盘失败 [{chart.get('error')}]：{chart.get('message', '排盘失败')}")
    return chart


def _summary(chart: dict) -> dict:
    pillars = chart['four_pillars']
    return {'four_pillars': {p: (pillars[p] or {}).get('ganzhi') for p in PILLARS},
            'day_master': chart['day_master'].get('stem'), 'hour_known': chart.get('hour_known'),
            'qi_yun_start': (chart.get('qi_yun') or {}).get('start_calendar_datetime'),
            'da_yun': [c['ganzhi'] for c in chart.get('da_yun', [])]}


QI_YUN_AFFECTS = '起运时刻、各步大运的起止年龄与年份'


def correct(before: object, after: object) -> dict:
    before_args, after_args = birth_arguments(before, 'before'), birth_arguments(after, 'after')
    replay = {'before': canonical_birth(before_args), 'after': canonical_birth(after_args)}
    comparisons = []
    for record in replay.values():
        comparisons.append({**record, 'month': abs(record['month']),
                            'leap': record['lunar'] and record['month'] < 0})
    old_input, new_input = comparisons
    changed = [k for k in FIELDS if old_input[k] != new_input[k]]
    if not changed:
        raise BirthInputError('request', '两份资料按相同默认值和闰月表示规范后相同，没有可更正的项')
    old_chart, new_chart = _chart(before_args, 'before'), _chart(after_args, 'after')
    old, new = _summary(old_chart), _summary(new_chart)
    moved = [p for p in PILLARS if old['four_pillars'][p] != new['four_pillars'][p]]
    invalid = list(dict.fromkeys(item for p in moved for item in AFFECTS[p]))
    if old['da_yun'] != new['da_yun'] or 'gender' in changed:
        invalid += [x for x in GENDER_AFFECTS if x not in invalid]
    qi_yun_moved = old.get('qi_yun_start') != new.get('qi_yun_start')
    if qi_yun_moved and QI_YUN_AFFECTS not in invalid:
        invalid.append(QI_YUN_AFFECTS)
    kept = [f'{NAMES[p]}{new["four_pillars"][p]}' for p in PILLARS if p not in moved]
    say = ['更正：' + '；'.join(f"{FIELD_NAMES[k]}由{_shown(old_input[k])}改为{_shown(new_input[k])}" for k in changed) + '。']
    if moved:
        say.append('、'.join(f"{NAMES[p]}由{old['four_pillars'][p]}改为{new['four_pillars'][p]}" for p in moved)
                   + f"；原先关于{'、'.join(invalid)}的说法作废，以新盘为准。")
    elif old['da_yun'] != new['da_yun']:
        say.append('四柱没有变，但大运变了：' + '、'.join(GENDER_AFFECTS) + '要按新盘重说。')
    elif qi_yun_moved:
        say.append(f"四柱和大运干支没有变，但起运时刻由 {old.get('qi_yun_start')} 改为 {new.get('qi_yun_start')}：原先关于"
                   f"{QI_YUN_AFFECTS}的说法作废，其余盘面结论保留。")
    else:
        say.append('四柱、大运和起运时刻都没有变，原先的盘面结论都保留。')
    if kept and moved:
        say.append(f"{'、'.join(kept)}不变，只依赖这几柱的说法可以保留。")
    return ok_envelope('birth_correction', {
        'input': replay, 'method': 'bazi-birth-correction',
        'time_context': {'source': 'before_after_birth_inputs', 'precision': 'minute_or_unknown_hour',
                         'calendar': 'signed_lunar_month_or_solar',
                         'calculation_context': 'calculation_context.before / calculation_context.after'},
        'calculation_context': {'before': calculation_context(old_chart), 'after': calculation_context(new_chart)},
        'changed_fields': changed, 'before': old, 'after': new, 'changed_pillars': moved,
        'invalidated': invalid, 'kept_pillars': kept, 'say': say,
        'next_step': '用 after 的资料重新运行 bazi_reading.py；回答里说明哪一项更正了、哪些结论改了，不把旧结论当成预测失误或命中。',
    })


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='出生资料更正：改了哪一项、哪几柱跟着变、哪些旧结论作废、新盘是什么',
        epilog='stdin JSON: {"before": {出生资料}, "after": {出生资料}}，字段同 bazi_calc（year month day hour minute '
               'gender lunar leap timezone longitude city time_standard sect fold）。两份资料都须明确提供 year month day gender；'
               'hour 可未知。农历 leap=true 规范为负月；负月不能同时 leap=false，公历不能指定闰月。'
               'Top-level JSON keys: ok tool version input method time_context calculation_context changed_fields '
               'before after changed_pillars invalidated kept_pillars say next_step; errors: ok=false error message field.')
    p.add_argument('--stdin', action='store_true', required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    build_parser().parse_args(argv)
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict) or set(request) - {'before', 'after'}:
            raise BirthInputError('request', '须为只含 before 与 after 的 JSON 对象')
        result = correct(request.get('before'), request.get('after'))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        json_print(error_envelope('birth_correction', 'invalid_request', str(exc), field=getattr(exc, 'field', 'request')))
        return 1
    json_print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
