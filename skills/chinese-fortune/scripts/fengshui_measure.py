"""风水测量合同：把罗盘或手机测得的角度换成二十四山坐向，测量事实与传统分类分开写，误差跨山时不取整。

传统部分只做分类，依据《协纪辨方书》卷二：
- 二十四山由四维卦、八干、十二支组成，「言山則向在其中，如子山則必午向」（xieji:c002:p0009）。
- 一卦管三山：戌乾亥属乾、壬子癸属坎……（同段）。
- 三针：正针「二十四山之正位，定向用之」；中针子位在正针壬子之间，「比正針先半位」；缝针子位在子癸之缝
  （xieji:c002:p0011、p0012）。

每山 15° 是把二十四方位等分得来的（原文说二十四位，没写度数）。测量部分（参照北、磁偏角、误差区间）是现代
测量约定，不出自古籍。这里不判吉凶，不排宅盘。

CLI:
    python fengshui_measure.py --bearing 92 --of facing --reference magnetic --error 3
"""
from __future__ import annotations

import argparse
import math
import sys

from utils import __version__, ensure_utf8_stdio, error_envelope, json_print

# 子山居 0°，顺时针每 15° 一山。
MOUNTAINS = ('子', '癸', '丑', '艮', '寅', '甲', '卯', '乙', '辰', '巽', '巳', '丙',
             '午', '丁', '未', '坤', '申', '庚', '酉', '辛', '戌', '乾', '亥', '壬')
PALACE = {'戌': '乾', '乾': '乾', '亥': '乾', '壬': '坎', '子': '坎', '癸': '坎', '丑': '艮', '艮': '艮', '寅': '艮',
          '甲': '震', '卯': '震', '乙': '震', '辰': '巽', '巽': '巽', '巳': '巽', '丙': '离', '午': '离', '丁': '离',
          '未': '坤', '坤': '坤', '申': '坤', '庚': '兑', '酉': '兑', '辛': '兑'}
STEP = 15.0
# 中针比正针先半位（子位在壬子之间），缝针子位在子癸之缝：相对正针各转 -7.5°、+7.5°。
NEEDLE_SHIFT = {'zheng': 0.0, 'zhong': -7.5, 'feng': 7.5}
NEEDLE_USE = {'zheng': '正针：二十四山正位，定向用之', 'zhong': '中针：地理家格龙用之',
              'feng': '缝针：消砂纳水用之'}
SOURCES = ['xieji:c002:p0009', 'xieji:c002:p0011', 'xieji:c002:p0012']
MAX_ERROR = 45.0


def norm(deg: float) -> float:
    return deg % 360.0


