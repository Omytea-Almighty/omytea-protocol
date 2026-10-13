"""Tests for omytea_protocol.verify — the specimen verifies; tampered receipts fail."""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from omytea_protocol.verify import (
    compute_frozen_hash,
    main,
    recompute_scores,
    validate_structure,
    verify_receipt,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECIMEN_PATH = REPO_ROOT / "examples" / "specimen-receipt.json"


@pytest.fixture()
def specimen():
    with open(SPECIMEN_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# The shipped specimen must verify
# ---------------------------------------------------------------------------


def test_specimen_is_clearly_labeled(specimen):
    assert specimen["specimen"] is True
    assert "Specimen receipt" in specimen["notes"]
    assert "Not a live track-record entry" in specimen["notes"]


def test_specimen_passes_structure_validation(specimen):
    assert validate_structure(specimen) == []


def test_specimen_passes_full_verification(specimen):
    report = verify_receipt(specimen)
    assert report.passed
    names = [name for name, _, _ in report.checks]
    assert "structure" in names
    assert "frozen_hash" in names
    assert "scores.brier" in names
    assert "scores.log_loss" in names
    assert "baseline_scores.uniform" in names


def test_cli_passes_on_specimen(capsys):
    exit_code = main([str(SPECIMEN_PATH)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "RESULT: PASS" in out


# ---------------------------------------------------------------------------
# Tampering must fail
# ---------------------------------------------------------------------------


def test_tampered_probability_breaks_hash(specimen):
    tampered = copy.deepcopy(specimen)
    branches = tampered["prediction"]["branches"]
    branches[0]["probability"] = 0.85
    branches[1]["probability"] = 0.05
    branches[2]["probability"] = 0.05
    branches[3]["probability"] = 0.05
    report = verify_receipt(tampered)
    assert not report.passed
    failed = {name for name, ok, _ in report.checks if not ok}
    assert "frozen_hash" in failed


def test_tampered_question_breaks_hash(specimen):
    tampered = copy.deepcopy(specimen)
    tampered["question"] = "A different question entirely"
    report = verify_receipt(tampered)
    assert not report.passed


def test_stripping_specimen_flag_breaks_hash(specimen):
    tampered = copy.deepcopy(specimen)
    del tampered["specimen"]
    report = verify_receipt(tampered)
    assert not report.passed
    failed = {name for name, ok, _ in report.checks if not ok}
    assert "frozen_hash" in failed


def test_tampered_scores_fail_recomputation(specimen):
    tampered = copy.deepcopy(specimen)
    tampered["scores"]["brier"] = 0.01  # flattering but false
    report = verify_receipt(tampered)
    assert not report.passed
    failed = {name for name, ok, _ in report.checks if not ok}
    assert "scores.brier" in failed
    # The hash still passes: scores are not frozen, they are recomputable.
    hash_checks = [ok for name, ok, _ in report.checks if name == "frozen_hash"]
    assert hash_checks == [True]


def test_tampered_outcome_fails_scores(specimen):
    tampered = copy.deepcopy(specimen)
    tampered["outcome"]["label"] = "south_exit"
    report = verify_receipt(tampered)
    assert not report.passed


def test_tampered_baseline_fails(specimen):
    tampered = copy.deepcopy(specimen)
    tampered["baseline_scores"]["uniform"]["brier"] = 0.0
    report = verify_receipt(tampered)
    assert not report.passed
    failed = {name for name, ok, _ in report.checks if not ok}
    assert "baseline_scores.uniform" in failed


def test_forged_hash_fails(specimen):
    tampered = copy.deepcopy(specimen)
    tampered["frozen_hash"] = "0" * 64
    report = verify_receipt(tampered)
    assert not report.passed


def test_cli_fails_on_tampered_receipt(tmp_path, specimen, capsys):
    tampered = copy.deepcopy(specimen)
    tampered["prediction"]["branches"][0]["probability"] = 0.56
    tampered["prediction"]["branches"][1]["probability"] = 0.19
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    exit_code = main([str(path)])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "RESULT: FAIL" in out


def test_cli_rejects_unreadable_input(tmp_path, capsys):
    missing = tmp_path / "missing.json"
    assert main([str(missing)]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main([str(bad)]) == 2
    capsys.readouterr()


# ---------------------------------------------------------------------------
# Structural validation details
# ---------------------------------------------------------------------------


def test_structure_rejects_missing_fields():
    problems = validate_structure({})
    assert any("missing required field" in p for p in problems)


def test_structure_rejects_unnormalized_branches(specimen):
    bad = copy.deepcopy(specimen)
    bad["prediction"]["branches"][0]["probability"] = 0.10
    problems = validate_structure(bad)
    assert any("sum to 1" in p for p in problems)


def test_structure_rejects_outcome_label_outside_branches(specimen):
    bad = copy.deepcopy(specimen)
    bad["outcome"]["label"] = "west_exit"
    problems = validate_structure(bad)
    assert any("not one of the declared branch labels" in p for p in problems)


def test_structure_rejects_scores_without_outcome(specimen):
    bad = copy.deepcopy(specimen)
    del bad["outcome"]
    problems = validate_structure(bad)
    assert any("scores must not be present without an outcome" in p for p in problems)


def test_pending_receipt_verifies_without_scores(specimen):
    pending = copy.deepcopy(specimen)
    del pending["outcome"]
    del pending["scores"]
    del pending["baseline_scores"]
    # Hash is unaffected: outcome/scores are not part of the frozen payload.
    assert compute_frozen_hash(pending) == pending["frozen_hash"]
    report = verify_receipt(pending)
    assert report.passed


def test_quantile_receipt_roundtrip():
    receipt = {
        "version": "0.1",
        "receipt_id": "unit-quantile-0001",
        "created_at": "2026-06-30T00:00:00Z",
        "question": "How many seconds until the tracked object reaches the gate?",
        "prediction": {
            "quantiles": {
                "levels": [0.1, 0.25, 0.5, 0.75, 0.9],
                "values": [8.0, 10.0, 12.0, 15.0, 20.0],
            }
        },
        "resolution_deadline": "2026-06-30T00:05:00Z",
        "resolution_source": {"description": "Gate sensor timestamp log."},
        "outcome": {"resolved_at": "2026-06-30T00:04:00Z", "value": 13.0},
    }
    receipt["frozen_hash"] = compute_frozen_hash(receipt)
    from omytea_protocol.verify import recompute_scores

    receipt["scores"] = recompute_scores(receipt)
    report = verify_receipt(receipt)
    assert report.passed, report.render()

    tampered = copy.deepcopy(receipt)
    tampered["prediction"]["quantiles"]["values"][2] = 13.0
    assert not verify_receipt(tampered).passed


# ---------------------------------------------------------------------------
# Timeline ordering
# ---------------------------------------------------------------------------

#: Fixed verification clock so the future-timestamp warnings are deterministic.
VERIFIED_AT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _branch_receipt(created_at, deadline, resolved_at=None, **labels):
    """A freshly frozen, correctly scored branch receipt."""
    receipt = {
        "version": "0.1",
        "receipt_id": "unit-timeline-0001",
        "created_at": created_at,
        "question": "Does the supplier confirm the delivery date by email before the deadline?",
        "prediction": {
            "branches": [
                {"label": "yes", "probability": 0.7},
                {"label": "no", "probability": 0.3},
            ]
        },
        "resolution_deadline": deadline,
        "resolution_source": {"description": "Supplier reply received in the agent mailbox."},
        **labels,
    }
    receipt["frozen_hash"] = compute_frozen_hash(receipt)
    if resolved_at is not None:
        receipt["outcome"] = {"resolved_at": resolved_at, "label": "yes"}
        receipt["scores"] = recompute_scores(receipt)
    return receipt


def _failed(report):
    return {name for name, ok, _ in report.checks if not ok}


def _warned(report):
    return [name for name, _ in report.warnings]


def test_well_ordered_receipt_has_no_timeline_findings():
    receipt = _branch_receipt(
        "2026-10-01T00:00:00Z", "2026-10-07T00:00:00Z", "2026-10-06T09:00:00Z"
    )
    report = verify_receipt(receipt, now=VERIFIED_AT)
    assert report.passed, report.render()
    assert report.warnings == []
    names = [name for name, _, _ in report.checks]
    assert "timeline.frozen_before_deadline" in names
    assert "timeline.resolved_after_freeze" in names


def test_outcome_resolved_before_freeze_fails(specimen):
    # The outcome is dated one year before the prediction was frozen.
    tampered = copy.deepcopy(specimen)
    tampered["outcome"]["resolved_at"] = "2025-06-30T18:00:00Z"
    assert tampered["outcome"]["resolved_at"] != specimen["outcome"]["resolved_at"]
    report = verify_receipt(tampered, now=VERIFIED_AT)
    assert not report.passed
    assert _failed(report) == {"timeline.resolved_after_freeze"}
    # resolved_at is not frozen, so the hash alone cannot catch this.
    assert [ok for name, ok, _ in report.checks if name == "frozen_hash"] == [True]


def test_outcome_resolved_at_the_freeze_instant_fails():
    receipt = _branch_receipt(
        "2026-10-08T18:31:52+00:00", "2026-10-14T18:00:00Z", "2026-10-08T18:31:52Z"
    )
    report = verify_receipt(receipt, now=VERIFIED_AT)
    assert not report.passed
    assert _failed(report) == {"timeline.resolved_after_freeze"}


@pytest.mark.parametrize("created_at", ["2026-06-30T18:01:00Z", "2026-06-30T18:01:30Z"])
def test_frozen_at_or_after_deadline_fails(specimen, created_at):
    tampered = copy.deepcopy(specimen)
    tampered["created_at"] = created_at  # deadline is 18:01:00Z, resolution 18:02:11Z
    tampered["frozen_hash"] = compute_frozen_hash(tampered)
    report = verify_receipt(tampered, now=VERIFIED_AT)
    assert not report.passed
    assert _failed(report) == {"timeline.frozen_before_deadline"}


def test_resolution_after_deadline_is_a_warning_not_a_failure():
    receipt = _branch_receipt(
        "2026-10-08T18:31:52+00:00", "2026-10-14T18:00:00Z", "2027-01-01T00:00:00Z"
    )
    report = verify_receipt(receipt, now=datetime(2027, 2, 1, tzinfo=timezone.utc))
    assert report.passed, report.render()
    assert _warned(report) == ["timeline.late_resolution"]
    rendered = report.render()
    assert "[WARN] timeline.late_resolution" in rendered
    assert "78 days, 6:00:00 after resolution_deadline" in rendered
    assert "RESULT: PASS (6/6 checks passed, 1 warning)" in rendered


def test_specimen_still_passes_with_its_resolution_lag_reported(specimen):
    report = verify_receipt(specimen, now=VERIFIED_AT)
    assert report.passed
    assert _warned(report) == ["timeline.late_resolution"]
    assert "0:01:11 after resolution_deadline" in dict(report.warnings)["timeline.late_resolution"]


def test_future_resolved_at_is_a_warning():
    # An outcome dated after the moment of verification.
    receipt = _branch_receipt(
        "2026-10-08T18:31:52+00:00", "2026-10-14T18:00:00Z", "2026-10-10T09:12:00Z"
    )
    report = verify_receipt(receipt, now=VERIFIED_AT)
    assert report.passed, report.render()
    assert _warned(report) == ["timeline.future_resolved_at"]


def test_future_created_at_on_pending_receipt_is_a_warning():
    receipt = _branch_receipt("2026-11-01T00:00:00Z", "2026-11-08T00:00:00Z")
    report = verify_receipt(receipt, now=VERIFIED_AT)
    assert report.passed, report.render()
    assert _warned(report) == ["timeline.future_created_at"]


def test_clock_skew_within_tolerance_is_not_flagged():
    resolved = (VERIFIED_AT + timedelta(minutes=1)).isoformat()
    receipt = _branch_receipt("2026-10-08T00:00:00Z", "2026-10-14T00:00:00Z", resolved)
    assert verify_receipt(receipt, now=VERIFIED_AT).warnings == []


def test_timestamps_without_offset_are_read_as_utc():
    # Mixing naive and offset timestamps must not crash the comparison.
    receipt = _branch_receipt(
        "2026-10-01T00:00:00", "2026-10-07T00:00:00Z", "2026-10-06T09:00:00+00:00"
    )
    report = verify_receipt(receipt, now=VERIFIED_AT.replace(tzinfo=None))
    assert report.passed, report.render()
    assert report.warnings == []


def test_cli_prints_warnings_and_provenance_without_failing(capsys):
    exit_code = main([str(SPECIMEN_PATH)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[WARN] timeline.late_resolution" in out
    assert "RESULT: PASS (7/7 checks passed, 1 warning)" in out
    assert "PROVENANCE: unknown" in out


# ---------------------------------------------------------------------------
# Provenance label
# ---------------------------------------------------------------------------


def test_absent_provenance_is_unknown_not_an_error(specimen):
    assert "provenance" not in specimen
    assert validate_structure(specimen) == []
    # The optional field leaves every existing hash unchanged.
    assert compute_frozen_hash(specimen) == (
        "7ee02cec942e823f2b122d9d27d7a5ec9994fd546f962654771e85e2ade50f34"
    )
    report = verify_receipt(specimen, now=VERIFIED_AT)
    assert report.passed
    assert report.provenance == "unknown"
    assert "PROVENANCE: unknown" in report.render()


@pytest.mark.parametrize("label", ["synthetic", "fixture", "real"])
def test_declared_provenance_is_reported_beside_the_result(label):
    receipt = _branch_receipt(
        "2026-10-01T00:00:00Z",
        "2026-10-07T00:00:00Z",
        "2026-10-06T09:00:00Z",
        provenance=label,
    )
    report = verify_receipt(receipt, now=VERIFIED_AT)
    assert report.passed, report.render()
    assert report.provenance == label
    lines = report.render().splitlines()
    result_at = next(i for i, line in enumerate(lines) if line.startswith("RESULT:"))
    provenance_line = lines[result_at + 1]
    assert provenance_line.startswith(f"PROVENANCE: {label} (")
    if label == "real":
        assert "not that it is true" in provenance_line
    else:
        assert "NOT evidence" in provenance_line


@pytest.mark.parametrize("bad", ["observed", "Real", "", None, ["real"]])
def test_unknown_provenance_value_fails_structure(bad):
    receipt = _branch_receipt("2026-10-01T00:00:00Z", "2026-10-07T00:00:00Z", provenance=bad)
    assert any("provenance must be one of" in p for p in validate_structure(receipt))
    report = verify_receipt(receipt, now=VERIFIED_AT)
    assert not report.passed
    assert report.provenance == "unknown"


def test_relabelling_provenance_breaks_hash():
    receipt = _branch_receipt(
        "2026-10-01T00:00:00Z",
        "2026-10-07T00:00:00Z",
        "2026-10-06T09:00:00Z",
        provenance="synthetic",
    )
    relabelled = copy.deepcopy(receipt)
    relabelled["provenance"] = "real"
    assert relabelled["provenance"] != receipt["provenance"]
    report = verify_receipt(relabelled, now=VERIFIED_AT)
    assert not report.passed
    assert _failed(report) == {"frozen_hash"}


def test_stripping_provenance_breaks_hash():
    receipt = _branch_receipt(
        "2026-10-01T00:00:00Z",
        "2026-10-07T00:00:00Z",
        "2026-10-06T09:00:00Z",
        provenance="fixture",
    )
    stripped = copy.deepcopy(receipt)
    del stripped["provenance"]
    report = verify_receipt(stripped, now=VERIFIED_AT)
    assert not report.passed
    assert _failed(report) == {"frozen_hash"}
    assert report.provenance == "unknown"


def test_labelling_an_existing_receipt_after_freezing_breaks_hash(specimen):
    labelled = copy.deepcopy(specimen)
    labelled["provenance"] = "fixture"
    report = verify_receipt(labelled, now=VERIFIED_AT)
    assert not report.passed
    assert _failed(report) == {"frozen_hash"}


def test_specimen_cannot_declare_real_provenance():
    receipt = _branch_receipt(
        "2026-10-01T00:00:00Z", "2026-10-07T00:00:00Z", specimen=True, provenance="real"
    )
    assert "a specimen receipt cannot declare provenance 'real'" in validate_structure(receipt)
