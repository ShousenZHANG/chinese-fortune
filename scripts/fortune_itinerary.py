"""Ordered multi-event feasibility, with explicit travel and shared natal facts.

A plan is a feasible witness, never an auspiciousness ranking. For a fixed
candidate combination, starting each event as early as constraints allow is
complete for feasibility: delaying it cannot help a later event in this model.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from utils import ok_envelope

EVENT_KEYS = {'id', 'event', 'candidates', 'duration_minutes', 'busy', 'period',
              'participant_ids', 'travel_minutes_from_previous'}


def feasible_plans(events: list[dict], *, limit: int = 20, node_limit: int = 10000) -> dict:
    plans: list[list[dict]] = []
    nodes = 0
    truncated = False

    def visit(index: int, previous_end: datetime | None, chosen: list[dict]) -> None:
        nonlocal nodes, truncated
        if len(plans) > limit or nodes >= node_limit:
            truncated = True
            return
        nodes += 1
        if index == len(events):
            plans.append(chosen)
            if len(plans) > limit:
                truncated = True
            return
        item = events[index]
        duration = timedelta(minutes=item['duration_minutes'])
        earliest = (previous_end + timedelta(minutes=item['travel_minutes_from_previous'])
                    if previous_end is not None else None)
        zone = ZoneInfo(item['result']['window']['timezone'])
        for candidate in item['result']['availability']:
            for interval in candidate['intervals']:
                start, end = (datetime.fromisoformat(interval[k]).astimezone(UTC) for k in ('start', 'end'))
                actual = max(start, earliest) if earliest is not None else start
                if actual + duration <= end:
                    visit(index + 1, actual + duration, [*chosen, {
                        'event_id': item['id'], 'candidate_id': candidate['id'],
                        'start': actual.astimezone(zone).isoformat(),
                        'end': (actual + duration).astimezone(zone).isoformat(),
                        'timezone': str(zone), 'travel_minutes_from_previous': item['travel_minutes_from_previous'],
                        'basis': 'earliest_feasible_witness_not_auspicious_time'}])
                if truncated:
                    return

    visit(0, None, [])
    return {'status': 'feasible_not_ranked' if plans else 'search_incomplete' if truncated else 'no_feasible_itinerary',
            'plans': plans[:limit], 'exhaustive': not truncated, 'search_nodes': nodes,
            'ordering': 'input_event_and_candidate_order_not_preference',
            'scope': '固定行程顺序、已声明交通准备时间下的可行组合；不是命理首选备选'}


def read_itinerary(payload: dict, now: dict, *, data_dir: Path | None = None) -> dict:
    from fortune_reading import read_request
    if any(k in payload for k in ('candidates', 'duration_minutes', 'busy')):
        raise ValueError('连续行程的档期、时长及占用请分别填入 events，不放在顶层')
    items = payload.get('events')
    if not isinstance(items, list) or not 2 <= len(items) <= 8:
        raise ValueError('events 需要按实际行程顺序提供2–8件事')
    people = payload.get('participants', [])
    if not isinstance(people, list) or not 1 <= len(people) <= 4 or not all(isinstance(p, dict) for p in people):
        raise ValueError('请提供已确认的参与者资料')
    identities = [p.get('id') for p in people]
    if not all(isinstance(x, str) and x for x in identities) or len(set(identities)) != len(identities):
        raise ValueError('参与者id必须明确且唯一')
    shared: dict = {'request_time': now, 'natal_charts': {}}
    results = []
    seen = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) - EVENT_KEYS:
            raise ValueError('连续行程子项包含未知字段')
        ident = item.get('id')
        if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in seen:
            raise ValueError('每件事需要唯一id，且不超过80字')
        seen.add(ident)
        if index and 'travel_minutes_from_previous' not in item:
            raise ValueError('第二件事起须明确 travel_minutes_from_previous；同地无需交通也请填0')
        travel = item.get('travel_minutes_from_previous', 0)
        if type(travel) is not int or not 0 <= travel <= 10080 or (not index and travel != 0):
            raise ValueError('交通和准备合计为0–10080整数分钟；第一项应为0')
        selected = item.get('participant_ids', identities)
        if (not isinstance(selected, list) or not selected or
                not all(isinstance(x, str) and x in identities for x in selected) or len(set(selected)) != len(selected)):
            raise ValueError('participant_ids须从顶层参与者中选择，不重复')
        event = item.get('event')
        if not isinstance(event, dict) or event.get('scenario') in (None, 'multiple_events', 'outlook'):
            raise ValueError('每件事须明确具体择时事项，不能嵌套连续行程或泛问运势')
        event = {**{k: v for k, v in payload['event'].items() if k != 'scenario'}, **event}
        request = {k: v for k, v in payload.items() if k in ('current_timezone', 'period', 'granularity',
                                                            'include_natal_reading', 'include_research')}
        request.update({k: item[k] for k in ('event', 'candidates', 'duration_minutes', 'busy', 'period') if k in item})
        request['event'] = event
        request['participants'] = [p for p in people if p['id'] in selected]
        result = read_request(request, data_dir=data_dir, _shared=shared)
        if result['capability']['route'] != 'selection' or not result['availability']:
            raise ValueError('每件事需要已支持的择时入口、候选窗口和持续时长')
        results.append({'id': ident, 'duration_minutes': item['duration_minutes'],
                        'travel_minutes_from_previous': travel, 'result': result})
    joint = feasible_plans(results)
    # Each birth chart is computed and transmitted once across all events.
    catalog: dict[str, dict] = {}
    for item in results:
        for person in item['result']['participants']:
            key = person['input_fingerprint']
            value = {'natal': person.pop('natal')}
            if 'natal_interpretation' in person:
                value['natal_interpretation'] = person.pop('natal_interpretation')
            catalog.setdefault(key, value)
            person['natal_ref'] = key
    return ok_envelope('fortune_reading', {'schema_version': '1.1', 'status': 'partial',
        'request_time': now, 'capability': {'scenario': 'multiple_events', 'route': 'itinerary'},
        'natal_catalog': catalog, 'events': results, 'itinerary': joint,
        'recommendation': {'status': 'evidence_needed', 'first_choice': None, 'backup': None},
        'message': '已核对连续行程的实际可行性；各事项的古籍条件分别保留，未把可行行程当命理最优。'})


def render_itinerary(result: dict) -> str:
    joint = result['itinerary']
    if joint['status'] == 'no_feasible_itinerary':
        return '按你给的行程顺序、档期和交通准备时间，目前无法把这些事全部排下。需要调整其中的时间或顺序。'
    if not joint['plans']:
        return '组合搜索尚未完成，目前不能确认这些事情是否排得下。请缩小候选范围后继续核对。'
    lines = ['这些事情能排在一起。下面是一组可行安排；古籍条件还不足以确定哪组最适合你。', '']
    for row in joint['plans'][0]:
        stamps = [datetime.fromisoformat(row[k]) for k in ('start', 'end')]
        start, end = [d.isoformat(sep=' ', timespec='auto' if d.second or d.microsecond else 'minutes') for d in stamps]
        lines.append(f"- {row['event_id']}：{start} 至 {end}（{row['timezone']}）；"
                     f"与上一件事间预留 {row['travel_minutes_from_previous']} 分钟。")
    lines.extend(['', '以上时刻由你给的档期、持续时间和交通准备时间算出，古籍没有为这些具体分钟作出推荐。'])
    if not joint['exhaustive']:
        lines.append('可行组合较多，本次只展示部分组合，尚未穷尽。')
    return '\n'.join(lines)