def mountain_at(deg: float, needle: str = 'zheng') -> int:
    return int(norm(deg - NEEDLE_SHIFT[needle] + STEP / 2) // STEP) % 24


def span(index: int, needle: str = 'zheng') -> tuple[float, float]:
    start = norm(index * STEP - STEP / 2 + NEEDLE_SHIFT[needle])
    return start, norm(start + STEP)


def _overlap(lo: float, width: float, start: float) -> float:
    """Degrees of [lo, lo+width] (circular) that fall inside [start, start+15)."""
    total = 0.0
    for shift in (-360.0, 0.0, 360.0):
        a, b = max(lo, start + shift), min(lo + width, start + shift + STEP)
        total += max(0.0, b - a)
    return total


def classify(deg: float, error: float, needle: str = 'zheng') -> dict:
    centre = mountain_at(deg, needle)
    start, end = span(centre, needle)
    lo = norm(deg - error)
    candidates = []
    for i in range(24):
        covered = _overlap(lo, 2 * error, span(i, needle)[0]) if error else (STEP if i == centre else 0.0)
        if covered > 1e-9:
            candidates.append({'mountain': MOUNTAINS[i], 'palace': PALACE[MOUNTAINS[i]],
                               'span': list(span(i, needle)), 'degrees_within_error': round(covered, 2)})
    to_boundary = min((deg - start) % 360.0, (end - deg) % 360.0)
    return {'bearing': round(norm(deg), 2), 'mountain': MOUNTAINS[centre], 'palace': PALACE[MOUNTAINS[centre]],
            'span': [start, end], 'distance_to_boundary': round(to_boundary, 2),
            'candidates': candidates, 'ambiguous': len(candidates) > 1}


def measure(bearing: float, of: str, reference: str, error: float, declination: float | None,
            needle: str = 'zheng') -> dict:
    converted, used = bearing, reference
    if reference == 'magnetic' and declination is not None:
        converted, used = norm(bearing + declination), 'true'  # 东偏为正：真方位 = 磁方位 + 偏角
    facing = converted if of == 'facing' else norm(converted + 180)
    sitting = norm(facing + 180)
    face, sit = classify(facing, error, needle), classify(sitting, error, needle)
    measurement = {'input_bearing': bearing, 'measured': of, 'reference_in': reference, 'declination': declination,
                   'reference_used': used, 'bearing_used': round(converted, 2), 'error': error,
                   'facing_interval': [round(norm(facing - error), 2), round(norm(facing + error), 2)],
                   'note': ('真方位 = 磁方位 + 磁偏角（东偏为正）' if used == 'true' and reference == 'magnetic' else
                            '按输入的参照北直接分类；磁北与真北相差当地磁偏角，未给偏角时不换算')}
    tradition = {'needle': needle, 'needle_use': NEEDLE_USE[needle], 'facing': face, 'sitting': sit,
                 'pair': f"坐{sit['mountain']}向{face['mountain']}", 'sources': SOURCES,
                 'division': '二十四位等分，每山 15°（原文只说二十四方位，度数为等分推出）',
                 'scope': '只做坐向分类，不判吉凶，不排宅盘'}
    what = '朝向' if of == 'facing' else '坐向'
    north_in = '磁北' if reference == 'magnetic' else '真北'
    head = f"测得{what} {bearing:g}°（按{north_in}，误差 ±{error:g}°）"
    if reference == 'magnetic' and used == 'true':
        head += f"，加磁偏角 {declination:+g}° 换成真北 {converted:g}°"
    if face['ambiguous']:
        names = '、'.join(c['mountain'] for c in face['candidates'])
        say = f"{head}：误差范围跨{names}几山，坐向要复测，不能取整定成一山。"
    else:
        say = (f"{head}：{tradition['pair']}，向在{face['mountain']}山（{face['palace']}宫），"
               f"离最近分界 {face['distance_to_boundary']:g}°，误差内不跨山。")
    return {'measurement': measurement, 'tradition': tradition, 'say': say}


EPILOG = """Top-level JSON keys on stdout (UTF-8):
  ok tool version input measurement tradition say

On error: {"ok": false, "error": ..., "message": ...} and exit 1."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='风水测量合同：角度换二十四山坐向，测量与传统分开，误差跨山不取整',
                                epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--bearing', type=float, required=True, help='测得的角度 0–360，北为 0，顺时针')
    p.add_argument('--of', choices=('facing', 'sitting'), required=True, help='这个角度是朝向（向）还是坐向（坐）')
    p.add_argument('--reference', choices=('magnetic', 'true'), required=True,
                   help='角度相对磁北（罗盘、多数手机指南针）还是真北（地图）')
    p.add_argument('--declination', type=float, default=None, help='当地磁偏角，东偏为正；给了就把磁方位换成真方位')
    p.add_argument('--error', type=float, required=True, help=f'测量误差 ±度数（0–{MAX_ERROR:g}），手机指南针常有几度')
    p.add_argument('--needle', choices=tuple(NEEDLE_SHIFT), default='zheng', help='罗盘盘层：正针（默认，定向）、中针、缝针')
    return p


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if not math.isfinite(args.bearing) or not 0 <= args.bearing <= 360:
        json_print(error_envelope('fengshui_measure', 'invalid_input', '角度须在 0–360 之间'))
        return 1
    if not math.isfinite(args.error) or not 0 <= args.error <= MAX_ERROR:
        json_print(error_envelope('fengshui_measure', 'invalid_input', f'误差须在 0–{MAX_ERROR:g} 度之间'))
        return 1
    if args.declination is not None and (not math.isfinite(args.declination) or abs(args.declination) > 30):
        json_print(error_envelope('fengshui_measure', 'invalid_input', '磁偏角须在 -30–30 度之间'))
        return 1
    if args.declination is not None and args.reference == 'true':
        json_print(error_envelope('fengshui_measure', 'invalid_input', '真北读数不需要磁偏角；要换算请把 --reference 设为 magnetic'))
        return 1
    result = measure(args.bearing, args.of, args.reference, args.error, args.declination, args.needle)
    json_print({'ok': True, 'tool': 'fengshui_measure', 'version': __version__, 'input': vars(args), **result})
    return 0


if __name__ == '__main__':
    sys.exit(main())
