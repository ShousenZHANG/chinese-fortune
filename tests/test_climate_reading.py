"""Audited climate branches must reach readings without reviving legacy priorities."""
from bazi_calc import calculate_bazi
from bazi_reading import build_parser, prepare_reading
from bazi_strength import select_yong_shen
from tiaohou_provenance import get_tiaohou_audit


def test_source_conflicts_change_candidates_and_seasonal_gap_stays_empty():
    for stem, branch, expected in [('甲', '未', ['丁', '庚']),
                                    ('己', '申', ['癸', '丙']),
                                    ('辛', '子', ['丙', '壬']), ('乙', '丑', [])]:
        result = select_yong_shen(stem, branch, {'label': '中和'}, {})
        view = result['yong_shen']['views']['tiaohou']
        assert view['candidates'] == expected
        assert not view['source_audit']['legacy_candidates_allowed']
        assert result['yong_shen']['primary'] is None


def test_climate_question_includes_actual_audit_passages_and_context():
    args = build_parser().parse_args(['--year', '2000', '--month', '1', '--day', '15',
                                     '--hour', '10', '--gender', 'male', '--as-of-year', '2026'])
    chart = calculate_bazi(args)
    reading = prepare_reading(chart, '调候和格局用神有何区别')
    audit = get_tiaohou_audit('壬|丑')
    assert reading['climate_review'] == audit
    ids = {p['passage_id'] for p in reading['evidence_bundle']['passages']}
    assert {r['passage_id'] for r in audit['source_refs']} <= ids
    assert len(ids) == len(reading['evidence_bundle']['passages'])
    assert prepare_reading(chart, '原局结构')['climate_review'] is None
