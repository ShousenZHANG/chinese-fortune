"""The repository ships three skills; each installs and runs on its own folder alone."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'skills'
NAMES = ('chinese-fortune', 'life-guide', 'fortune-extras')
MAINTENANCE = {'build_skill.py', 'import_classics.py', 'build_han_variants.py', 'rule_registry.py',
               'import_life_guide.py', 'life_guide_refs.py', 'life_guide_review.py'}


def _frontmatter(name: str) -> dict:
    text = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
    head = text.split('---', 2)[1]
    return dict(line.split(': ', 1) for line in head.strip().splitlines())


@pytest.mark.parametrize('name', NAMES)
def test_each_skill_names_itself_and_says_when_to_use_it(name):
    meta = _frontmatter(name)
    assert meta['name'] == name and re.fullmatch(r'[a-z][a-z0-9-]*', name)
    assert 0 < len(meta['description']) <= 1024 and 'Python 3.9' in meta['compatibility']
    assert (SKILLS / name / 'LICENSE').is_file()


@pytest.mark.parametrize('name', ['life-guide', 'fortune-extras'])
def test_every_script_imports_from_its_own_skill_only(name):
    """With only that skill's scripts/ on the path, every runtime module imports."""
    scripts = SKILLS / name / 'scripts'
    modules = sorted(p.stem for p in scripts.glob('*.py') if p.name not in MAINTENANCE)
    code = (f'import sys; sys.path.insert(0, {str(scripts)!r}); '
            + '; '.join(f'import {module}' for module in modules))
    done = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize('module,skills', [('cf_io.py', ('life-guide', 'fortune-extras')),
                                           ('safety_stop.py', ('chinese-fortune', 'life-guide')),
                                           ('entropy.py', ('chinese-fortune', 'fortune-extras'))])
def test_shared_helpers_are_identical_copies(module, skills):
    first, *rest = (SKILLS / skill / 'scripts' / module for skill in skills)
    for other in rest:
        assert other.read_bytes() == first.read_bytes(), other


def test_the_small_envelope_matches_chinese_fortunes():
    import cf_io
    import utils
    assert cf_io.__version__ == utils.__version__ and cf_io.ENVELOPE_VERSION == utils.ENVELOPE_VERSION
    for error in ('invalid_input', 'invalid_timezone', 'symbol_not_found'):
        mine, theirs = cf_io.error_envelope('t', error, 'm'), utils.error_envelope('t', error, 'm')
        assert mine == theirs, error


def test_chinese_fortune_no_longer_ships_or_attaches_the_moved_parts():
    fortune = SKILLS / 'chinese-fortune'
    for path in ('scripts/life_guide.py', 'scripts/tarot_draw.py', 'scripts/jiemeng_lookup.py',
                 'assets/life_guide.json', 'assets/tarot78.json', 'assets/jiemeng.json'):
        assert not (fortune / path).exists(), path
    from fortune_reading import read_request
    from test_answer_length import MOVING
    assert 'life_reference' not in read_request(MOVING)


def test_an_emergency_inside_a_fortune_question_still_stops_first():
    """The fortune router keeps its own copy of the detector, so it works without life-guide installed."""
    from question_router import route
    routed = route('我现在胸痛，帮我起一卦')
    assert routed['flow'] == 'life_guide' and routed['stop'] == 'emergency' and routed['skill'] == 'life-guide'


@pytest.mark.parametrize('question,skill', [('帮我抽一张塔罗', 'fortune-extras'), ('我梦见蛇是什么意思', 'fortune-extras'),
                                            ('双子座和天蝎座配吗', 'fortune-extras'),
                                            ('押金不退怎么办', 'life-guide')])
def test_questions_for_the_other_skills_name_them(question, skill):
    from question_router import route
    assert route(question).get('skill') == skill


