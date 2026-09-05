"""Tests for the skill packaging (scripts/build_skill.py).

Locks the distribution contract: the zip must nest under chinese-fortune/,
carry SKILL.md + runtime files, and leak NO dev/test cruft.
"""
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
        ".bak", "/.git/", "_competitors", "build_skill",
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
