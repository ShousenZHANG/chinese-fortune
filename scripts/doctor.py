"""Install check: one command that says whether this copy works and what to fix.

Every other tool fails on its own first missing piece; a new user then has to
guess whether the cause is Python, a partial download, a broken system zoneinfo
or a terminal encoding. This runs each prerequisite in order, stops nothing on
the first failure, and gives the next action for the first one that failed.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from utils import VENDORED_MISSING, __version__, ensure_utf8_stdio, json_print

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
# Every data file under assets/ that some tool loads; tests keep this list equal
# to the directory, so a new asset cannot ship without doctor checking it.
REQUIRED_ASSETS = ('64hex.json', 'bazi_rules.json', 'cities_cn.json', 'classical_evidence.json',
                   'facsimile_witnesses.json', 'geju_rules.json', 'han-variants.json', 'jiemeng.json',
                   'life_guide.json', 'luck_rules.json', 'method_rules.json', 'name_bihua.json', 'shensha.json',
                   'tarot78.json', 'tiaohou.json', 'tiaohou_provenance.json')
# A fictional birth with a published answer: 2000-01-15 10:30 Beijing time.
REFERENCE = {'args': ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10', '--minute', '30',
                      '--gender', 'male', '--timezone', 'Asia/Shanghai', '--longitude', '116.4'],
             'pillars': ('己卯', '丁丑', '壬申', '乙巳')}


def _check(name: str, ok: bool, detail: str, fix: str = '') -> dict:
    return {'name': name, 'ok': ok, 'detail': detail, **({} if ok else {'fix': fix})}


def check_python() -> dict:
    version = '.'.join(map(str, sys.version_info[:3]))
    return _check('python', sys.version_info >= (3, 9), f'{version} at {sys.executable}',
                  '安装 Python 3.9 或更新版本，再用 python3、python 或 py -3 运行')


def check_record(package: str) -> dict:
    """Every vendored file must match the hash its dist-info RECORD published."""
    name = f'vendored:{package}'
    infos = sorted(SCRIPTS.glob(f'{package}-*.dist-info'))
    if not infos:
        return _check(name, False, 'dist-info 缺失', VENDORED_MISSING)
    rows = csv.reader((infos[-1] / 'RECORD').read_text(encoding='utf-8').splitlines())
    bad = []
    for row in rows:
        if len(row) < 2 or not row[0].startswith(package + '/') or not row[1]:
            continue
        path = SCRIPTS / row[0]
        algorithm, expected = row[1].split('=', 1)
        actual = hashlib.new(algorithm, path.read_bytes()).digest() if path.is_file() else b''
        if base64.urlsafe_b64encode(actual).rstrip(b'=').decode() != expected:
            bad.append(row[0])
    version = infos[-1].name.removeprefix(package + '-').removesuffix('.dist-info')
    return _check(name, not bad, f'{version}；' + ('文件与发布哈希一致' if not bad else '不一致：' + '、'.join(bad[:5])),
                  VENDORED_MISSING)


def check_timezone() -> dict:
    """Historical offsets need real tzdata: Shanghai kept summer time in 1990."""
    try:
        from zoneinfo import ZoneInfo
        offset = datetime(1990, 5, 10, 14, tzinfo=ZoneInfo('Asia/Shanghai')).utcoffset()
    except Exception as exc:  # noqa: BLE001 - any failure here is the finding
        return _check('timezone_history', False, f'{type(exc).__name__}: {exc}',
                      '清空 PYTHONTZPATH 环境变量后重试；仍失败请重新下载完整技能包')
    hours = offset.total_seconds() / 3600 if offset else None
    return _check('timezone_history', hours == 9, f'Asia/Shanghai 1990-05-10 UTC{hours:+g}' if hours is not None else '无偏移',
                  '系统时区库缺历史夏令时；清空 PYTHONTZPATH，让程序使用随包 tzdata')


def check_library() -> dict:
    from classical_search import validate_library
    result = validate_library()
    books = result.get('books', [])
    return _check('classical_library', bool(result.get('ok')),
                  f"{len(books)} 本，{sum(b.get('passages', 0) for b in books)} 段" if result.get('ok')
                  else '；'.join(result.get('errors', [])[:3]),
                  '古籍文件缺失或被改动：重新下载完整技能包，不要手改 knowledge/')


def check_assets() -> dict:
    """Every data file the tools load must be present and parse; a missing one is not 'fewer files'."""
    missing, broken = [], []
    for name in REQUIRED_ASSETS:
        path = ROOT / 'assets' / name
        if not path.is_file():
            missing.append(name)
            continue
        try:
            json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            broken.append(name)
    problems = ([f"缺少：{'、'.join(missing)}"] if missing else []) + ([f"读不出：{'、'.join(broken)}"] if broken else [])
    return _check('assets', not problems,
                  f'{len(REQUIRED_ASSETS)} 个数据文件齐全可读' if not problems else '；'.join(problems),
                  '数据文件缺失或损坏：重新下载完整技能包')


def check_reference_chart() -> dict:
    from bazi_calc import build_parser, calculate_bazi
    chart = calculate_bazi(build_parser().parse_args(REFERENCE['args']))
    got = tuple(chart.get('four_pillars', {}).get(k, {}).get('ganzhi') for k in ('year', 'month', 'day', 'hour'))
    return _check('reference_chart', got == tuple(REFERENCE['pillars']),
                  '虚构样例 2000-01-15 10:30 北京：' + ' '.join(map(str, got)),
                  '排盘结果和已知答案不同：先看上面哪项失败；都正常时请带本输出报告问题')


def run_checks() -> list[dict]:
    checks = [check_python()]
    steps = (('vendored:lunar_python', lambda: check_record('lunar_python')),
             ('vendored:tzdata', lambda: check_record('tzdata')), ('timezone_history', check_timezone),
             ('classical_library', check_library), ('assets', check_assets),
             ('reference_chart', check_reference_chart))
    for name, step in steps:
        try:
            checks.append(step())
        except Exception as exc:  # noqa: BLE001 - report and keep checking the rest
            checks.append(_check(name, False, f'{type(exc).__name__}: {exc}', '重新下载完整技能包后再运行 doctor'))
    return checks


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    argparse.ArgumentParser(description='安装自检：Python、随包依赖、时区历史、古籍、数据文件、样例排盘',
                            epilog='Top-level JSON keys: ok tool version healthy checks next_step').parse_args(argv)
    checks = run_checks()
    failed = next((c for c in checks if not c['ok']), None)
    json_print({'ok': True, 'tool': 'doctor', 'version': __version__, 'healthy': failed is None,
                'checks': checks,
                'next_step': f"{failed['name']}：{failed['fix']}" if failed else '安装正常，可以直接使用全部功能'})
    return 0 if failed is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
