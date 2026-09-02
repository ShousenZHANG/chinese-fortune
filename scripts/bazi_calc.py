"""Compute a full BaZi (八字) chart.

Outputs four pillars, hidden stems, 十神, weighted 五行 distribution, 日主旺衰,
35 神煞 (driven by assets/shensha.json), 用神/喜神/忌神 (扶抑 + 调候 combined),
格局 detection (special-format priority then 月令本气透干), 干支互动
(合冲刑害三合三会), 纳音, 大运 sequence with 起运岁, and 流年 hints.

Backed by lunar_python for the calendrical math; assets/shensha.json for 神煞
qi-fa tables; assets/tiaohou.json (if present) for 调候用神 climate balance.

Usage:
    python bazi_calc.py --year 1990 --month 5 --day 10 --hour 14 --minute 30 \\
        --gender male --tz 8 --longitude 116.4

Optional flags:
    --no-shensha    skip 神煞 detection
    --no-yongshen   skip 用神/喜神/忌神
    --no-geju       skip 格局 detection
    --lunar         treat input as 农历

Output: pretty UTF-8 JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from bazi_geju import _shi_shen_safe, detect_ge_ju
from bazi_shensha import detect_all_shensha
from bazi_strength import day_master_strength, select_yong_shen, weighted_wuxing
from bazi_tables import (
    DIZHI_CHONG,
    DIZHI_HAI,
    DIZHI_LIU_HE,
    PILLAR_LABELS_CN,
    SAN_HE_GROUPS,
    SAN_HUI_GROUPS,
    SAN_XING_PAIRS,
    SAN_XING_SELF,
    SAN_XING_TRIPLES,
    TIANGAN_HE,
)
from utils import (
    DIZHI_WUXING,
    DIZHI_YIN_YANG,
    DIZHI_ZODIAC,
    HIDDEN_STEMS,
    TIANGAN_WUXING,
    TIANGAN_YIN_YANG,
    __version__,
    ensure_utf8_stdio,
    json_print,
    longitude_correction,
    require_lunar,
    true_solar_time_info,
    warn,
)

VERSION = __version__
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


# --------------------------------------------------------------------------- #
# Asset loading (graceful degradation if files absent)
# --------------------------------------------------------------------------- #

def _load_json(name: str) -> dict | None:
    path = ASSETS_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        warn(f"failed to load {name}: {e}")
        return None



# 干支 互动 detection
# --------------------------------------------------------------------------- #

PILLAR_ORDER: list[str] = ["year", "month", "day", "hour"]


def detect_interactions(pillars: dict[str, dict]) -> dict:
    # Only the pillars actually present — a three-pillar chart has no 时柱.
    present = [p for p in PILLAR_ORDER if p in pillars]
    stems = [pillars[p]["stem"] for p in present]
    branches = [pillars[p]["branch"] for p in present]

    out: dict[str, list] = {
        "tiangan_he": [],
        "dizhi_liu_he": [],
        "san_he": [],
        "san_hui": [],
        "dizhi_chong": [],
        "dizhi_hai": [],
        "dizhi_xing": [],
    }

    # 天干五合
    for i in range(len(stems)):
        for j in range(i + 1, len(stems)):
            pair = frozenset([stems[i], stems[j]])
            if pair in TIANGAN_HE:
                out["tiangan_he"].append({
                    "pair": [stems[i], stems[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "干",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "干",
                    ],
                    "transforms_to": TIANGAN_HE[pair],
                })

    # 地支六合
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            pair = frozenset([branches[i], branches[j]])
            if pair in DIZHI_LIU_HE:
                out["dizhi_liu_he"].append({
                    "pair": [branches[i], branches[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "支",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "支",
                    ],
                    "transforms_to": DIZHI_LIU_HE[pair],
                })

    # 地支三合 (全合 or 半合: 三合首字+中字, 中字+末字, 首字+末字)
    bset = set(branches)
    for trio, wx in SAN_HE_GROUPS:
        present = [b for b in trio if b in bset]
        if len(present) >= 2:
            out["san_he"].append({
                "branches": present,
                "type": "全合" if len(present) == 3 else "半合",
                "transforms_to": wx,
            })

    # 地支三会
    for trio, wx in SAN_HUI_GROUPS:
        present = [b for b in trio if b in bset]
        if len(present) >= 2:
            out["san_hui"].append({
                "branches": present,
                "type": "全会" if len(present) == 3 else "半会",
                "transforms_to": wx,
            })

    # 地支六冲
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            pair = frozenset([branches[i], branches[j]])
            if pair in DIZHI_CHONG and branches[i] != branches[j]:
                out["dizhi_chong"].append({
                    "pair": [branches[i], branches[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "支",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "支",
                    ],
                })

    # 地支六害
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            pair = frozenset([branches[i], branches[j]])
            if pair in DIZHI_HAI and branches[i] != branches[j]:
                out["dizhi_hai"].append({
                    "pair": [branches[i], branches[j]],
                    "positions": [
                        PILLAR_LABELS_CN[PILLAR_ORDER[i]] + "支",
                        PILLAR_LABELS_CN[PILLAR_ORDER[j]] + "支",
                    ],
                })

    # 三刑 (三字)
    for trio in SAN_XING_TRIPLES:
        present = [b for b in trio if b in bset]
        if len(present) >= 2:
            out["dizhi_xing"].append({
                "branches": present,
                "type": "三刑" if len(present) == 3 else "半刑",
            })
    for pair in SAN_XING_PAIRS:
        if pair.issubset(bset):
            out["dizhi_xing"].append({
                "branches": list(pair),
                "type": "互刑",
            })
    for self_b in SAN_XING_SELF:
        if branches.count(self_b) >= 2:
            out["dizhi_xing"].append({
                "branches": [self_b, self_b],
                "type": "自刑",
            })

    return out


# --------------------------------------------------------------------------- #
# Pillar helpers
# --------------------------------------------------------------------------- #

def pillar_dict(stem: str, branch: str, nayin: str) -> dict:
    return {
        "stem": stem,
        "branch": branch,
        "ganzhi": f"{stem}{branch}",
        "stem_wuxing": TIANGAN_WUXING.get(stem),
        "branch_wuxing": DIZHI_WUXING.get(branch),
        "stem_yin_yang": TIANGAN_YIN_YANG.get(stem),
        "branch_yin_yang": DIZHI_YIN_YANG.get(branch),
        "hidden_stems": HIDDEN_STEMS.get(branch, []),
        "nayin": nayin,
        "zodiac": DIZHI_ZODIAC.get(branch),
    }


def ten_gods_per_pillar(day_stem: str, pillars: dict) -> dict:
    out: dict = {}
    for label, p in pillars.items():
        entry: dict = {"stem": None, "hidden": []}
        if label == "day":
            entry["stem"] = "日主"
        else:
            entry["stem"] = _shi_shen_safe(day_stem, p["stem"])
        for hs in p["hidden_stems"]:
            entry["hidden"].append({"stem": hs, "shi_shen": _shi_shen_safe(day_stem, hs)})
        out[label] = entry
    return out


# --------------------------------------------------------------------------- #
# Argparse
# --------------------------------------------------------------------------- #

EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version hour_known notes input true_solar_time solar_date
  lunar_date four_pillars
  day_master ten_gods wuxing_count day_master_strength interactions shen_sha
  yong_shen xi_shen ji_shen ge_ju na_yin qi_yun da_yun liu_nian

qi_yun: years months days text (起运 duration, 周岁).
da_yun[]: start_age/end_age are 周岁 anchored to qi_yun.years;
  start_age_xusui is the 虚岁 equivalent.

On error: {"error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="八字排盘 v1.1 — 公历/农历, 含 35 神煞 / 用神 / 格局 / 干支互动"
    ,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--year", type=int, required=True, help="出生年 (公历或农历)")
    p.add_argument("--month", type=int, required=True, help="出生月 1-12")
    p.add_argument("--day", type=int, required=True, help="出生日 1-31")
    p.add_argument("--hour", type=int, default=None,
                   help="出生时 0-23; 省略则走三柱模式 (时柱待补, 不揣测时辰)")
    p.add_argument("--minute", type=int, default=0, help="出生分 0-59")
    p.add_argument("--gender", choices=["male", "female"], required=True,
                   help="性别 (用于排大运 + 天罗地网)")
    p.add_argument("--tz", type=float, default=8.0,
                   help="时区偏移小时 (默认 8 即 GMT+8)")
    p.add_argument("--longitude", type=float, default=120.0,
                   help="出生地经度 (E°, 默认 120, 用于真太阳时)")
    p.add_argument("--lunar", action="store_true",
                   help="若指定, 视输入日期为农历")
    p.add_argument("--years", type=int, default=80,
                   help="大运覆盖年数 (默认 80)")
    p.add_argument("--no-shensha", action="store_true",
                   help="跳过 35 神煞 检测")
    p.add_argument("--no-yongshen", action="store_true",
                   help="跳过 用神/喜神/忌神 计算")
    p.add_argument("--no-geju", action="store_true",
                   help="跳过 格局 判定")
    p.add_argument("--as-of-year", type=int, default=None,
                   help="流年起算年份 (默认当前年; 指定后输出确定可复现)")
    return p


def _validate_args(args) -> str | None:
    """Boundary-validate inputs before touching lunar_python.

    Returns an error message string if invalid, else None.
    """
    if not 1 <= args.month <= 12:
        return f"month 必须在 1-12, 收到 {args.month}"
    if not 1 <= args.day <= 31:
        return f"day 必须在 1-31, 收到 {args.day}"
    if args.hour is not None and not 0 <= args.hour <= 23:
        return f"hour 必须在 0-23, 收到 {args.hour}"
    if not 0 <= args.minute <= 59:
        return f"minute 必须在 0-59, 收到 {args.minute}"
    # lunar_python supports roughly 1900-2100.
    if not 1900 <= args.year <= 2100:
        return f"year 超出支持范围 1900-2100, 收到 {args.year}"
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)

    err = _validate_args(args)
    if err:
        json_print({
            "ok": False, "tool": "bazi", "version": VERSION,
            "error": "invalid_input", "message": err, "input": vars(args),
        })
        return 1

    require_lunar()
    from lunar_python import Lunar, Solar  # type: ignore

    # 真太阳时 info (informational + applied)
    # 时辰未知 -> three-pillar mode. Noon is used only to obtain the 年/月/日柱
    # (it cannot cross a day boundary); no 时柱 is derived from it, and every
    # aggregate below is computed over six characters instead of eight.
    # references/00-intake.md: 时辰未知 → 仍可排年/月/日柱; 时柱缺如, 不揣测时辰.
    hour_known = args.hour is not None
    eff_hour = args.hour if hour_known else 12
    eff_minute = args.minute if hour_known else 0

    try:
        tst_info = true_solar_time_info(
            longitude=args.longitude,
            tz_offset_hours=args.tz,
            year=args.year,
            month=args.month,
            day=args.day,
            hour=eff_hour,
            minute=eff_minute,
        )
        tst_info["applied"] = True
    except Exception as e:
        warn(f"true_solar_time_info failed: {e}")
        tst_info = {"applied": False, "error": str(e)}
    if not hour_known:
        tst_info = {"applied": False, "reason": "时辰未知, 无法校正真太阳时"}

    # Apply correction for pillar computation (incl. day roll-over near midnight)
    day_offset, corr_hour, corr_minute = longitude_correction(
        eff_hour, eff_minute, args.longitude, args.tz,
        year=args.year, month=args.month, day=args.day,
    )
    if not hour_known:
        day_offset = 0  # noon cannot roll into an adjacent day
    corr_year, corr_month, corr_day = args.year, args.month, args.day
    if day_offset != 0:
        from datetime import date, timedelta
        _d = date(args.year, args.month, args.day) + timedelta(days=day_offset)
        corr_year, corr_month, corr_day = _d.year, _d.month, _d.day

    try:
        if args.lunar:
            lunar = Lunar.fromYmdHms(
                corr_year, corr_month, corr_day, corr_hour, corr_minute, 0
            )
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(
                corr_year, corr_month, corr_day, corr_hour, corr_minute, 0
            )
            lunar = solar.getLunar()
    except Exception as e:
        json_print({
            "ok": False,
            "tool": "bazi",
            "version": VERSION,
            "error": "invalid_date",
            "message": str(e),
            "input": vars(args),
        })
        return 1

    try:
        eight = lunar.getEightChar()
    except Exception as e:
        json_print({
            "ok": False,
            "tool": "bazi",
            "version": VERSION,
            "error": "bazi_failed",
            "message": str(e),
            "input": vars(args),
        })
        return 1

    try:
        eight.setSect(2)
    except Exception:
        pass

    year_gz = (eight.getYearGan(), eight.getYearZhi())
    month_gz = (eight.getMonthGan(), eight.getMonthZhi())
    day_gz = (eight.getDayGan(), eight.getDayZhi())
    hour_gz = (eight.getTimeGan(), eight.getTimeZhi())

    year_nayin = eight.getYearNaYin()
    month_nayin = eight.getMonthNaYin()
    day_nayin = eight.getDayNaYin()
    hour_nayin = eight.getTimeNaYin()

    pillars = {
        "year":  pillar_dict(*year_gz,  year_nayin),
        "month": pillar_dict(*month_gz, month_nayin),
        "day":   pillar_dict(*day_gz,   day_nayin),
    }
    if hour_known:
        pillars["hour"] = pillar_dict(*hour_gz, hour_nayin)

    day_stem = day_gz[0]
    day_branch = day_gz[1]
    day_ganzhi = day_stem + day_branch
    year_stem = year_gz[0]
    year_branch = year_gz[1]
    month_branch = month_gz[1]

    active = [p for p in PILLAR_ORDER if p in pillars]
    stems_map = {p: pillars[p]["stem"] for p in active}
    branches_map = {p: pillars[p]["branch"] for p in active}

    # 十神
    ten_gods = ten_gods_per_pillar(day_stem, pillars)

    # Weighted 五行
    weighted_counts, root_bonus = weighted_wuxing(pillars, day_stem)

    # Day-master strength
    strength = day_master_strength(day_stem, month_branch, weighted_counts, pillars)

    # 神煞
    shensha_list: list[dict] = []
    if not args.no_shensha:
        shensha_data = _load_json("shensha.json")
        shensha_list = detect_all_shensha(
            shensha_data,
            day_stem=day_stem,
            day_branch=day_branch,
            day_ganzhi=day_ganzhi,
            year_stem=year_stem,
            year_branch=year_branch,
            month_branch=month_branch,
            stems_map=stems_map,
            branches_map=branches_map,
            gender=args.gender,
        )

    # 干支 互动
    interactions = detect_interactions(pillars)

    # 用神 / 喜神 / 忌神
    yong_shen = xi_shen = ji_shen = None
    if not args.no_yongshen:
        tiaohou_data = _load_json("tiaohou.json")
        yj = select_yong_shen(
            day_stem, month_branch, strength, weighted_counts, tiaohou_data
        )
        yong_shen = yj["yong_shen"]
        xi_shen = yj["xi_shen"]
        ji_shen = yj["ji_shen"]

    # 格局
    ge_ju = None
    if not args.no_geju:
        ge_ju = detect_ge_ju(day_stem, pillars, weighted_counts, strength)

    # 大运
    da_yun_list: list[dict] = []
    qi_yun: dict | None = None
    try:
        yun = eight.getYun(1 if args.gender == "male" else 0)
        start_solar = yun.getStartSolar()
        # 起运 is a DURATION from birth (年/月/日), not an age: lunar_python's
        # Yun.getStartYear() is "years until 起运". 01-bazi.md §7.2 writes it as
        # 6岁4个月 and anchors every 大运 band to it — 起运6岁 -> 6—16, 16—26 —
        # so the band start is that figure in 周岁, stepping by 10.
        start_years = yun.getStartYear()
        start_months = yun.getStartMonth()
        start_days = yun.getStartDay()
        cycles = yun.getDaYun(args.years // 10 + 2)
        for d in cycles:
            ganzhi = d.getGanZhi()
            if not ganzhi:
                continue
            stem = ganzhi[0]
            branch = ganzhi[1] if len(ganzhi) > 1 else ""
            band = start_years + 10 * len(da_yun_list)
            da_yun_list.append({
                # 周岁, per 01-bazi.md §7.2. lunar_python's getStartAge() is
                # 虚岁 (one greater); kept beside it rather than passed off as 周岁.
                "start_age": band,
                "end_age": band + 10,
                "start_age_xusui": d.getStartAge(),
                "start_year": d.getStartYear(),
                "end_year": d.getEndYear(),
                "ganzhi": ganzhi,
                "stem": stem,
                "branch": branch,
                "shi_shen": _shi_shen_safe(day_stem, stem) if stem in TIANGAN_WUXING else "",
                "branch_wuxing": DIZHI_WUXING.get(branch),
            })
        remainder = (f"{start_months}个月" if start_months else "")
        qi_yun = {
            "start_year": start_solar.getYear(),
            "start_month": start_solar.getMonth(),
            "start_day": start_solar.getDay(),
            "years": start_years,
            "months": start_months,
            "days": start_days,
            "text": f"{start_years}岁{remainder}".rstrip(),
            "convention": "周岁; 大运各柱起讫岁数以此为基准 (01-bazi.md §7.2)",
        }
    except Exception as e:
        warn(f"da_yun unavailable: {e}")

    # 流年 — current solar year + next 5
    liu_nian: list[dict] = []
    try:
        from datetime import datetime
        now_year = args.as_of_year if args.as_of_year else datetime.now().year
        for y in range(now_year, now_year + 6):
            ly = Solar.fromYmdHms(y, 6, 1, 12, 0, 0).getLunar()
            gz = ly.getYearInGanZhi()
            year_stem_y = gz[0] if gz else ""
            liu_nian.append({
                "year": y,
                "ganzhi": gz,
                "zodiac": ly.getYearShengXiao(),
                "shi_shen": _shi_shen_safe(day_stem, year_stem_y) if year_stem_y in TIANGAN_WUXING else "",
            })
    except Exception as e:
        warn(f"liu_nian failed: {e}")

    result: dict[str, Any] = {
        "ok": True,
        "tool": "bazi",
        "version": VERSION,
        "input": vars(args),
        "true_solar_time": tst_info,
        "solar_date": {
            "year": solar.getYear(), "month": solar.getMonth(),
            "day": solar.getDay(), "hour": solar.getHour(),
            "minute": solar.getMinute(),
        },
        "lunar_date": {
            "year": lunar.getYear(), "month": lunar.getMonth(),
            "day": lunar.getDay(),
            "year_in_ganzhi": lunar.getYearInGanZhi(),
            "month_in_ganzhi": lunar.getMonthInGanZhi(),
            "day_in_ganzhi": lunar.getDayInGanZhi(),
            "time_in_ganzhi": lunar.getTimeInGanZhi(),
            "year_in_chinese": lunar.getYearInChinese(),
            "month_in_chinese": lunar.getMonthInChinese(),
            "day_in_chinese": lunar.getDayInChinese(),
            "zodiac": lunar.getYearShengXiao(),
        },
        "hour_known": hour_known,
        "notes": ([] if hour_known else
                  ["时柱待补: 未提供出生时辰, 已按三柱 (年/月/日) 论断; "
                   "五行得分/旺衰/用神/格局/神煞 均只计六字, 未揣测时辰。"]),
        "four_pillars": (pillars if hour_known else
                         {**pillars, "hour": {"status": "时柱待补"}}),
        "day_master": {
            "stem": day_stem,
            "wuxing": TIANGAN_WUXING.get(day_stem),
            "yin_yang": TIANGAN_YIN_YANG.get(day_stem),
        },
        "ten_gods": ten_gods,
        "wuxing_count": {
            "weighted": {k: round(v, 3) for k, v in weighted_counts.items()},
            "root_bonus": {k: round(v, 3) for k, v in root_bonus.items()},
        },
        "day_master_strength": strength,
        "interactions": interactions,
        "shen_sha": shensha_list,
        "yong_shen": yong_shen,
        "xi_shen": xi_shen,
        "ji_shen": ji_shen,
        "ge_ju": ge_ju,
        "na_yin": {
            "year": year_nayin, "month": month_nayin,
            "day": day_nayin,
            "hour": hour_nayin if hour_known else None,
        },
        "qi_yun": qi_yun,
        "da_yun": da_yun_list,
        "liu_nian": liu_nian,
    }

    json_print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
