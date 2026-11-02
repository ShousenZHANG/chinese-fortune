# Contribution rules

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing behavior. The checks below run in the full pytest job.

| Invariant | Owner and regression checks |
| --- | --- |
| Classical quotations match the frozen corpus, cited book and passage together. | `scripts/answer_check.py`; `tests/test_quote_authority.py`. |
| Facts retain producer identity, rejected siblings, uncertainty and person labels. | `scripts/answer_evidence.py`; `tests/test_evidence_admission.py`, `tests/test_v60_evidence_boundaries.py`. |
| Birth corrections use supplied identities and replay the accepted time convention. | `scripts/birth_candidates.py`, `scripts/birth_correction.py`; `tests/test_v60_birth_boundaries.py`. |
| Qimen candidates and exclusions cover the requested actual time interval. | `scripts/qimen_select.py`; `tests/test_qimen_intervals.py`. |
| Imported text retains source characters and source metadata survives installation. | `scripts/import_classics.py`; `tests/test_yilin_spans.py`, `tests/test_capture_metadata.py`. |

Run the checks for the changed boundary and then the required full checks in CONTRIBUTING. Final release gates use the exact committed artifact and remote CI, as described in [docs/RELEASE-PROCESS.md](docs/RELEASE-PROCESS.md).
