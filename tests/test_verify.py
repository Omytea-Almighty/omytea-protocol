"""Tests for omytea_protocol.verify — the specimen verifies; tampered receipts fail."""

import copy
import json
from pathlib import Path

import pytest

from omytea_protocol.verify import (
    compute_frozen_hash,
    main,
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
