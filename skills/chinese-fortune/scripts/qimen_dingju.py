"""符头三元与实交节定局；来源及现代日界约定见 docs/QIMEN-LIUREN-METHODS.md。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from qimen_tables import YANG_JIE_QI, YIN_JIE_QI
from utils import UTC, jiazi_index, require_lunar

SOURCE_URL = "https://zh.wikisource.org/w/index.php?oldid=8259389"
CALENDAR_ZONE = timezone(timedelta(hours=8))


def futou(day_ganzhi: str) -> tuple[str, str]:
    """最近甲/己日起五日一元；符头地支定上中下，不从交节日重新起上元。"""
    if len(day_ganzhi) != 2:
        raise ValueError("日干支须为两个字")
    index = jiazi_index(day_ganzhi[0], day_ganzhi[1])
    head = index - index % 5
    stem = "甲乙丙丁戊己庚辛壬癸"[head % 10]
    branch = "子丑寅卯辰巳午未申酉戌亥"[head % 12]
    yuan = "上元" if branch in "子午卯酉" else "中元" if branch in "寅申巳亥" else "下元"
    return stem + branch, yuan


def determine_ju(jieqi_name: str, day_ganzhi: str) -> tuple[str, str, int]:
    """《元灵经》三元符头、阴阳各局；不用超神接气置闰。"""
    _, yuan = futou(day_ganzhi)
    index = ("上元", "中元", "下元").index(yuan)
    if jieqi_name in YANG_JIE_QI:
        return "阳遁", yuan, YANG_JIE_QI[jieqi_name][index]
    if jieqi_name in YIN_JIE_QI:
        return "阴遁", yuan, YIN_JIE_QI[jieqi_name][index]
    raise ValueError(f"unknown 节气: {jieqi_name}")


# 超神接气置闰（《遁甲演义》卷一 dunjia:c001:p0013–p0015）：每个节气配一个上元符头起的十五日（三元），
# 按符头先后连排；符头早于交节为超神，晚于为接气，同日为正授。超神只在芒种、大雪置闰：这两个节气的
# 上元符头比交节早九日以上，就把同一节气再排十五日（闰奇）。书中万历二十六年大雪超十二日置闰、
# 二十九年芒种超九日置闰、二十六年芒种超八日不闰、二十七年小暑甲子正授，测试逐条复算。
TERM_ORDER = ('冬至', '小寒', '大寒', '立春', '雨水', '惊蛰', '春分', '清明', '谷雨', '立夏', '小满', '芒种',
              '夏至', '小暑', '大暑', '立秋', '处暑', '白露', '秋分', '寒露', '霜降', '立冬', '小雪', '大雪')
ZHIRUN_TERMS = ('芒种', '大雪')
ZHIRUN_DAYS = 9
ZHIRUN_SOURCES = (
    ('dunjia:c001:p0013', '節未至而日辰符頭先到則以符頭為主而超用未來之節氣此之謂超', '超神'),
    ('dunjia:c001:p0013', '置閏定在芒種大雪之後', '只在芒种、大雪置闰'),
    ('dunjia:c001:p0014', '超神不過十日遇芒種大雪超過九日即置閏也', '超九日以上置闰'),
    ('dunjia:c001:p0015', '十三甲午日疊作大雪節此名閏竒', '闰奇例'),
)


def _term_dates(first_year: int, last_year: int) -> list[tuple]:
    from datetime import date as _date

    require_lunar()
    from lunar_python import Solar
    found: dict = {}
    for year in range(first_year, last_year + 1):
        for key, value in Solar.fromYmd(year, 6, 1).getLunar().getJieQiTable().items():
            name = {'DONG_ZHI': '冬至', 'XIAO_HAN': '小寒', 'DA_HAN': '大寒', 'LI_CHUN': '立春',
                    'YU_SHUI': '雨水', 'DA_XUE': '大雪'}.get(key, key)
            if name in TERM_ORDER:
                day = _date(value.getYear(), value.getMonth(), value.getDay())
                found[day] = name
    return sorted(found.items())


def zhirun_term(target: date) -> dict:
    """The 节气 and 元 at a civil date by 超神接气置闰, chained from seven years earlier."""
    from datetime import timedelta as _td

    terms = _term_dates(target.year - 7, target.year + 1)
    u = terms[0][0] + _td(days=30)
    while _jiazi_of(u) % 15:
        u += _td(days=1)
    j = min(range(len(terms)), key=lambda i: abs((terms[i][0] - u).days))
    repeated = False
    while u + _td(days=15) <= target:
        chao = (terms[j][0] - u).days
        if terms[j][1] in ZHIRUN_TERMS and chao >= ZHIRUN_DAYS and not repeated:
            repeated = True
        else:
            j, repeated = j + 1, False
        u += _td(days=15)
    chao = (terms[j][0] - u).days
    mode = '闰奇' if repeated else '正授' if chao == 0 else '超神' if chao > 0 else '接气'
    yuan = ('上元', '中元', '下元')[(target - u).days // 5]
    return {'term': terms[j][1], 'term_date': terms[j][0].isoformat(), 'yuan_start': u.isoformat(),
            'chao_days': chao, 'mode': mode, 'yuan': yuan}


def _jiazi_of(day: date) -> int:
    require_lunar()
    from lunar_python import Solar
    gz = Solar.fromYmdHms(day.year, day.month, day.day, 12, 0, 0).getLunar().getDayInGanZhi()
    return jiazi_index(gz[0], gz[1])


def determine_ju_zhirun(target: date) -> tuple[str, str, int, dict]:
    row = zhirun_term(target)
    index = ('上元', '中元', '下元').index(row['yuan'])
    if row['term'] in YANG_JIE_QI:
        return '阳遁', row['yuan'], YANG_JIE_QI[row['term']][index], row
    return '阴遁', row['yuan'], YIN_JIE_QI[row['term']][index], row


def seasonal_context(instant: datetime) -> dict:
    """Select the last solar term at the actual instant, including the year boundary.

    lunar_python's term table uses UTC+08 clock values. An aware input is first
    converted to that clock. A floating input cannot locate an astronomical
    instant and is returned explicitly as an unresolved calendar assumption.
    """
    require_lunar()
    from lunar_python import Solar

    aware = instant.tzinfo is not None and instant.utcoffset() is not None
    clock = instant.astimezone(CALENDAR_ZONE) if aware else instant
    solar = Solar.fromYmdHms(clock.year, clock.month, clock.day,
                            clock.hour, clock.minute, clock.second)
    term = solar.getLunar().getPrevJieQi()
    value = term.getSolar()
    boundary = datetime(value.getYear(), value.getMonth(), value.getDay(),
                        value.getHour(), value.getMinute(), value.getSecond(),
                        tzinfo=CALENDAR_ZONE)
    return {
        "name": term.getName(),
        "boundary_calendar": boundary.isoformat(),
        "boundary_utc": boundary.astimezone(UTC).isoformat() if aware else None,
        "status": "instant_resolved" if aware else "floating_calendar_assumption",
        "note": ("交节表按 UTC+08 比较实际瞬间；地点时钟用于日时干支。" if aware else
                 "未提供目标时区；交节仅按输入钟面与历表比较，不能确认交节两侧的唯一盘，请补目标时区。"),
    }


def solar_term_boundaries(start: datetime, end: datetime) -> tuple[datetime, ...]:
    """All term instants strictly inside an aware interval, using the same UTC+08 table."""
    require_lunar()
    from lunar_python import Solar
    terms: set[datetime] = set()
    required = set(YANG_JIE_QI) | set(YIN_JIE_QI)
    for year in range(start.astimezone(CALENDAR_ZONE).year, end.astimezone(CALENDAR_ZONE).year + 1):
        table = Solar.fromYmdHms(year, 7, 1, 12, 0, 0).getLunar().getJieQiTable()
        if not required.issubset(table):
            raise ValueError(f'{year} 节气表不完整，不能保证择时区间覆盖')
        for value in table.values():
            boundary = datetime(value.getYear(), value.getMonth(), value.getDay(),
                                value.getHour(), value.getMinute(), value.getSecond(),
                                tzinfo=CALENDAR_ZONE).astimezone(UTC)
            if start < boundary < end:
                terms.add(boundary)
    return tuple(sorted(terms))


def zhi_shi_position(origin: int, hour_ganzhi: str, ju_type: str) -> tuple[int, int]:
    """值使自旬首原宫沿一至九宫顺逆计数；只在数完后将中五寄坤二。"""
    if not 1 <= origin <= 9 or ju_type not in {"阳遁", "阴遁"}:
        raise ValueError("invalid 值使起宫或遁法")
    step = jiazi_index(hour_ganzhi[0], hour_ganzhi[1]) % 10
    sign = 1 if ju_type == "阳遁" else -1
    raw = (origin - 1 + sign * step) % 9 + 1
    return raw, 2 if raw == 5 else raw
