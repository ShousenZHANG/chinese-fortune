"""出生资料更正: 改了哪一项、哪几柱跟着变、哪些旧结论作废、哪些保留、新盘是什么.

用户说「刚才时辰给错了」「其实是农历」时, 先跑这里再重新解读。只比较两份资料
算出的盘面事实; 旧回答里具体写了什么由宿主对照 invalidated 去改。
"""
from __future__ import annotations

import argparse
import json
import sys

from bazi_calc import build_parser as bazi_parser
from bazi_calc import calculate_bazi
from birth_candidates import AFFECTS, NAMES, PILLARS
from utils import ensure_utf8_stdio, error_envelope, json_print, ok_envelope

FIELDS = ('year', 'month', 'day', 'hour', 'minute', 'gender', 'lunar', 'leap', 'timezone', 'longitude', 'city',
          'time_standard', 'sect', 'fold')
FIELD_NAMES = {'year': '年', 'month': '月', 'day': '日', 'hour': '时', 'minute': '分', 'gender': '性别',
               'lunar': '农历/公历', 'leap': '闰月', 'timezone': '出生地时区', 'longitude': '经度', 'city': '出生地',
               'time_standard': '时间口径', 'sect': '晚子时取法', 'fold': '重复钟点'}
GENDER_AFFECTS = ['大运顺逆（阳男阴女顺、阴男阳女逆）', '大运干支序列与起运岁数']
SHOWN = {'male': '男', 'female': '女', True: '是', False: '否', None: '未给'}


def _shown(value: object) -> str:
    return SHOWN.get(value, str(value)) if isinstance(value, (str, bool)) or value is None else str(value)


def _chart(birth: dict) -> dict:
    defaults = vars(bazi_parser().parse_args(['--year', '2000', '--month', '1', '--day', '1', '--gender', 'male']))
    unknown = set(birth) - set(FIELDS)
    if unknown:
        raise ValueError(f"不认识的字段：{'、'.join(sorted(unknown))}")
    chart = calculate_bazi(argparse.Namespace(**{**defaults, 'no_shensha': True, 'no_geju': True,
                                                 'no_yongshen': True, **birth}))
    if not chart.get('ok'):
        raise ValueError(chart.get('message', '排盘失败'))
    return chart


def _summary(chart: dict) -> dict:
    pillars = chart['four_pillars']
    return {'four_pillars': {p: (pillars[p] or {}).get('ganzhi') for p in PILLARS},
            'day_master': chart['day_master'].get('stem'), 'hour_known': chart.get('hour_known'),
            'qi_yun_start': (chart.get('qi_yun') or {}).get('start_calendar_datetime'),
            'da_yun': [c['ganzhi'] for c in chart.get('da_yun', [])]}


def correct(before: dict, after: dict) -> dict:
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError('需要 before 与 after 两份出生资料')
    changed = [k for k in FIELDS if before.get(k) != after.get(k)]
    if not changed:
        raise ValueError('两份资料相同，没有可更正的项')
    old, new = _summary(_chart(before)), _summary(_chart(after))
    moved = [p for p in PILLARS if old['four_pillars'][p] != new['four_pillars'][p]]
    invalid = list(dict.fromkeys(item for p in moved for item in AFFECTS[p]))
    if old['da_yun'] != new['da_yun'] or 'gender' in changed:
        invalid += [x for x in GENDER_AFFECTS if x not in invalid]
    kept = [f'{NAMES[p]}{new["four_pillars"][p]}' for p in PILLARS if p not in moved]
    say = ['更正：' + '；'.join(f"{FIELD_NAMES[k]}由{_shown(before.get(k))}改为{_shown(after.get(k))}" for k in changed) + '。']
    if moved:
        say.append('、'.join(f"{NAMES[p]}由{old['four_pillars'][p]}改为{new['four_pillars'][p]}" for p in moved)
                   + f"；原先关于{'、'.join(invalid)}的说法作废，以新盘为准。")
    else:
        say.append('四柱没有变' + ('，但大运变了：' + '、'.join(GENDER_AFFECTS) + '要按新盘重说。'
                                    if old['da_yun'] != new['da_yun'] else '，原先的盘面结论都保留。'))
    if kept and moved:
        say.append(f"{'、'.join(kept)}不变，只依赖这几柱的说法可以保留。")
    return ok_envelope('birth_correction', {
        'changed_fields': changed, 'before': old, 'after': new, 'changed_pillars': moved,
        'invalidated': invalid, 'kept_pillars': kept, 'say': say,
        'next_step': '用 after 的资料重新运行 bazi_reading.py；回答里说明哪一项更正了、哪些结论改了，不把旧结论当成预测失误或命中。',
    })


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='出生资料更正：改了哪一项、哪几柱跟着变、哪些旧结论作废、新盘是什么',
        epilog='stdin JSON: {"before": {出生资料}, "after": {出生资料}}，字段同 bazi_calc（year month day hour minute '
               'gender lunar leap timezone longitude city time_standard sect fold）。Top-level JSON keys: ok tool '
               'version changed_fields before after changed_pillars invalidated kept_pillars say next_step; '
               'errors: ok=false error message.')
    p.add_argument('--stdin', action='store_true', required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    build_parser().parse_args(argv)
    try:
        request = json.loads(sys.stdin.read())
        result = correct(request.get('before'), request.get('after'))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        json_print(error_envelope('birth_correction', 'invalid_request', str(exc)))
        return 1
    json_print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
