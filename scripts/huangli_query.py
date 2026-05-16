"""Daily 黄历 / 老黄历 query — almanac for a specific solar date.

Usage:
    python huangli_query.py [--date YYYY-MM-DD]

Outputs JSON with: 公历, 农历, 干支, 12 建除值神, 28 宿, 宜, 忌,
吉时/凶时, 喜神/财神/福神/贵神方位, 彭祖百忌, 胎神方位, 冲煞.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Optional

from utils import json_print, require_lunar, warn


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _safe_method(obj, name: str, default=None):
    """Call an optional method by name across lunar_python versions."""
    try:
        fn = getattr(obj, name)
    except AttributeError:
        return default
    return _safe(fn, default)


def _hour_pillars(lunar) -> list[dict]:
    """For each of the 12 双小时, return ganzhi + ji/xiong markers."""
    out: list[dict] = []
    try:
        shichen_list = lunar.getTimes()
        # Some versions: getShichenJiXiong / getTimeJiXiong.
    except Exception:
        shichen_list = []

    # Fallback: build 12 time entries by iterating over hour 0..23 step 2
    try:
        from lunar_python import Solar  # type: ignore
        solar = lunar.getSolar()
        for hour_pair in range(0, 24, 2):
            # 子时归当日 (sect=2). Use middle of the 2-hour window for safety.
            h = hour_pair if hour_pair != 23 else 23
            s = Solar.fromYmdHms(solar.getYear(), solar.getMonth(),
                                 solar.getDay(), h, 30, 0)
            lh = s.getLunar()
            time_in_gz = lh.getTimeInGanZhi()
            # ji or xiong
            try:
                jx = lh.getTimeXun()  # not exactly ji/xiong but provides 旬
            except Exception:
                jx = None
            try:
                yixion = lh.getTimeYi()
                ji = lh.getTimeJi()
                chong_sha = lh.getTimeChongDesc()
            except Exception:
                yixion = []
                ji = []
                chong_sha = None
            out.append({
                "hour_range": f"{hour_pair:02d}:00-{(hour_pair+2)%24:02d}:00",
                "ganzhi": time_in_gz,
                "yi": yixion,
                "ji": ji,
                "chong_sha": chong_sha,
            })
    except Exception as e:
        warn(f"hour pillars failed: {e}")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="黄历日历查询 (今日宜忌 / 神位 / 吉凶时辰)"
    )
    p.add_argument("--date", type=str, default=None,
                   help="日期 YYYY-MM-DD (默认今日)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    require_lunar()
    from lunar_python import Solar  # type: ignore

    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError as e:
            json_print({"error": "invalid_date_format",
                        "message": str(e), "expected": "YYYY-MM-DD"})
            return 1
    else:
        dt = datetime.now()

    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, 12, 0, 0)
    lunar = solar.getLunar()

    # Almanac entries (lunar_python provides rich daily info)
    day_yi = _safe_method(lunar, "getDayYi", [])
    day_ji = _safe_method(lunar, "getDayJi", [])
    zhi_xing = _safe_method(lunar, "getZhiXing", None)
    xiu = _safe_method(lunar, "getXiu", None)
    zheng = _safe_method(lunar, "getZheng", None)
    animal_28 = _safe_method(lunar, "getAnimal", None)

    xi_shen = _safe_method(lunar, "getDayPositionXi", None)        # 喜神方位
    cai_shen = _safe_method(lunar, "getDayPositionCai", None)      # 财神方位
    fu_shen = _safe_method(lunar, "getDayPositionFu", None)        # 福神方位
    yang_gui = _safe_method(lunar, "getDayPositionYangGui", None)  # 阳贵神
    yin_gui = _safe_method(lunar, "getDayPositionYinGui", None)    # 阴贵神

    tai_shen = _safe_method(lunar, "getDayPositionTai", None)
    tai_shen_desc = _safe_method(lunar, "getDayPositionTaiDesc", None)

    chong = _safe_method(lunar, "getDayChongDesc", None) or _safe_method(lunar, "getDayChongGan", None)
    sha = _safe_method(lunar, "getDaySha", None)

    peng_zu_gan = _safe_method(lunar, "getPengZuGan", None)
    peng_zu_zhi = _safe_method(lunar, "getPengZuZhi", None)

    # 今日吉时/凶时
    ji_xiong_shichen = _hour_pillars(lunar)
    ji_shi = [s for s in ji_xiong_shichen if s.get("yi")]
    xiong_shi = [s for s in ji_xiong_shichen if not s.get("yi") and s.get("ji")]

    # Nearest jieqi
    jieqi_now = _safe(lunar.getJieQi, None)
    prev_jq = _safe(lunar.getPrevJieQi, None)
    next_jq = _safe(lunar.getNextJieQi, None)

    out = {
        "input": vars(args),
        "solar_date": {
            "iso": f"{solar.getYear():04d}-{solar.getMonth():02d}-{solar.getDay():02d}",
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(),
        },
        "lunar_date": {
            "year": lunar.getYear(), "month": lunar.getMonth(), "day": lunar.getDay(),
            "year_chinese": lunar.getYearInChinese(),
            "month_chinese": lunar.getMonthInChinese(),
            "day_chinese": lunar.getDayInChinese(),
            "zodiac": lunar.getYearShengXiao(),
        },
        "ganzhi": {
            "year": lunar.getYearInGanZhi(),
            "month": lunar.getMonthInGanZhi(),
            "day": lunar.getDayInGanZhi(),
        },
        "zhi_shen_12jianchu": zhi_xing,
        "xiu_28": {
            "xiu": xiu, "zheng": zheng, "animal": animal_28,
            "full": (f"{xiu}{zheng}{animal_28}" if xiu else None),
        },
        "yi": day_yi,
        "ji": day_ji,
        "ji_shi": ji_shi,
        "xiong_shi": xiong_shi,
        "shichen_detail": ji_xiong_shichen,
        "directions": {
            "喜神": xi_shen,
            "财神": cai_shen,
            "福神": fu_shen,
            "阳贵神": yang_gui,
            "阴贵神": yin_gui,
        },
        "peng_zu_bai_ji": {
            "gan": peng_zu_gan, "zhi": peng_zu_zhi,
        },
        "tai_shen_fang_wei": {
            "position": tai_shen, "desc": tai_shen_desc,
        },
        "chong_sha": {
            "chong": chong, "sha": sha,
        },
        "jieqi": {
            "today": jieqi_now,
            "prev": {"name": prev_jq.getName(), "solar": str(prev_jq.getSolar())} if prev_jq else None,
            "next": {"name": next_jq.getName(), "solar": str(next_jq.getSolar())} if next_jq else None,
        },
    }

    json_print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
