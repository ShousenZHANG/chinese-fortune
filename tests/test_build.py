"""Tests for the skill packaging (scripts/build_skill.py).

Locks the distribution contract: the zip must nest under chinese-fortune/,
carry SKILL.md + runtime files, and leak NO dev/test cruft.
"""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build_skill.py"


@pytest.fixture(scope="module")
def package(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("dist") / "pkg.zip"
    proc = subprocess.run(
        [sys.executable, str(BUILD), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, f"build failed: {proc.stderr}\n{proc.stdout}"
    assert out.exists()
    return out


def test_skill_md_at_package_root(package):
    names = zipfile.ZipFile(package).namelist()
    assert "chinese-fortune/SKILL.md" in names


def test_runtime_files_present(package):
    names = set(zipfile.ZipFile(package).namelist())
    for must in [
        "chinese-fortune/scripts/bazi_calc.py",
        "chinese-fortune/scripts/bazi_reading.py",
        "chinese-fortune/scripts/request_time.py",
        "chinese-fortune/scripts/classical_search.py",
        "chinese-fortune/knowledge/manifest.json",
        "chinese-fortune/docs/CLASSICAL-SOURCES.md",
        "chinese-fortune/scripts/utils.py",
        "chinese-fortune/scripts/requirements.txt",
        "chinese-fortune/assets/64hex.json",
        "chinese-fortune/references/00-foundations.md",
        "chinese-fortune/agents/openai.yaml",
        "chinese-fortune/README.md",
        "chinese-fortune/README.en.md",
        "chinese-fortune/LICENSE",
    ]:
        assert must in names, f"missing from package: {must}"


def test_no_dev_cruft_leaked(package):
    names = zipfile.ZipFile(package).namelist()
    leaks = [n for n in names if any(x in n for x in (
        "/tests/", "test_", "/evals/", "__pycache__", ".pyc",
        ".bak", "/.git/", "_competitors", "build_skill", "import_classics",
    ))]
    assert leaks == [], f"dev cruft leaked into package: {leaks}"


def test_extracted_package_runs(package, tmp_path):
    """A freshly extracted package must be self-contained and runnable."""
    zipfile.ZipFile(package).extractall(tmp_path)
    skill = tmp_path / "chinese-fortune"
    proc = subprocess.run(
        [sys.executable, str(skill / "scripts" / "bazi_calc.py"),
         "--year", "1990", "--month", "5", "--day", "10", "--hour", "14",
         "--gender", "male", "--as-of-year", "2026"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0
    assert "乙亥" in proc.stdout  # day pillar of the canonical test chart


# --------------------------------------------------------------------------- #
# 版本来源 — 静默回退 "0.0.0" 会产出错名的发布包
# --------------------------------------------------------------------------- #

def test_read_version_matches_the_shipped_constant():
    sys.path.insert(0, str(ROOT / "scripts"))
    import bazi_calc
    import build_skill

    assert build_skill.read_version() == bazi_calc.VERSION


def test_read_version_fails_loudly_when_absent(monkeypatch):
    """A missing VERSION used to yield "0.0.0" silently, so a refactor that
    moved the constant would have shipped a misnamed zip with nothing red."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_skill

    monkeypatch.setattr(Path, "read_text", lambda self, *a, **kw: "# no version here")
    with pytest.raises(SystemExit):
        build_skill.read_version()


def test_default_output_name_carries_the_version(tmp_path):
    """test_build always passed --out, so the version-derived default filename
    was never exercised.

    This used to assert against ROOT/dist, which made it self-polluting AND
    permanently green: build_skill wrote there on every test run (dist/ is
    gitignored and never cleaned), so a stale zip of the right name satisfied
    the glob even when the default path was broken. Verified: point the default
    at a CWD-relative dir and pre-place a same-named zip -> the old test still
    passed. It now builds into tmp_path via --dist-dir and asserts the file the
    run actually produced.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_skill

    dist = tmp_path / "dist"
    proc = subprocess.run(
        [sys.executable, str(BUILD), "--dist-dir", str(dist)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    expected = dist / f"chinese-fortune-v{build_skill.read_version()}.zip"
    assert expected.exists(), (
        f"default name not version-derived; dir={list(dist.glob('*')) if dist.exists() else None}"
        f" stdout={proc.stdout[-400:]}")
    assert zipfile.ZipFile(expected).namelist(), "produced zip is empty"


def test_no_test_invokes_the_builder_without_an_explicit_output():
    """The suite must not write into dist/. It used to: this file's default-name
    test ran build_skill with no --out, so every `pytest` silently overwrote
    dist/chinese-fortune-v<current>.zip from whatever the working tree looked
    like at that moment — possibly dirty, possibly not the tagged commit. That
    also made the assertion permanently green, since dist/ is gitignored and
    never cleaned.

    Checked statically rather than by re-running pytest (which would recurse).

    The first version of this check only matched `subprocess.run([...])` with a
    literal list, so three real regression paths walked straight through it:
    an in-process `build_skill.main([])` (the most likely one — this file
    already imports build_skill four times, and it was verified to actually
    overwrite dist/chinese-fortune-v1.7.2.zip), a hoisted `cmd = [...]` passed
    by name, and `subprocess.check_output([...])`. It now works on the parsed
    AST instead of source text, so call shape no longer matters.
    """
    import ast
    offenders = []
    for f in sorted((ROOT / "tests").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        # 先收集本文件里被赋值成 list 的名字, 以便 cmd = [...] 这种写法也能查。
        lists: dict[str, ast.List] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        lists[tgt.id] = node.value

        def flags_of(node, lists=lists) -> tuple[bool, bool]:
            """(mentions the builder, passes an explicit output)"""
            text = ast.dump(node)
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            for nm in names & set(lists):
                text += ast.dump(lists[nm])
            builder = "BUILD" in text or "build_skill" in text
            explicit = "--out" in text or "--dist-dir" in text or "out_path" in text
            return builder, explicit

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            # subprocess.run/check_output/Popen(...) 或 build_skill.main(...)/build(...)
            is_sub = isinstance(fn, ast.Attribute) and fn.attr in (
                "run", "check_output", "check_call", "Popen")
            is_direct = isinstance(fn, ast.Attribute) and fn.attr in ("main", "build")
            if not (is_sub or is_direct):
                continue
            builder, explicit = flags_of(node)
            if builder and not explicit:
                offenders.append(f"{f.name}:{node.lineno}")
    assert not offenders, (
        "these invoke the builder with no explicit output path, so it writes to "
        f"the repo's dist/: {offenders}")


def test_package_is_lf_only_so_the_build_depends_on_the_commit_not_the_checkout(tmp_path):
    """The build reads the WORKING TREE. With core.autocrlf=true and no
    .gitattributes, a fresh clone of a tag checks out CRLF while the tree a
    release was cut from held LF — so the same commit produced two different
    artifacts.

    Measured on v1.7.2: the published asset and a rebuild from that exact tag
    differ in 59 of 63 files, and are byte-identical once line endings are
    normalised. build() now forces LF, and .gitattributes keeps the tree LF too.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_skill
    out_path = tmp_path / "lf_check.zip"          # 绝不写进仓库的 dist/
    build_skill.build(out_path, build_skill.collect())
    offenders = []
    with zipfile.ZipFile(out_path) as zf:
        for name in zf.namelist():
            if b"\r\n" in zf.read(name):
                offenders.append(name)
    assert not offenders, f"CRLF in packaged files: {offenders[:10]}"


def test_gitattributes_pins_line_endings():
    """Without this, the next clone silently reintroduces the CRLF drift above."""
    ga = ROOT / ".gitattributes"
    assert ga.exists(), "missing .gitattributes — checkout line endings unpinned"
    assert "eol=lf" in ga.read_text(encoding="utf-8")


def test_zip_creator_metadata_is_independent_of_host(tmp_path, monkeypatch):
    """Windows and Unix ZipInfo defaults must produce the same release bytes."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_skill

    source = tmp_path / "sample.md"
    source.write_bytes(b"deterministic package\r\n")
    monkeypatch.setattr(build_skill, "ROOT", tmp_path)
    normal_out_path = tmp_path / "normal.zip"
    windows_out_path = tmp_path / "windows.zip"
    build_skill.build(normal_out_path, [source])

    class WindowsZipInfo(zipfile.ZipInfo):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.create_system = 0

    # Preserve ZipInfo's class identity contract used by ZipFile.writestr.
    # The override simulates the Windows default even when CI runs on Linux.
    with monkeypatch.context() as windows:
        windows.setattr(zipfile, "ZipInfo", WindowsZipInfo)
        build_skill.build(windows_out_path, [source])

    assert normal_out_path.read_bytes() == windows_out_path.read_bytes(), (
        "host-specific ZIP headers changed otherwise identical release bytes"
    )
    for out_path in (normal_out_path, windows_out_path):
        with zipfile.ZipFile(out_path) as archive:
            assert archive.namelist() == ["chinese-fortune/sample.md"]
            assert archive.read("chinese-fortune/sample.md") == b"deterministic package\n"
            assert all(info.create_system == 3 for info in archive.infolist()), (
                "creator platform must be serialized consistently as Unix"
            )


def test_changelog_ships_with_the_package(package):
    """SKILL.md 的 frontmatter 只允许 name+description (evals/run_checks.py:47
    强制), 所以解压到 ~/.claude/skills/ 之后, 包内唯一的版本证据是
    scripts/utils.py 里那一行常量 —— 用户看不出装的是哪一版、修了什么。
    """
    names = set(zipfile.ZipFile(package).namelist())
    assert "chinese-fortune/CHANGELOG.md" in names, sorted(
        n for n in names if "/" not in n.split("/", 1)[1])
    body = zipfile.ZipFile(package).read("chinese-fortune/CHANGELOG.md").decode("utf-8")
    sys.path.insert(0, str(ROOT / "scripts"))
    from utils import __version__
    assert f"## [{__version__}]" in body, "包内 CHANGELOG 没有当前版本的条目"


def test_runtime_and_source_archives_have_explicit_different_scopes(package, tmp_path):
    from classical_search import validate_library
    with zipfile.ZipFile(package) as archive:
        archive.extractall(tmp_path / "runtime")
        names = set(archive.namelist())
        manifest = json.loads(archive.read("chinese-fortune/knowledge/manifest.json"))
    source_out_path = package.with_name(package.stem + "-sources.zip")
    assert manifest["schema_version"] == "2.0" and manifest["distribution_kind"] == "runtime"
    assert not any("/knowledge/sources/" in name for name in names)
    expected = json.loads((ROOT / "knowledge/manifest.json").read_text(encoding="utf-8"))
    chapters = {"chinese-fortune/knowledge/" + c["path"] for b in expected["books"] for c in b["chapters"]}
    assert len(chapters) == 416 and chapters <= names
    assert set(manifest["runtime_files"]) == {n.removeprefix("chinese-fortune/") for n in names} - {"knowledge/manifest.json"}
    assert manifest["source_archive"]["sha256"] == hashlib.sha256(source_out_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(source_out_path) as archive:
        archive.extractall(tmp_path / "source")
        for source in expected["supporting_sources"]:
            data = archive.read("chinese-fortune/knowledge/" + source["path"])
            assert hashlib.sha256(data).hexdigest() == source["sha256"]
    runtime = validate_library(tmp_path / "runtime/chinese-fortune/knowledge")
    source = validate_library(tmp_path / "source/chinese-fortune/knowledge")
    assert runtime["ok"] and not runtime["raw_sources_verified"]
    assert source["ok"] and source["raw_sources_verified"]
    assert runtime["validation_scope"] != source["validation_scope"]
    for line in (package.parent / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256((package.parent / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("damage", ["chapter", "script", "inventory", "supporting_source", "source_mode"])
def test_runtime_corruption_is_rejected(package, tmp_path, damage):
    from classical_search import validate_library
    zipfile.ZipFile(package).extractall(tmp_path)
    skill = tmp_path / "chinese-fortune"
    path = skill / "knowledge/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if damage == "chapter":
        (skill / "knowledge" / manifest["books"][0]["chapters"][0]["path"]).unlink()
    elif damage == "script":
        (skill / "scripts/utils.py").write_text("# altered", encoding="utf-8")
    elif damage == "inventory":
        name = "knowledge/" + manifest["books"][0]["chapters"][0]["path"]
        del manifest["runtime_files"][name]
    elif damage == "supporting_source":
        del manifest["source_archive"]["files"][manifest["supporting_sources"][0]["path"]]
    else:
        manifest["distribution_kind"] = "source"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    assert not validate_library(skill / "knowledge")["ok"]


def test_working_tree_provenance_ignores_unrelated_untracked_notes(tmp_path, monkeypatch):
    import build_skill
    for cmd in (["git", "init", "-q", str(tmp_path)],
                ["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.invalid"],
                ["git", "-C", str(tmp_path), "config", "user.name", "Fixture"]):
        subprocess.run(cmd, check=True, capture_output=True)
    (tmp_path / "SKILL.md").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "SKILL.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "fixture"], check=True, capture_output=True)
    monkeypatch.setattr(build_skill, "ROOT", tmp_path)
    (tmp_path / "user-notes.md").write_text("unrelated", encoding="utf-8")
    assert build_skill._provenance(None)["dirty"] is False
    (tmp_path / "SKILL.md").write_text("changed", encoding="utf-8")
    assert build_skill._provenance(None)["dirty"] is True


def test_fixed_commit_executes_its_builder_not_dirty_local_script(tmp_path, monkeypatch):
    import build_skill
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    fixture = "import argparse\np=argparse.ArgumentParser()\np.add_argument('--out')\np.add_argument('--snapshot-commit')\np.add_argument('--snapshot-archive')\np.add_argument('--snapshot-commit-object')\na=p.parse_args()\nfrom pathlib import Path\nPath(a.out).write_text(a.snapshot_commit)\n"
    (repo / "scripts/build_skill.py").write_text(fixture, encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "fixture@example.invalid"],
                ["git", "config", "user.name", "Fixture"], ["git", "add", "."],
                ["git", "commit", "-qm", "fixture"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    (repo / "scripts/build_skill.py").write_text("raise SystemExit('dirty builder ran')", encoding="utf-8")
    (repo / "untracked-user-plan.md").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(build_skill, "ROOT", repo)
    out_path = tmp_path / "fixed.txt"
    assert build_skill._build_snapshot(commit, out_path) == 0
    assert out_path.read_text(encoding="utf-8") == commit
    assert (repo / "untracked-user-plan.md").read_text(encoding="utf-8") == "keep"
    with pytest.raises(ValueError, match="full immutable"):
        build_skill._build_snapshot("HEAD", out_path)


def test_prebuilt_verification_never_rebuilds_or_executes_tools(package, monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "evals"))
    import package_smoke
    def forbidden(*args, **kwargs):
        raise AssertionError("archive-only verification launched a subprocess")
    monkeypatch.setattr(package_smoke.subprocess, "run", forbidden)
    assert package_smoke.main(["--archive", str(package), "--verify-only"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["artifact"]["sha256"] == hashlib.sha256(package.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="required commit"):
        package_smoke.verify_archive(package, expected_commit="0" * 40)


def test_prebuilt_verification_rejects_changed_archive_bytes(package, tmp_path):
    import shutil
    sys.path.insert(0, str(ROOT / "evals"))
    import package_smoke
    out_path = tmp_path / package.name
    shutil.copy2(package, out_path)
    shutil.copy2(package.parent / "SHA256SUMS", tmp_path / "SHA256SUMS")
    out_path.write_bytes(out_path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="runtime ZIP checksum"):
        package_smoke.verify_archive(out_path)


def test_snapshot_proof_binds_the_tree_not_only_a_commit_label(tmp_path, monkeypatch):
    import io
    import tarfile

    import build_skill
    repo = tmp_path / "repo"
    (repo / "nested").mkdir(parents=True)
    (repo / "nested/text.md").write_bytes(b"committed\n")
    for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "fixture@example.invalid"],
                ["git", "config", "user.name", "Fixture"], ["git", "add", "."],
                ["git", "commit", "-qm", "fixture"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    data = subprocess.check_output(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "archive", "--format=tar", commit], cwd=repo)
    archive_out_path, proof_out_path = tmp_path / "commit.tar", tmp_path / "commit.object"
    archive_out_path.write_bytes(data)
    proof_out_path.write_bytes(subprocess.check_output(["git", "cat-file", "commit", commit], cwd=repo))
    snapshot = tmp_path / "snapshot"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        archive.extractall(snapshot, filter="data")
    monkeypatch.setattr(build_skill, "ROOT", snapshot)
    build_skill._verify_snapshot(commit, archive_out_path, proof_out_path)
    (snapshot / "nested/text.md").write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="differs from commit archive"):
        build_skill._verify_snapshot(commit, archive_out_path, proof_out_path)
    with pytest.raises(ValueError, match="does not match its SHA"):
        build_skill._verify_snapshot("0" * 40, archive_out_path, proof_out_path)
