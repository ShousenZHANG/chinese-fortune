#!/usr/bin/env python3
"""Build verified runtime/source archives; release inputs come from a fixed commit.

Development builds use the working tree and identify dirty input. For publishing,
use --commit <full SHA>, test the emitted archive, then reuse those exact bytes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_FOLDER = "chinese-fortune"
INCLUDE_FILES = ["SKILL.md", "README.md", "README.en.md", "LICENSE",
                 "CHANGELOG.md", "docs/OUTPUT-VALIDATION.md", "docs/OUTPUT-EXAMPLE.md",
                 "docs/OPTIONAL-TOOLS.md", "docs/CLASSICAL-SOURCES.md",
                 "docs/QIMEN-LIUREN-METHODS.md", "docs/BAZI-RULES.md", "docs/CONTENT-COVERAGE.md",
                 "docs/RELEASE-PROCESS.md", "docs/FACSIMILE-COLLATION.md",
                 "docs/FACSIMILE-CANDIDATES.md", "docs/BAZI-TIME-METHOD.md"]
INCLUDE_DIRS = ["references", "assets", "agents"]
SCRIPT_EXCLUDE = {"build_skill.py", "import_classics.py"}
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


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_bytes(path: Path) -> bytes:
    # The frozen corpus is already hash-bound: do not rewrite its raw sources.
    data = path.read_bytes()
    return data if path.is_relative_to(ROOT / "knowledge") else data.replace(b"\r\n", b"\n")


def _source_manifest() -> dict:
    from classical_search import validate_library
    library = ROOT / "knowledge"
    report = validate_library(library_root=library)
    if not report["ok"] or report.get("distribution_kind") != "source":
        raise ValueError("full source validation failed: " + str(report))
    return json.loads((library / "manifest.json").read_text(encoding="utf-8"))


def collect() -> list[Path]:
    """Validate full sources, then select all five books' runtime chapters."""
    manifest = _source_manifest()
    picked = []
    for name in INCLUDE_FILES:
        path = ROOT / name
        if not path.is_file():
            raise ValueError("required file missing: " + name)
        picked.append(path)
    for name in INCLUDE_DIRS:
        base = ROOT / name
        if not base.is_dir():
            raise ValueError("required dir missing: " + name)
        picked.extend(p for p in base.rglob("*") if p.is_file())
    picked.extend(ROOT / "knowledge" / c["path"]
                  for b in manifest["books"] for c in b["chapters"])
    picked.extend(p for p in (ROOT / "scripts").rglob("*")
                  if p.is_file() and p.name not in SCRIPT_EXCLUDE)
    if any(not p.resolve().is_relative_to(ROOT.resolve()) for p in picked):
        raise ValueError("runtime path escapes the project root")
    return sorted({p for p in picked if not EXCLUDE_RE.search("/" + p.relative_to(ROOT).as_posix())},
                  key=lambda p: p.relative_to(ROOT).as_posix())


