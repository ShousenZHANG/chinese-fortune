"""One command tells a new user whether the install works, and what to do if not."""
import doctor
from conftest import run_cli


def test_healthy_checkout_passes_every_check():
    data = run_cli('doctor.py')
    assert data['tool'] == 'doctor' and data['healthy'] is True
    names = [c['name'] for c in data['checks']]
    assert names == ['python', 'vendored:lunar_python', 'vendored:tzdata', 'timezone_history',
                     'classical_library', 'assets', 'reference_chart']
    assert all(c['ok'] for c in data['checks'])
    assert data['next_step'].startswith('安装正常')


def test_a_failed_check_names_its_fix_and_sets_exit_status(monkeypatch, capsys):
    monkeypatch.setattr(doctor, 'REFERENCE', {**doctor.REFERENCE, 'pillars': ('甲子',) * 4})
    assert doctor.main([]) == 1
    out = capsys.readouterr().out
    assert '"healthy": false' in out and 'reference_chart' in out


def test_tampered_vendored_file_is_reported(tmp_path, monkeypatch):
    package = tmp_path / 'tzdata'
    package.mkdir()
    (package / '__init__.py').write_text('x', encoding='utf-8')
    info = tmp_path / 'tzdata-0.dist-info'
    info.mkdir()
    (info / 'RECORD').write_text('tzdata/__init__.py,sha256=AAAA,1\n', encoding='utf-8')
    monkeypatch.setattr(doctor, 'SCRIPTS', tmp_path)
    check = doctor.check_record('tzdata')
    assert not check['ok'] and 'tzdata/__init__.py' in check['detail']


def test_a_crashing_check_is_reported_under_its_own_name(monkeypatch):
    def boom():
        raise RuntimeError('broken')
    monkeypatch.setattr(doctor, 'check_library', boom)
    row = next(c for c in doctor.run_checks() if c['name'] == 'classical_library')
    assert not row['ok'] and 'RuntimeError' in row['detail'] and row['fix']


def test_required_assets_match_the_shipped_directory():
    from pathlib import Path
    shipped = {p.name for p in (Path(doctor.ROOT) / 'assets').glob('*.json')}
    assert set(doctor.REQUIRED_ASSETS) == shipped


def test_a_missing_rule_asset_makes_the_install_unhealthy(tmp_path, monkeypatch):
    import shutil
    assets = tmp_path / 'assets'
    shutil.copytree(doctor.ROOT / 'assets', assets)
    (assets / 'geju_rules.json').unlink()
    monkeypatch.setattr(doctor, 'ROOT', tmp_path)
    check = doctor.check_assets()
    assert not check['ok'] and 'geju_rules.json' in check['detail'] and check['fix']