def test_life_guide_region_reads_its_own_zone_tables():
    """No tzdata package needed: zone names, countries and links come from assets/tz."""
    from region import country_of, is_zone, region_of
    assert is_zone('Asia/Calcutta') and country_of('Asia/Calcutta') == 'IN'
    assert region_of('Asia/Shanghai') == '中国大陆' and region_of('Australia/Sydney') == '境外'
    assert not is_zone('Asia/Shanghai ')
    rows = (SKILLS / 'life-guide/assets/tz/zone.tab').read_text(encoding='utf-8')
    assert 'Asia/Shanghai' in rows


def test_the_marketplace_lists_every_skill():
    market = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
    assert sorted(p['source'] for p in market['plugins']) == sorted(f'./skills/{name}' for name in NAMES)


def test_life_guide_keeps_the_books_code_notice_and_licenses():
    life = SKILLS / 'life-guide'
    data = json.loads((life / 'assets/life_guide.json').read_text(encoding='utf-8'))
    notice = (life / 'licenses/HowToLiveBetter-MIT.txt').read_text(encoding='utf-8').strip()
    assert notice == data['source']['license_detail']['code_notice']
    notices = (life / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
    for fragment in ('《高性价比人生指南》，eternity4719', '842e11c9d51fac7943e5abb4e332e29b460b5061', 'CC BY 4.0',
                     'Copyright (c) 2026 eternity4719', 'Three entries', 'tzdata==2026.3'):
        assert fragment in notices, fragment
    for target in re.findall(r'\]\(([^)#]+)\)', notices):
        if not target.startswith('http'):
            assert (life / target).is_file(), target


def test_the_installed_layout_is_packed_and_reads_the_same_bytes():
    """The skill folder ships the corpus and the vendored packages as archives, never beside loose copies."""
    fortune = SKILLS / 'chinese-fortune'
    for packed, loose in (('knowledge/books.zip', 'knowledge/books'), ('knowledge/sources.zip', 'knowledge/sources'),
                          ('scripts/vendor.zip', 'scripts/lunar_python'), ('scripts/vendor.zip', 'scripts/tzdata')):
        assert (fortune / packed).is_file() and not (fortune / loose).exists(), loose
    from classical_search import library_bytes, validate_library
    report = validate_library()
    assert report['ok'] and report['distribution_kind'] == 'source'
    manifest = json.loads((fortune / 'knowledge/manifest.json').read_text(encoding='utf-8'))
    first = manifest['books'][0]['chapters'][0]
    import hashlib
    assert hashlib.sha256(library_bytes(fortune / 'knowledge', first['path'])).hexdigest() == first['sha256']
    files = sum(1 for p in fortune.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    assert files < 300, files       # was 1,972 before packing


def test_corpus_archives_round_trip_byte_for_byte(tmp_path):
    import shutil

    import corpus_archive
    root = tmp_path / 'knowledge'
    shutil.copytree(SKILLS / 'chinese-fortune/knowledge', root)
    names = ('books.zip', 'sources.zip')
    before = {n: _members(root / n) for n in names}
    corpus_archive.unpack(root)
    assert (root / 'books/ziping').is_dir() and not (root / 'books.zip').exists()
    corpus_archive.pack(root)
    # Same entries, order, timestamps and bytes; the deflate stream itself differs between zlib builds
    # (CI's Linux zlib vs Windows), so the committed archives are compared by content, not raw bytes.
    assert {n: _members(root / n) for n in names} == before
    first = {n: (root / n).read_bytes() for n in names}
    corpus_archive.unpack(root)
    corpus_archive.pack(root)
    assert {n: (root / n).read_bytes() for n in names} == first     # repeatable on one machine


def _members(path):
    import zipfile
    with zipfile.ZipFile(path) as archive:
        return [(i.filename, i.date_time, i.compress_type, i.external_attr, archive.read(i))
                for i in archive.infolist()]


def test_import_refuses_to_write_beside_packed_archives():
    done = subprocess.run([sys.executable, '-X', 'utf8', str(SKILLS / 'chinese-fortune/scripts/import_classics.py'),
                           '--wikisource'], capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 2 and 'corpus_archive.py unpack' in done.stderr
