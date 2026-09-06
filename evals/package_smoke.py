"""Build, install runtime dependencies in a fresh venv, and exercise the ZIP.

No globally installed packages or source-checkout imports are used by smoke commands.
"""
from __future__ import annotations

import argparse
import hashlib
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
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(command, cwd=cwd, env=env, input=data, capture_output=True,
                            text=True, encoding='utf-8', timeout=180)
    if result.returncode != expected:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}): '
                           f'{result.stdout[-2000:]}\n{result.stderr[-2000:]}')
    return result.stdout


def verify_archive(archive: Path, *, expected_commit: str | None = None) -> dict:
    """Check exact membership and external digests before extraction or execution."""
    sums = {}
    for line in (archive.parent / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if name in sums or Path(name).name != name or '/' in name or "\\" in name:
            raise ValueError('invalid or duplicate checksum filename')
        sums[name] = digest
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if sums.get(archive.name) != actual:
        raise ValueError('runtime ZIP checksum mismatch')
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)) or package.testzip() is not None:
            raise ValueError('duplicate or corrupt ZIP members')
        for info in package.infolist():
            parts = info.filename.split('/')
            if parts[0] != 'chinese-fortune' or any(p in ('', '.', '..') or ':' in p for p in parts):
                raise ValueError('unsafe archive member')
            if "\\" in info.filename or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('unsafe archive member')
        manifest = json.loads(package.read('chinese-fortune/knowledge/manifest.json'))
        required = {'chinese-fortune/' + name for name in manifest['runtime_files']}
        required.add('chinese-fortune/knowledge/manifest.json')
        if set(names) != required:
            raise ValueError('runtime ZIP membership differs from its inventory')
        if manifest.get('distribution_kind') != 'runtime' or manifest.get('schema_version') != '2.0':
            raise ValueError('expected runtime distribution schema 2.0')
        for name, digest in manifest['runtime_files'].items():
            if hashlib.sha256(package.read('chinese-fortune/' + name)).hexdigest() != digest:
                raise ValueError('runtime member checksum mismatch: ' + name)
        release = json.loads(package.read('chinese-fortune/RELEASE.json'))
        if expected_commit and release['build'] != {'mode': 'commit_snapshot', 'commit': expected_commit, 'dirty': False}:
            raise ValueError('runtime was not built from the required commit snapshot')
        source = manifest['source_archive']
        if Path(source['filename']).name != source['filename'] or '/' in source['filename'] or "\\" in source['filename']:
            raise ValueError('unsafe source archive filename')
        source_sha = hashlib.sha256((archive.parent / source['filename']).read_bytes()).hexdigest()
        if sums.get(source['filename']) != source_sha or source['sha256'] != source_sha:
            raise ValueError('source archive checksum mismatch')
        if source['build'] != release['build']:
            raise ValueError('source and runtime commit provenance differs')
    return {'sha256': actual, 'source_sha256': source_sha, 'version': release['version'], 'build': release['build']}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='test this existing runtime ZIP; never rebuild it')
    parser.add_argument('--expected-commit', help='require this full immutable commit in the package metadata')
    parser.add_argument('--verify-only', action='store_true', help='verify archive bytes and provenance without installing or executing tools')
    args = parser.parse_args(argv)
    if args.expected_commit and not args.archive:
        parser.error('--expected-commit requires --archive')
    # TemporaryDirectory owns only this newly created, resolved temp child.
    base = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix='fortune-package-', dir=base) as directory:
        work = Path(directory).resolve()
        if work.parent != base:
            raise RuntimeError('unexpected temporary workspace')
        archive = args.archive.resolve() if args.archive else work / 'skill.zip'
        if not args.archive:
            run([sys.executable, str(ROOT / 'scripts/build_skill.py'), '--out', str(archive)], work)
        artifact = verify_archive(archive, expected_commit=args.expected_commit)
        if args.verify_only:
            print(json.dumps({"ok": True, "validation": "archive_only", "artifact": artifact}, indent=2))
            return 0
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
        library = json.loads(run([str(python), '-X', 'utf8',
                                  str(skill / 'scripts/classical_search.py'), '--validate'], work))
        assert library['ok'] and library['distribution_kind'] == 'runtime'
        assert library['raw_sources_verified'] is False
        instant = json.loads(run([str(python), '-X', 'utf8',
                                  str(skill / 'scripts/request_time.py'),
                                  '--current-timezone', 'Australia/Sydney'], work))
        assert instant['ok'] and instant['timezone'] == 'Australia/Sydney'
        reading = json.loads(run([str(python), '-X', 'utf8',
                                  str(skill / 'scripts/bazi_reading.py'), *common,
                                  '--current-timezone', 'Australia/Sydney',
                                  '--request-time', instant['utc']], work))
        assert reading['ok'] and reading['evidence_bundle']['schema_version'] == '2.0'
        assert any(p['passage_id'] == 'ziping:c008:p0001' for p in reading['evidence_bundle']['passages'])
        assert 'day_master_strength' not in reading['chart_facts']
        review = json.loads(run([str(python), '-X', 'utf8',
                                 str(skill / 'scripts/reading_support.py'), '--stdin'], work,
                                data=json.dumps({'chart': chart}, ensure_ascii=False)))
        assert review['ok'] and review['semantic_review'] == 'required'
        assert outputs['bazi_calc.py']['solar_date'] == outputs['ziwei_calc.py']['solar_date']
        cast = json.loads(run([str(python), '-X', 'utf8', str(skill / 'scripts/yijing_cast.py'),
                               'time', '--current-timezone', 'Australia/Sydney',
                               '--request-time', instant['utc'], '--question', '安装验证'], work))
        assert cast['ok']
        gap = json.loads(run([str(python), '-X', 'utf8', str(skill / 'scripts/bazi_calc.py'),
                              '--year', '2026', '--month', '10', '--day', '4', '--hour', '2',
                              '--minute', '30', '--gender', 'male', '--timezone', 'Australia/Sydney'],
                             work, expected=1))
        assert not gap['ok'] and '不存在' in gap['message']
        installed = json.loads(run([str(python), '-m', 'pip', 'list', '--format=json'], work))
        print(json.dumps({'ok': True, 'platform': sys.platform, 'python': sys.version.split()[0],
                          'checks': ['bazi', 'ziwei', 'classical_library', 'current_time',
                                     'bazi_reading', 'shared_time', 'reading_review', 'yijing', 'dst_gap'],
                          'dependencies': installed, 'artifact': artifact}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
