"""Build, install runtime dependencies in a fresh venv, and exercise the ZIP.

No globally installed packages or source-checkout imports are used by smoke commands.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path, *, expected: int = 0, data: str | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, input=data, capture_output=True,
                            text=True, encoding='utf-8', timeout=180)
    if result.returncode != expected:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}): '
                           f'{result.stdout[-2000:]}\n{result.stderr[-2000:]}')
    return result.stdout


def main() -> int:
    # TemporaryDirectory owns only this newly created, resolved temp child.
    base = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix='fortune-package-', dir=base) as directory:
        work = Path(directory).resolve()
        if work.parent != base:
            raise RuntimeError('unexpected temporary workspace')
        archive = work / 'skill.zip'
        run([sys.executable, str(ROOT / 'scripts/build_skill.py'), '--out', str(archive)], work)
        with zipfile.ZipFile(archive) as package:
            for name in package.namelist():
                if not (work / name).resolve().is_relative_to(work):
                    raise RuntimeError('unsafe archive member')
            package.extractall(work)
        skill = work / 'chinese-fortune'
        venv.EnvBuilder(with_pip=True).create(work / 'venv')
        python = work / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        run([str(python), '-m', 'pip', 'install', '-r', str(skill / 'scripts/requirements.txt'),
             '-c', str(skill / 'scripts/constraints-runtime.txt')], work)
        common = ['--year', '2000', '--month', '1', '--day', '15', '--hour', '10',
                  '--gender', 'male', '--timezone', 'Asia/Shanghai']
        outputs = {}
        for name in ('bazi_calc.py', 'ziwei_calc.py'):
            extra = ['--as-of-year', '2026'] if name == 'bazi_calc.py' else []
            outputs[name] = json.loads(run([str(python), '-X', 'utf8',
                                           str(skill / 'scripts' / name), *common, *extra], work))
            assert outputs[name]['ok'] and outputs[name]['schema_version'] == '2.0'
        chart = outputs['bazi_calc.py']
        review = json.loads(run([str(python), '-X', 'utf8',
                                 str(skill / 'scripts/reading_support.py'), '--stdin'], work,
                                data=json.dumps({'chart': chart}, ensure_ascii=False)))
        assert review['ok'] and review['semantic_review'] == 'required'
        assert outputs['bazi_calc.py']['solar_date'] == outputs['ziwei_calc.py']['solar_date']
        cast = json.loads(run([str(python), '-X', 'utf8', str(skill / 'scripts/yijing_cast.py'),
                               'coins', '--question', '安装验证'], work))
        assert cast['ok']
        gap = json.loads(run([str(python), '-X', 'utf8', str(skill / 'scripts/bazi_calc.py'),
                              '--year', '2026', '--month', '10', '--day', '4', '--hour', '2',
                              '--minute', '30', '--gender', 'male', '--timezone', 'Australia/Sydney'],
                             work, expected=1))
        assert not gap['ok'] and '不存在' in gap['message']
        installed = json.loads(run([str(python), '-m', 'pip', 'list', '--format=json'], work))
        print(json.dumps({'ok': True, 'platform': sys.platform, 'python': sys.version.split()[0],
                          'checks': ['bazi', 'ziwei', 'shared_time', 'reading_review', 'yijing', 'dst_gap'],
                          'dependencies': installed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
