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
import posixpath
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

# The installable skill lives in skills/chinese-fortune/ (what `npx skills add` and plugin hosts copy);
# READMEs, docs and the changelog stay at the repository root and are added to the release ZIP beside it.
SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
SKILL_FOLDER = "chinese-fortune"
SKILL_FILES = ["SKILL.md"]
INCLUDE_FILES = ["README.md", "README.en.md", "CHANGELOG.md"]
INCLUDE_DIRS = ["references", "assets", "agents", "docs"]
# Maintenance tools: they run from a checkout, never from the installed
# package. Tests derive their own exemptions from this set rather than
# keeping parallel lists -- three copies had already drifted apart.
# requirements-dev.txt pins build_han_variants' opencc; its own first line says
# it stays out of the runtime package, yet it had been shipping.
SCRIPT_EXCLUDE = {"build_skill.py", "import_classics.py", "build_han_variants.py",
                  "import_life_guide.py", "life_guide_refs.py", "life_guide_review.py", "rule_registry.py",
                  "requirements-dev.txt"}
EXCLUDE_RE = re.compile(
    r"(__pycache__|\.pyc$|\.pyo$|\.bak|\.bak-|/\.git/|\.pytest_cache|"
    r"\.DS_Store|Thumbs\.db|\.original\.md$)"
)
LEGAL_DIGESTS = {
    "LICENSE": "3eee53bd84945816dd771de205a605833bcd009dd0cf8666580caec9d88274e5",
    "licenses/Renhuai-MIT.txt": "c0214b387494be5b7a6d3e7bf62897e43dd425c2b77f42e20925029252275be4",
    "licenses/iztro-MIT.txt": "e6c7b6e313cbda3135b41bccc66c98be132cb8319d0d465903d17e669e748b36",
    "licenses/HowToLiveBetter-MIT.txt": "b5637b996d72e74dac01e8799701ff6440b5a979cd15a29ac120e7ae57963c67",
    "licenses/CC-BY-4.0.txt": "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411",
    "licenses/CC-BY-SA-4.0.txt": "28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5",
    "licenses/OpenCC-Python-NOTICE.txt": "afcbc6ee2d4fa9c2e9d5944b53ca05d3cc06bab6d082817c689bdfa33c38fcb0",
    "licenses/OpenCC-Python-Apache-2.0.txt": "18f3fedf9eac72e6054260489c764c1e54f63cf2b16055523f561ffeec7bc908",
    "licenses/lunar-python-MIT.txt": "a9d04f47f0615c0ce48bdbe2ff58d5c174279d9f20f044ef29249632302a4ab3",
    "licenses/tzdata-NOTICE.txt": "df58f69ea88683035d720b5375bcef0cf5aeaa98a1d098d572e0992c378deb46",
    "licenses/tzdata-Apache-2.0.txt": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
}
LEGAL_FILES = (*LEGAL_DIGESTS, "DISCLAIMER.md", "THIRD_PARTY_NOTICES.md", "licenses/README.md")
NOTICE_COVERAGE = (
    "lunar-python 1.4.8", "Copyright (c) 2020 6tail", "tzdata 2026.3",
    "Copyright (c) 2020, Paul Ganssle (Google)", "Copyright (c) 2026, Stan Ulbrych",
    "《高性价比人生指南》，eternity4719", "842e11c9d51fac7943e5abb4e332e29b460b5061",
    "CC BY 4.0", "Copyright (c) 2026 eternity4719", "Three entries",
    "Wikisource contributors", "CC BY-SA 4.0 where applicable", "ShareAlike",
    "modern editorial work", "1923", "Module:SKchar revision 9013306",
    "opencc-python-reimplemented==0.1.7", "1803", "dictionary-derived subset",
    "iztro 2.6.3", "f24f2d9f21c37a3d48aa06c76d73372e4cc9bc94",
    "Copyright (c) 2023 All Contributors", "seven-level star-brightness table",
    "495b79ecb3524b20b2edc026067d7d0b0f407319", "Copyright (c) 2026 紫微研究",
    "alternative 庚干四化 and 魁钺 tables", "大耗", "岁破",
)


