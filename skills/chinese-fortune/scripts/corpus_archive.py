#!/usr/bin/env python3
"""Pack or unpack the frozen corpus (knowledge/books/ <-> knowledge/books.zip, knowledge/sources/ <->
corpus/sources.zip at the repository root) and the vendored packages (scripts/lunar_python, scripts/tzdata
and their dist-info <-> scripts/vendor.zip).

The raw sources are only for rebuilding and re-verifying, so their archive sits outside the skill folder.

The installed skill keeps the two folders as archives (one file each instead of about 1,100).
Maintainers unpack to edit or re-import, then pack again; the library reads either form, and the
bytes inside are unchanged, so every SHA-256 in knowledge/manifest.json still holds. Packing is
deterministic (sorted names, fixed timestamps), so the same folder always gives the same archive.
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

from utils import ensure_utf8_stdio, json_print

ROOT = Path(__file__).resolve().parents[1] / 'knowledge'
CORPUS = Path(__file__).resolve().parents[3] / 'corpus'
SCRIPTS = Path(__file__).resolve().parent
FOLDERS = ('books', 'sources')
VENDORED = ('lunar_python', 'lunar_python-1.4.8.dist-info', 'tzdata', 'tzdata-2026.3.dist-info')
STAMP = (2026, 1, 1, 0, 0, 0)


def _write(target: Path, files: list[tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files):
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def pack_vendor(scripts: Path = SCRIPTS) -> dict:
    """One zip on sys.path (utils.py adds it) replaces about 660 vendored files; bytes and RECORD unchanged."""
    files = [(path.relative_to(scripts).as_posix(), path.read_bytes())
             for top in VENDORED if (scripts / top).is_dir()
             for path in sorted((scripts / top).rglob('*')) if path.is_file() and '__pycache__' not in path.parts]
    if not files:
        return {}
    target = scripts / 'vendor.zip'
    _write(target, files)
    for top in VENDORED:
        if (scripts / top).is_dir():
            shutil.rmtree(scripts / top)
    return {'vendor': {'files': len(files), 'bytes': target.stat().st_size}}


def unpack_vendor(scripts: Path = SCRIPTS) -> dict:
    target = scripts / 'vendor.zip'
    if not target.is_file():
        return {}
    with zipfile.ZipFile(target) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        for name in names:
            path = (scripts / name).resolve()
            if not path.is_relative_to(scripts.resolve()):
                raise ValueError('unsafe archive member: ' + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    target.unlink()
    return {'vendor': {'files': len(names)}}


def _home(root: Path, folder: str, corpus: Path | None) -> Path:
    """Where a folder's archive lives: sources in corpus/ (the repository's, for the skill's own knowledge)."""
    if folder != 'sources':
        return root
    return corpus if corpus is not None else CORPUS if root.resolve() == ROOT.resolve() else root


def pack(root: Path = ROOT, corpus: Path | None = None) -> dict:
    done = {}
    for folder in FOLDERS:
        source = root / folder
        if not source.is_dir():
            continue
        files = sorted(p for p in source.rglob('*') if p.is_file())
        home = _home(root, folder, corpus)
        home.mkdir(parents=True, exist_ok=True)
        target = home / f'{folder}.zip'
        _write(target, [(path.relative_to(source).as_posix(), path.read_bytes()) for path in files])
        shutil.rmtree(source)
        done[folder] = {'files': len(files), 'bytes': target.stat().st_size}
    return done


def unpack(root: Path = ROOT, corpus: Path | None = None) -> dict:
    done = {}
    for folder in FOLDERS:
        archive_path = _home(root, folder, corpus) / f'{folder}.zip'
        if not archive_path.is_file():
            continue
        target = root / folder
        with zipfile.ZipFile(archive_path) as archive:
            names = [info.filename for info in archive.infolist() if not info.is_dir()]
            for name in names:
                path = (target / name).resolve()
                if not path.is_relative_to(target.resolve()):
                    raise ValueError('unsafe archive member: ' + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
        archive_path.unlink()
        done[folder] = {'files': len(names)}
    return done


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__,
                                     epilog='Top-level JSON keys: ok tool action folders (files and bytes per archive).')
    parser.add_argument('action', choices=('pack', 'unpack', 'pack-vendor', 'unpack-vendor'))
    parser.add_argument('--root', type=Path, default=ROOT, help='knowledge 目录（默认本技能的 knowledge/）')
    parser.add_argument('--corpus', type=Path, default=None,
                        help='sources.zip 所在目录（默认仓库根的 corpus/；--root 指向别处时默认同 --root）')
    args = parser.parse_args(argv)
    actions = {'pack': lambda: pack(args.root, args.corpus), 'unpack': lambda: unpack(args.root, args.corpus),
               'pack-vendor': pack_vendor, 'unpack-vendor': unpack_vendor}
    result = actions[args.action]()
    json_print({'ok': True, 'tool': 'corpus_archive', 'action': args.action, 'folders': result})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