def compile_check(files: list[Path]) -> None:
    for path in files:
        if path.suffix == ".py":
            compile(path.read_bytes(), str(path), "exec")


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            if name.startswith("/") or "\\" in name or any(p in ("", ".", "..") for p in name.split("/")):
                raise ValueError("unsafe archive path: " + name)
            info = zipfile.ZipInfo(f"{SKILL_FOLDER}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def build(out_path: Path, files: list[Path]) -> None:
    """Low-level deterministic ZIP writer; distribution creation uses build_distribution."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(_zip_bytes({p.relative_to(ROOT).as_posix(): _file_bytes(p) for p in files}))


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", timeout=30)
    if result.returncode:
        raise ValueError("git failed: " + result.stderr.strip())
    return result.stdout.strip()


def _provenance(commit: str | None) -> dict:
    if commit:
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("snapshot commit must be a full SHA")
        return {"mode": "commit_snapshot", "commit": commit, "dirty": False}
    try:
        sha = _git("rev-parse", "HEAD")
        # Unrelated untracked notes do not prevent or dirty the runtime inputs.
        changed = _git("status", "--porcelain", "--untracked-files=all", "--",
                       "scripts", "knowledge", *INCLUDE_FILES, *INCLUDE_DIRS)
        return {"mode": "development", "commit": sha, "dirty": bool(changed)}
    except ValueError:
        return {"mode": "development", "commit": None, "dirty": True}


def build_distribution(out_path: Path, *, commit: str | None = None) -> dict:
    """Emit two distinct distributions, each bound by the external checksum file."""
    from classical_search import validate_library
    validate_skill_md()
    files = collect()  # full source check must happen before any output write
    compile_check(files)
    manifest = _source_manifest()
    version, provenance = read_version(), _provenance(commit)
    entries = {p.relative_to(ROOT).as_posix(): _file_bytes(p) for p in files}
    release = {"schema_version": "1.0", "version": version, "build": provenance,
               "license": "LICENSE; chapter transcription licenses in knowledge/manifest.json",
               "validation_scope": "frozen text inventory and bytes, not image collation or prediction validity"}
    entries["RELEASE.json"] = _json_bytes(release)
    source_entries = {"knowledge/manifest.json": (ROOT / "knowledge/manifest.json").read_bytes(),
                      "LICENSE": entries["LICENSE"], "RELEASE.json": entries["RELEASE.json"]}
    archived = {}
    for book in manifest["books"]:
        archived[book["index_path"]] = book["index_sha256"]
        if book.get("source_metadata_path"):
            archived[book["source_metadata_path"]] = book["source_metadata_sha256"]
        for row in book["chapters"]:
            chapter = json.loads((ROOT / "knowledge" / row["path"]).read_text(encoding="utf-8"))
            archived[chapter["raw_path"]] = chapter["raw_sha256"]
            source_entries["knowledge/" + row["path"]] = (ROOT / "knowledge" / row["path"]).read_bytes()
    for source in manifest.get("supporting_sources", []):
        archived[source["path"]] = source["sha256"]
    for name in archived:
        source_entries["knowledge/" + name] = (ROOT / "knowledge" / name).read_bytes()
    with tempfile.TemporaryDirectory(prefix="fortune-source-validation-") as directory:
        source_root = Path(directory)
        for name, data in source_entries.items():
            path = source_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        source_report = validate_library(source_root / "knowledge")
        if not source_report["ok"] or source_report["distribution_kind"] != "source":
            raise ValueError("staged source validation failed: " + str(source_report))
    source_bytes = _zip_bytes(source_entries)
    source_out_path = out_path.with_name(out_path.stem + "-sources.zip")
    runtime = copy.deepcopy(manifest)
    runtime.update({"schema_version": "2.0", "distribution_kind": "runtime",
                    "source_paths_scope": "source_archive/knowledge",
                    "source_archive": {"filename": source_out_path.name, "sha256": _digest(source_bytes),
                                       "build": provenance, "files": archived},
                    "runtime_files": {name: _digest(data) for name, data in sorted(entries.items())},
                    "manifest_integrity": "external SHA256SUMS covers the complete runtime ZIP"})
    entries["knowledge/manifest.json"] = _json_bytes(runtime)
    # Validate exactly the bytes about to ship, without installing sources beside them.
    with tempfile.TemporaryDirectory(prefix="fortune-runtime-validation-") as directory:
        folder = Path(directory)
        for name, data in entries.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        runtime_report = validate_library(folder / "knowledge")
        if not runtime_report["ok"] or runtime_report["distribution_kind"] != "runtime":
            raise ValueError("runtime validation failed: " + str(runtime_report))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    source_out_path.write_bytes(source_bytes)
    out_path.write_bytes(_zip_bytes(entries))
    sums_out_path = out_path.parent / "SHA256SUMS"
    sums_out_path.write_text(f"{_digest(out_path.read_bytes())}  {out_path.name}\n"
                             f"{_digest(source_bytes)}  {source_out_path.name}\n", encoding="utf-8")
    return {"ok": True, "version": version, "build": provenance,
            "runtime": {"path": str(out_path), "files": len(entries), "sha256": _digest(out_path.read_bytes()),
                        "validation": runtime_report},
            "source_archive": {"path": str(source_out_path), "files": len(source_entries),
                               "sha256": _digest(source_bytes), "validation": source_report}}


def _git_object_digest(kind: str, data: bytes) -> str:
    return hashlib.sha1(kind.encode() + b" " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _verify_snapshot(commit: str, archive_path: Path, commit_object_path: Path) -> None:
    """Prove the extracted files' Git tree is bound to this commit object SHA.

    A caller cannot mark a dirty working tree as a commit build by supplying a
    label: the commit's content hash and complete source tree must match.
    """
    commit_object = commit_object_path.read_bytes()
    if _git_object_digest("commit", commit_object) != commit:
        raise ValueError("snapshot commit object does not match its SHA")
    expected_tree = commit_object.splitlines()[0].decode("ascii").removeprefix("tree ")
    tree: dict = {}
    expected_files = set()
    with tarfile.open(archive_path, "r:") as archive:
        for info in archive.getmembers():
            if info.isdir():
                continue
            if not info.isfile():
                raise ValueError("unsupported snapshot file type")
            parts = info.name.split("/")
            if any(part in ("", ".", "..") or ":" in part for part in parts) or "\\" in info.name:
                raise ValueError("unsafe snapshot member")
            expected_files.add(info.name)
            data = (ROOT / info.name).read_bytes()
            stream = archive.extractfile(info)
            if stream is None or data != stream.read():
                raise ValueError("snapshot file differs from commit archive: " + info.name)
            mode = 0o100755 if info.mode & 0o111 else 0o100644
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = (format(mode, "o"), _git_object_digest("blob", data))
    actual_files = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()}
    if actual_files != expected_files:
        raise ValueError("snapshot file inventory differs from commit archive")

    def digest_tree(node: dict) -> str:
        chunks = []
        for name, value in sorted(node.items(), key=lambda pair: (pair[0] + ("/" if isinstance(pair[1], dict) else "")).encode("utf-8")):
            mode, digest = ("40000", digest_tree(value)) if isinstance(value, dict) else value
            chunks.append(mode.encode() + b" " + name.encode("utf-8") + b"\0" + bytes.fromhex(digest))
        return _git_object_digest("tree", b"".join(chunks))

    if digest_tree(tree) != expected_tree:
        raise ValueError("snapshot source tree is not the requested commit's tree")


def _build_snapshot(commit: str, out_path: Path) -> int:
    resolved = _git("rev-parse", "--verify", commit + "^{commit}")
    if resolved != commit:
        raise ValueError("--commit requires the full immutable commit SHA")
    result = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "archive", "--format=tar", resolved], cwd=ROOT,
                            capture_output=True, timeout=60, check=True)
    with tempfile.TemporaryDirectory(prefix="fortune-commit-") as directory:
        snapshot = Path(directory).resolve() / "source"
        snapshot.mkdir()
        archive_path = snapshot.parent / "commit.tar"
        archive_path.write_bytes(result.stdout)
        commit_object_path = snapshot.parent / "commit.object"
        commit_object_path.write_bytes(subprocess.run(["git", "cat-file", "commit", resolved], cwd=ROOT,
                                                     capture_output=True, timeout=30, check=True).stdout)
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
            for info in archive.getmembers():
                target = (snapshot / info.name).resolve()
                if not target.is_relative_to(snapshot) or not (info.isdir() or info.isfile()):
                    raise ValueError("unsafe commit archive entry")
                if info.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stream = archive.extractfile(info)
                    if stream is None:
                        raise ValueError("missing commit file")
                    target.write_bytes(stream.read())
        # Run the builder and validator from the selected commit, not dirty local code.
        command = [sys.executable, str(snapshot / "scripts/build_skill.py"),
                   "--out", str(out_path), "--snapshot-commit", resolved,
                   "--snapshot-archive", str(archive_path), "--snapshot-commit-object", str(commit_object_path)]
        return subprocess.run(command, cwd=snapshot, timeout=180).returncode


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="runtime ZIP output path (source ZIP and SHA256SUMS beside it)")
    parser.add_argument("--dist-dir", help="output directory; default <repo>/dist")
    parser.add_argument("--commit", help="full commit SHA: build only its tracked snapshot, using its builder")
    parser.add_argument("--snapshot-commit", help=argparse.SUPPRESS)
    parser.add_argument("--snapshot-archive", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--snapshot-commit-object", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.commit and args.snapshot_commit:
            raise ValueError("choose one commit build mode")
        if args.snapshot_commit or args.snapshot_archive or args.snapshot_commit_object:
            if not all((args.snapshot_commit, args.snapshot_archive, args.snapshot_commit_object)):
                raise ValueError("snapshot mode requires a complete commit proof")
            _verify_snapshot(args.snapshot_commit, args.snapshot_archive, args.snapshot_commit_object)
        if args.commit:
            text = _git("show", args.commit + ":scripts/utils.py")
            match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
            if not match:
                raise ValueError("selected commit has no version")
            version = match.group(1)
        else:
            version = read_version()
        out_path = (Path(args.out) if args.out else
                    Path(args.dist_dir or ROOT / "dist") / f"chinese-fortune-v{version}.zip").resolve()
        if args.commit:
            return _build_snapshot(args.commit, out_path)
        print(json.dumps(build_distribution(out_path, commit=args.snapshot_commit), ensure_ascii=False, indent=2))
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as exc:
        print("FATAL: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