def validate_legal_bundle(entries: dict[str, bytes]) -> None:
    """Validate the reviewed legal bundle independently of a package's inventory."""
    for name in LEGAL_FILES:
        if not entries.get(name, b"").strip():
            raise ValueError("required legal file missing or blank: " + name)
    for name, digest in LEGAL_DIGESTS.items():
        if _digest(entries[name]) != digest:
            raise ValueError("legal fulltext differs from reviewed upstream bytes: " + name)
    notices = entries["THIRD_PARTY_NOTICES.md"].decode("utf-8")
    for fragment in NOTICE_COVERAGE:
        if fragment not in notices:
            raise ValueError("third-party notice coverage missing: " + fragment)
    manifest = json.loads(entries["knowledge/manifest.json"])
    trusted_manifest = json.loads((SKILL / "knowledge/manifest.json").read_bytes())
    for key in ("books", "supporting_sources"):
        if manifest[key] != trusted_manifest[key]:
            raise ValueError("legal provenance index differs from trusted checkout: " + key)
    for book in manifest["books"]:
        row = next((line for line in notices.splitlines()
                    if line.startswith(f"| `{book['id']}` |")), "")
        if any(str(book[key]) not in row for key in ("title", "source_url", "revision")):
            raise ValueError("third-party book attribution missing: " + book["id"])
        attribution = book["license"].get("attribution")
        if attribution and attribution not in notices:
            raise ValueError("third-party source attribution missing: " + book["id"])
    for source in manifest["supporting_sources"]:
        if source["source_url"] not in notices or source["license"] not in notices:
            raise ValueError("supporting-source attribution missing: " + source["path"])
    for name in LEGAL_FILES:
        if name.endswith(".md"):
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", entries[name].decode("utf-8")):
                if target.startswith(("https://", "http://", "#")):
                    continue
                path = posixpath.normpath(posixpath.join(posixpath.dirname(name), target.split("#")[0]))
                if path not in entries:
                    raise ValueError(f"unresolved legal reference in {name}: {target}")


def _legal_files() -> list[Path]:
    files = [SKILL / name for name in LEGAL_FILES]
    entries = {_arcname(path): _file_bytes(path) for path in files if path.is_file()}
    entries["knowledge/manifest.json"] = (SKILL / "knowledge/manifest.json").read_bytes()
    validate_legal_bundle(entries)
    if (ROOT / "LICENSE").read_bytes().replace(b"\r\n", b"\n") != entries["LICENSE"]:
        raise ValueError("root and installed skill MIT licenses differ")
    return files


def read_version() -> str:
    """Read the shipped VERSION constant.

    Fails hard rather than falling back to "0.0.0": a silent fallback would
    ship a misnamed release zip, and nothing downstream would go red.
    """
    source = SKILL / "scripts" / "utils.py"
    text = source.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit(
            f"FATAL: no VERSION constant in {source.relative_to(ROOT)}; "
            f"refusing to build a misnamed package"
        )
    return m.group(1)


def validate_skill_md() -> None:
    md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
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
    # agentskills.io: optional, 1-500 characters when present.
    if len(meta.get("compatibility", "")) > 500:
        sys.exit("FATAL: SKILL.md compatibility > 500 chars")


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_bytes(path: Path) -> bytes:
    # The frozen corpus is already hash-bound: do not rewrite its raw sources.
    # Binary files (the vendored zoneinfo data) keep their bytes: 0D 0A there is data.
    data = path.read_bytes()
    if (path.is_relative_to(SKILL / "knowledge") or
            path.is_relative_to(SKILL / "licenses") or b"\0" in data):
        return data
    data = data.replace(b"\r\n", b"\n")
    if path.suffix == ".md" and not path.is_relative_to(SKILL):
        # The root READMEs link into skills/chinese-fortune/; in the package those files sit beside them.
        data = data.replace(b"](skills/chinese-fortune/", b"](")
    return data


