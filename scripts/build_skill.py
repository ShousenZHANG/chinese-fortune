#!/usr/bin/env python3
"""Build a distributable skill package (.zip) for Claude / OpenAI import.

Produces ``dist/chinese-fortune-v<VERSION>.zip`` containing ONLY the files an
end user needs — SKILL.md, references/, scripts/ (runtime + requirements),
assets/, agents/, README (中文 + English), LICENSE — with dev/test cruft excluded
(tests/, evals/, __pycache__, .git, *.bak, _competitors, dist/build).

The archive nests everything under a top-level ``chinese-fortune/`` folder so it
extracts cleanly into a named skill directory, ready for:
  - Claude Code:  unzip into ~/.claude/skills/
  - Claude.ai:    upload the zip as a Skill
  - OpenAI:       agents/openai.yaml + scripts/ as a custom tool/agent

Self-validating: aborts if SKILL.md frontmatter is malformed, the description
exceeds 1024 chars, any bundled script fails to compile, or a required path is
missing. Deterministic output (sorted, fixed mtime) for reproducible builds.

Usage:
    python scripts/build_skill.py            # -> dist/chinese-fortune-v<version>.zip
    python scripts/build_skill.py --out X    # custom output path
"""
from __future__ import annotations

import argparse
import py_compile
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_FOLDER = "chinese-fortune"  # top-level dir inside the archive

# Whitelist of paths (relative to repo root) to ship to end users.
# CHANGELOG 也要进包: SKILL.md 的 frontmatter 只允许 name+description
# (evals/run_checks.py:47 强制), 所以解压到 ~/.claude/skills/ 之后, 包内
# 唯一的版本证据是 scripts/utils.py 里那一行常量 —— 用户看不出装的是哪版、
# 修了什么。
INCLUDE_FILES = ["SKILL.md", "README.md", "README.en.md", "LICENSE",
                 "CHANGELOG.md", "docs/OUTPUT-VALIDATION.md", "docs/OUTPUT-EXAMPLE.md"]
INCLUDE_DIRS = ["references", "assets", "agents"]
# scripts/: ship runtime .py + requirements.txt, but NOT this builder or tests.
SCRIPT_EXCLUDE = {"build_skill.py"}

# Patterns never to ship.
EXCLUDE_RE = re.compile(
    r"(__pycache__|\.pyc$|\.pyo$|\.bak|\.bak-|/\.git/|\.pytest_cache|"
    r"\.DS_Store|Thumbs\.db|\.original\.md$)"
)


def read_version() -> str:
    """Read the shipped VERSION constant.

    Fails hard rather than falling back to "0.0.0": a silent fallback would
    ship a misnamed release zip, and nothing downstream would go red.
    """
    source = ROOT / "scripts" / "utils.py"
    text = source.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit(
            f"FATAL: no VERSION constant in {source.relative_to(ROOT)}; "
            f"refusing to build a misnamed package"
        )
    return m.group(1)


def validate_skill_md() -> None:
    md = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not md.startswith("---\n"):
        sys.exit("FATAL: SKILL.md missing YAML frontmatter")
    _, fm, _ = md.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    if meta.get("name") != "chinese-fortune":
        sys.exit(f"FATAL: SKILL.md name must be chinese-fortune, got {meta.get('name')!r}")
    desc = meta.get("description", "")
    if not desc:
        sys.exit("FATAL: SKILL.md description empty")
    if len(desc) > 1024:
        sys.exit(f"FATAL: SKILL.md description {len(desc)} > 1024 chars")


def collect() -> list[Path]:
    """Return the sorted, filtered list of files to package."""
    picked: list[Path] = []

    for f in INCLUDE_FILES:
        p = ROOT / f
        if not p.exists():
            sys.exit(f"FATAL: required file missing: {f}")
        picked.append(p)

    for d in INCLUDE_DIRS:
        base = ROOT / d
        if not base.exists():
            sys.exit(f"FATAL: required dir missing: {d}")
        picked += [p for p in base.rglob("*") if p.is_file()]

    # scripts/ — runtime python + requirements, minus builder/tests.
    for p in (ROOT / "scripts").rglob("*"):
        if p.is_file() and p.name not in SCRIPT_EXCLUDE:
            picked.append(p)

    # Filter cruft + dedupe + sort for deterministic archives.
    out, seen = [], set()
    for p in picked:
        rel = p.relative_to(ROOT).as_posix()
        if EXCLUDE_RE.search("/" + rel) or rel in seen:
            continue
        seen.add(rel)
        out.append(p)
    return sorted(out, key=lambda p: p.relative_to(ROOT).as_posix())


def compile_check(files: list[Path]) -> None:
    for p in files:
        if p.suffix == ".py":
            try:
                py_compile.compile(str(p), doraise=True)
            except py_compile.PyCompileError as e:
                sys.exit(f"FATAL: bundled script fails to compile: {p.name}\n{e}")


def build(out_path: Path, files: list[Path]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Fixed timestamp -> reproducible zip.
    zi_date = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            arc = f"{SKILL_FOLDER}/{p.relative_to(ROOT).as_posix()}"
            # Normalise to LF. Every bundled file is text (.py/.md/.json/.yaml),
            # and the build reads the WORKING TREE, so without this the artifact
            # depends on the checkout rather than on the commit: with
            # core.autocrlf=true and no .gitattributes, a fresh clone of a tag
            # yields CRLF while the tree the release was cut from held LF.
            # Verified on v1.7.2 — the published asset and a rebuild from the
            # same tag differ in 59 of 63 files, and are byte-identical once
            # line endings are normalised. LF also matches what shipped.
            data = p.read_bytes().replace(b"\r\n", b"\n")
            info = zipfile.ZipInfo(arc, date_time=zi_date)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the chinese-fortune skill package")
    ap.add_argument("--out", default=None, help="output zip path")
    ap.add_argument("--dist-dir", default=None,
                    help="directory for the version-derived default name "
                         "(default: <repo>/dist). Lets tests exercise the default "
                         "filename without writing into the repo's release dir.")
    args = ap.parse_args(argv)

    version = read_version()
    validate_skill_md()
    files = collect()
    compile_check(files)

    if args.out:
        out_path = Path(args.out)
    else:
        dist_dir = Path(args.dist_dir) if args.dist_dir else ROOT / "dist"
        if dist_dir.exists() and not dist_dir.is_dir():
            # 否则 mkdir 抛 FileExistsError, 是一条裸 traceback 路径 —— 本文件
            # 其余失败路径一律走 sys.exit("FATAL: ...")。
            sys.exit(f"FATAL: --dist-dir is not a directory: {dist_dir}")
        dist_dir.mkdir(parents=True, exist_ok=True)
        out_path = dist_dir / f"chinese-fortune-v{version}.zip"
    build(out_path, files)

    size_kb = out_path.stat().st_size / 1024
    rel = out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path
    print(f"OK  built {rel}")
    print(f"    version {version} | {len(files)} files | {size_kb:.0f} KB")
    print(f"    root folder in archive: {SKILL_FOLDER}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
