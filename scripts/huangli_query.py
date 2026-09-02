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

from utils import ensure_utf8_stdio, json_print, require_lunar, warn


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
    """Return the queried day's 13 时辰 blocks: 早子 … 亥 … 夜子.

    时辰 boundaries follow the classical odd-start convention (丑 01-03,
    寅 03-05 … 亥 21-23) — NOT even clock blocks (00-02, 02-04 …), which
    straddle two 时辰 and mislabel the second half. Each block is sampled at
    its midpoint so 干支/天神 are correct for the whole block.

    子时 is emitted as TWO rows because one civil day contains two different
    子 时柱 under the 晚子时 (sect-2) convention this project uses throughout
    (see bazi_calc.setSect(2)):

        早子 00:00-01:00 → 时干 from 五鼠遁 of the queried day's 日干
        夜子 23:00-24:00 → 时干 from 五鼠遁 of the NEXT day's 日干

    Collapsing them into one 23:00-01:00 row (as before v1.4.0) forced that
    row to carry the next day's 干支/天神/冲煞 while the object's own
    ganzhi.day and chong_sha described the queried day.

    Rows are emitted in clock order, so 早子 … 亥 form a contiguous run of the
    六十甲子 and 夜子 closes the day.

    吉凶 comes from the hour's 天神 黄道/黑道 (getTimeTianShenLuck), NOT from
    whether the hour has any 宜 — every 时辰 has non-empty 宜, so the latter
    would mark all 12 as 吉.
    """
    out: list[dict] = []
    try:
        from lunar_python import Solar  # type: ignore
        solar = lunar.getSolar()
        # (label, 时辰, sample hour, displayed range) in clock order.
        blocks = [("早子", "子", 0, "00:00-01:00")]
        blocks += [(b, b, h, f"{h:02d}:00-{h + 2:02d}:00") for b, h in zip(
            "丑寅卯辰巳午未申酉戌亥", [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21],
            strict=True)]
        blocks.append(("夜子", "子", 23, "23:00-24:00"))
        for label, branch, start, rng in blocks:
            s = Solar.fromYmdHms(solar.getYear(), solar.getMonth(),
                                 solar.getDay(), start, 30, 0)
            lh = s.getLunar()
            out.append({
                "shichen": label,
                "branch": branch,
                "hour_range": rng,
                "ganzhi": lh.getTimeInGanZhi(),
                "tian_shen": _safe_method(lh, "getTimeTianShen", None),
                "huang_hei_dao": _safe_method(lh, "getTimeTianShenType", None),
                "luck": _safe_method(lh, "getTimeTianShenLuck", None),
                "yi": _safe_method(lh, "getTimeYi", []),
                "ji": _safe_method(lh, "getTimeJi", []),
                "chong_sha": _safe_method(lh, "getTimeChongDesc", None),
            })
    except Exception as e:
        warn(f"hour pillars failed: {e}")
    return out


EPILOG = """Top-level JSON keys on stdout (UTF-8):
  input solar_date lunar_date ganzhi zhi_shen_12jianchu xiu_28 yi ji
  ji_shi xiong_shi shichen_detail directions peng_zu_bai_ji
  tai_shen_fang_wei chong_sha jieqi

shichen_detail: 13 rows, 早子 00:00-01:00 ... 亥 ... 夜子 23:00-24:00.
  Each row: shichen branch hour_range ganzhi tian_shen huang_hei_dao
  luck yi ji chong_sha

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="黄历日历查询 (今日宜忌 / 神位 / 吉凶时辰)"
    ,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--date", type=str, default=None,
                   help="日期 YYYY-MM-DD (默认今日)")
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
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

    chong = _safe_method(lunar, "getDayChongDesc", None) or _safe_method(lunar, "getDayChongGan", None)
    sha = _safe_method(lunar, "getDaySha", None)

    peng_zu_gan = _safe_method(lunar, "getPengZuGan", None)
    peng_zu_zhi = _safe_method(lunar, "getPengZuZhi", None)

    # 今日吉时/凶时 — 按 时辰黄黑道吉凶 (黄道=吉, 黑道=凶), 非"有无宜事"
    ji_xiong_shichen = _hour_pillars(lunar)
    ji_shi = [s for s in ji_xiong_shichen if s.get("luck") == "吉"]
    xiong_shi = [s for s in ji_xiong_shichen if s.get("luck") == "凶"]

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
        # 胎神只有方位; lunar_python 无 getDayPositionTaiDesc, 旧的 desc 键
        # 恒为 None (勿改调 getDayPositionTaiSuiDesc —— 那是太岁不是胎神).
        "tai_shen_fang_wei": {
            "position": tai_shen,
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