def _source_manifest() -> dict:
    from classical_search import validate_library
    library = SKILL / "knowledge"
    report = validate_library(library_root=library)
    if not report["ok"] or report.get("distribution_kind") != "source":
        raise ValueError("full source validation failed: " + str(report))
    return json.loads((library / "manifest.json").read_text(encoding="utf-8"))


def collect() -> list[Path]:
    """Validate full sources, then select every declared book's runtime chapters."""
    picked = _legal_files()
    manifest = _source_manifest()
    for base_dir, names in ((SKILL, SKILL_FILES), (ROOT, INCLUDE_FILES)):
        for name in names:
            path = base_dir / name
            if not path.is_file():
                raise ValueError("required file missing: " + name)
            picked.append(path)
    for name in INCLUDE_DIRS:
        base = SKILL / name
        if not base.is_dir():
            raise ValueError("required dir missing: " + name)
        picked.extend(p for p in base.rglob("*") if p.is_file())
    picked.extend(SKILL / "knowledge" / c["path"]
                  for b in manifest["books"] for c in b["chapters"])
    picked.extend(p for p in (SKILL / "scripts").rglob("*")
                  if p.is_file() and p.name not in SCRIPT_EXCLUDE)
    if any(not p.resolve().is_relative_to(ROOT.resolve()) for p in picked):
        raise ValueError("runtime path escapes the project root")
    kept = {p for p in picked if not EXCLUDE_RE.search("/" + _arcname(p))}
    by_name = {_arcname(p): p for p in kept}
    if len(by_name) != len(kept):
        raise ValueError("two files map to the same archive path")
    return [by_name[name] for name in sorted(by_name)]


def _arcname(path: Path) -> str:
    """Path inside chinese-fortune/: skill files by their place in the skill, root docs by theirs."""
    base = SKILL if path.is_relative_to(SKILL) else ROOT
    return path.relative_to(base).as_posix()


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
    out_path.write_bytes(_zip_bytes({_arcname(p): _file_bytes(p) for p in files}))


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
                       SKILL.relative_to(ROOT).as_posix(), *INCLUDE_FILES)
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
    entries = {_arcname(p): _file_bytes(p) for p in files}
    release = {"schema_version": "1.0", "version": version, "build": provenance,
               "license": "LICENSE; THIRD_PARTY_NOTICES.md; DISCLAIMER.md; licenses/",
               "validation_scope": "frozen text inventory and bytes, not image collation or prediction validity"}
    entries["RELEASE.json"] = _json_bytes(release)
    source_entries = {name: entries[name] for name in LEGAL_FILES}
    source_entries.update({"knowledge/manifest.json": (SKILL / "knowledge/manifest.json").read_bytes(),
                           "RELEASE.json": entries["RELEASE.json"]})
    archived = {}
    for book in manifest["books"]:
        archived[book["index_path"]] = book["index_sha256"]
        if book.get("source_metadata_path"):
            archived[book["source_metadata_path"]] = book["source_metadata_sha256"]
        for row in book["chapters"]:
            chapter = json.loads((SKILL / "knowledge" / row["path"]).read_text(encoding="utf-8"))
            archived[chapter["raw_path"]] = chapter["raw_sha256"]
            source_entries["knowledge/" + row["path"]] = (SKILL / "knowledge" / row["path"]).read_bytes()
    for source in manifest.get("supporting_sources", []):
        archived[source["path"]] = source["sha256"]
    for name in archived:
        source_entries["knowledge/" + name] = (SKILL / "knowledge" / name).read_bytes()
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
        command = [sys.executable, str(snapshot / SKILL.relative_to(ROOT) / "scripts/build_skill.py"),
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
            text = _git("show", f"{args.commit}:{SKILL.relative_to(ROOT).as_posix()}/scripts/utils.py")
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
