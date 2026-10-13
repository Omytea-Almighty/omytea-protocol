"""Receipt verifier: validate structure, recompute the frozen hash, recompute scores.

Usage:

    python -m omytea_protocol.verify receipt.json

Exit code 0 when every check passes, 1 when any check fails, 2 when the
input cannot be read or parsed. Warnings are printed but never change the
exit code.

The verifier is deliberately dependency-free: the point of a receipt is
that anyone can check it with nothing but the standard library. The
formal interface is ``schema/receipt.schema.json`` (JSON Schema draft
2020-12); this module implements the equivalent structural checks
natively so no third-party validator is required.

Timeline checks (not expressible in JSON Schema, so they live here):

- FAIL ``timeline.frozen_before_deadline`` unless ``created_at`` is strictly
  before ``resolution_deadline``. A prediction frozen at or after its own
  horizon predicted nothing.
- FAIL ``timeline.resolved_after_freeze`` unless ``outcome.resolved_at`` is
  strictly after ``created_at``. An outcome recorded before, or at the same
  instant as, the freeze contradicts the one property a receipt exists to
  show: the prediction came first.
- WARN ``timeline.late_resolution`` when ``outcome.resolved_at`` is after
  ``resolution_deadline``. This is a warning, not a failure, because
  ``resolved_at`` is when the resolution was recorded and the deadline is
  when the outcome must be resolvable; honest resolvers lag (the shipped
  specimen resolves 71 seconds after its deadline). The verifier cannot
  tell latency from an outcome read outside the declared window, so it
  reports the lag and leaves the judgement to the reader.
- WARN ``timeline.future_created_at`` / ``timeline.future_resolved_at`` when
  a timestamp is later than the verifier's clock by more than
  ``CLOCK_SKEW_TOLERANCE``. A warning, not a failure, because the verdict
  would otherwise depend on when verification runs: the same receipt would
  fail today and pass next week.

Timestamps without a UTC offset are read as UTC, as the schema documents.

The optional ``provenance`` label (``synthetic`` | ``fixture`` | ``real``)
is printed beside the result. It is the issuer's declaration: when present
it is bound into ``frozen_hash``, so a passing hash shows the label was not
changed after freezing, never that it is true. An absent label is reported
as ``unknown`` and is not an error.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from omytea_protocol.scoring import brier_score, crps_from_quantiles, log_loss

__all__ = [
    "FROZEN_FIELDS",
    "OPTIONAL_FROZEN_FIELDS",
    "PROVENANCE_VALUES",
    "SCORE_TOLERANCE",
    "CLOCK_SKEW_TOLERANCE",
    "canonical_frozen_payload",
    "compute_frozen_hash",
    "validate_structure",
    "recompute_scores",
    "verify_receipt",
    "VerificationReport",
    "main",
]

#: Fields that make up the canonical frozen payload, in the order they
#: are documented. ``OPTIONAL_FROZEN_FIELDS`` are additionally included
#: when present.
FROZEN_FIELDS: tuple[str, ...] = (
    "receipt_id",
    "created_at",
    "question",
    "prediction",
    "resolution_deadline",
    "resolution_source",
)

#: Labels that join the frozen payload only when present, so receipts that
#: omit them hash exactly as before. Stripping or relabelling one after
#: freezing breaks ``frozen_hash``.
OPTIONAL_FROZEN_FIELDS: tuple[str, ...] = ("specimen", "provenance")

#: Allowed values of the optional ``provenance`` label. Absent means unknown.
PROVENANCE_VALUES: tuple[str, ...] = ("synthetic", "fixture", "real")

#: Absolute tolerance when comparing recorded scores against recomputed ones.
SCORE_TOLERANCE = 1e-9

#: How far past the verifier's clock a timestamp may sit before it is flagged.
CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)

_PROBABILITY_SUM_TOLERANCE = 1e-6


# ---------------------------------------------------------------------------
# Canonical hashing
# ---------------------------------------------------------------------------


def canonical_frozen_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    """Extract the frozen payload: the fields committed at freeze time."""
    payload = {name: receipt[name] for name in FROZEN_FIELDS if name in receipt}
    for name in OPTIONAL_FROZEN_FIELDS:
        if name in receipt:
            payload[name] = receipt[name]
    return payload


def compute_frozen_hash(receipt: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical serialization of the frozen payload.

    Canonical serialization is exactly::

        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    encoded as UTF-8. Any change to any frozen field changes the digest.
    """
    blob = json.dumps(
        canonical_frozen_payload(receipt),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Structural validation (mirrors schema/receipt.schema.json)
# ---------------------------------------------------------------------------


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _parse_utc(value: str) -> datetime:
    """Parse an ISO 8601 timestamp, reading one without an offset as UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _validate_branches(branches: Any, problems: list[str]) -> None:
    if not isinstance(branches, list) or len(branches) < 2:
        problems.append("prediction.branches must be an array of at least 2 entries")
        return
    labels: list[str] = []
    total = 0.0
    for i, entry in enumerate(branches):
        if not isinstance(entry, dict):
            problems.append(f"prediction.branches[{i}] must be an object")
            return
        label = entry.get("label")
        prob = entry.get("probability")
        if not isinstance(label, str) or not label:
            problems.append(f"prediction.branches[{i}].label must be a non-empty string")
        else:
            labels.append(label)
        if not isinstance(prob, (int, float)) or isinstance(prob, bool) or not 0.0 <= float(prob) <= 1.0:
            problems.append(f"prediction.branches[{i}].probability must be a number in [0, 1]")
        else:
            total += float(prob)
        extra = set(entry) - {"label", "probability"}
        if extra:
            problems.append(f"prediction.branches[{i}] has unexpected fields: {sorted(extra)}")
    if len(labels) != len(set(labels)):
        problems.append("prediction.branches labels must be unique")
    if abs(total - 1.0) > _PROBABILITY_SUM_TOLERANCE:
        problems.append(
            f"prediction.branches probabilities must sum to 1 "
            f"(tolerance {_PROBABILITY_SUM_TOLERANCE}); got {total}"
        )


def _validate_quantiles(quantiles: Any, problems: list[str]) -> None:
    if not isinstance(quantiles, dict):
        problems.append("prediction.quantiles must be an object")
        return
    levels = quantiles.get("levels")
    values = quantiles.get("values")
    if not isinstance(levels, list) or not levels:
        problems.append("prediction.quantiles.levels must be a non-empty array")
        return
    if not isinstance(values, list) or len(values) != len(levels):
        problems.append("prediction.quantiles.values must be an array aligned with levels")
        return
    prev = 0.0
    for tau in levels:
        if not isinstance(tau, (int, float)) or isinstance(tau, bool) or not 0.0 < float(tau) < 1.0:
            problems.append("prediction.quantiles.levels must be numbers in (0, 1)")
            return
        if float(tau) <= prev:
            problems.append("prediction.quantiles.levels must be strictly increasing")
            return
        prev = float(tau)
    for a, b in zip(values, values[1:]):
        if float(b) < float(a):
            problems.append("prediction.quantiles.values must be non-decreasing")
            return


def validate_structure(receipt: Any) -> list[str]:
    """Return a list of structural problems; empty list means valid."""
    problems: list[str] = []
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]

    required = (
        "version",
        "receipt_id",
        "created_at",
        "question",
        "prediction",
        "resolution_deadline",
        "resolution_source",
        "frozen_hash",
    )
    for name in required:
        if name not in receipt:
            problems.append(f"missing required field: {name}")
    if problems:
        return problems

    if receipt["version"] != "0.1":
        problems.append(f"version must be '0.1'; got {receipt['version']!r}")
    if not isinstance(receipt["receipt_id"], str) or not receipt["receipt_id"]:
        problems.append("receipt_id must be a non-empty string")
    if not _is_iso_datetime(receipt["created_at"]):
        problems.append("created_at must be an ISO 8601 date-time string")
    if not isinstance(receipt["question"], str) or not receipt["question"]:
        problems.append("question must be a non-empty string")
    if not _is_iso_datetime(receipt["resolution_deadline"]):
        problems.append("resolution_deadline must be an ISO 8601 date-time string")

    source = receipt["resolution_source"]
    if not isinstance(source, dict) or not isinstance(source.get("description"), str) or not source.get("description"):
        problems.append("resolution_source must be an object with a non-empty 'description'")

    frozen_hash = receipt["frozen_hash"]
    if (
        not isinstance(frozen_hash, str)
        or len(frozen_hash) != 64
        or any(c not in "0123456789abcdef" for c in frozen_hash)
    ):
        problems.append("frozen_hash must be a 64-character lowercase hex string")

    prediction = receipt["prediction"]
    if not isinstance(prediction, dict):
        problems.append("prediction must be an object")
    else:
        has_branches = "branches" in prediction
        has_quantiles = "quantiles" in prediction
        if has_branches == has_quantiles:
            problems.append("prediction must contain exactly one of 'branches' or 'quantiles'")
        elif has_branches:
            _validate_branches(prediction["branches"], problems)
        else:
            _validate_quantiles(prediction["quantiles"], problems)

    outcome = receipt.get("outcome")
    if outcome is not None:
        if not isinstance(outcome, dict):
            problems.append("outcome must be an object")
        else:
            if not _is_iso_datetime(outcome.get("resolved_at")):
                problems.append("outcome.resolved_at must be an ISO 8601 date-time string")
            if isinstance(prediction, dict) and "branches" in prediction:
                label = outcome.get("label")
                if not isinstance(label, str) or not label:
                    problems.append("outcome.label is required for branch predictions")
                else:
                    declared = {
                        b.get("label")
                        for b in prediction.get("branches", [])
                        if isinstance(b, dict)
                    }
                    if label not in declared:
                        problems.append(
                            f"outcome.label {label!r} is not one of the declared branch labels"
                        )
            if isinstance(prediction, dict) and "quantiles" in prediction:
                value = outcome.get("value")
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    problems.append("outcome.value (a number) is required for quantile predictions")
        if "scores" not in receipt:
            problems.append("scores are required once an outcome is present")

    if "scores" in receipt and outcome is None:
        problems.append("scores must not be present without an outcome")

    specimen = receipt.get("specimen")
    if specimen is not None and not isinstance(specimen, bool):
        problems.append("specimen must be a boolean")

    if "provenance" in receipt:
        provenance = receipt["provenance"]
        if provenance not in PROVENANCE_VALUES:
            problems.append(
                f"provenance must be one of {list(PROVENANCE_VALUES)}; got {provenance!r}"
            )
        elif specimen is True and provenance == "real":
            problems.append("a specimen receipt cannot declare provenance 'real'")

    return problems


# ---------------------------------------------------------------------------
# Score recomputation
# ---------------------------------------------------------------------------


def _branch_probabilities(prediction: dict[str, Any]) -> dict[str, float]:
    return {
        str(b["label"]): float(b["probability"])
        for b in prediction["branches"]
    }


def recompute_scores(receipt: dict[str, Any]) -> dict[str, float]:
    """Recompute the mechanical scores from `prediction` + `outcome`.

    Returns ``{"brier": ..., "log_loss": ...}`` for branch predictions
    and ``{"crps": ...}`` for quantile predictions. Raises
    ``ValueError`` if the receipt has no outcome.
    """
    outcome = receipt.get("outcome")
    if outcome is None:
        raise ValueError("receipt has no outcome; nothing to score")
    prediction = receipt["prediction"]
    if "branches" in prediction:
        predicted = _branch_probabilities(prediction)
        label = str(outcome["label"])
        return {
            "brier": brier_score(predicted, label),
            "log_loss": log_loss(predicted, label),
        }
    quantiles = prediction["quantiles"]
    return {
        "crps": crps_from_quantiles(
            quantiles["levels"], quantiles["values"], float(outcome["value"])
        )
    }


def _recompute_baseline(
    baseline: dict[str, Any], outcome: dict[str, Any]
) -> dict[str, float]:
    out: dict[str, float] = {}
    if "probabilities" in baseline:
        predicted = {str(k): float(v) for k, v in baseline["probabilities"].items()}
        label = str(outcome["label"])
        out["brier"] = brier_score(predicted, label)
        out["log_loss"] = log_loss(predicted, label)
    if "quantiles" in baseline:
        q = baseline["quantiles"]
        out["crps"] = crps_from_quantiles(q["levels"], q["values"], float(outcome["value"]))
    return out


# ---------------------------------------------------------------------------
# Verification report
# ---------------------------------------------------------------------------


_PROVENANCE_NOTES = {
    "real": (
        "issuer-declared; a passing frozen_hash shows the label was not changed "
        "after freezing, not that it is true"
    ),
    "synthetic": (
        "NOT evidence that any predicted event was observed, however cleanly "
        "it verifies"
    ),
    "fixture": (
        "test or demo artifact; NOT evidence that any predicted event was "
        "observed, however cleanly it verifies"
    ),
    "unknown": (
        "no provenance label, as on every receipt older than the field; "
        "verification alone does not show this is a real prediction"
    ),
}


@dataclass
class VerificationReport:
    """Outcome of verifying one receipt.

    ``checks`` decide ``passed``; ``warnings`` are reported but never fail
    a receipt. ``provenance`` is the declared label, or ``"unknown"``.
    """

    receipt_path: str
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)
    provenance: str = "unknown"
    specimen: bool = False

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append((name, ok, detail))

    def warn(self, name: str, detail: str) -> None:
        self.warnings.append((name, detail))

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(ok for _, ok, _ in self.checks)

    def render(self) -> str:
        lines = [f"Receipt verification: {self.receipt_path}"]
        for name, ok, detail in self.checks:
            tag = "PASS" if ok else "FAIL"
            lines.append(f"  [{tag}] {name}: {detail}")
        for name, detail in self.warnings:
            lines.append(f"  [WARN] {name}: {detail}")
        n = len(self.checks)
        summary = f"{sum(1 for _, ok, _ in self.checks if ok)}/{n} checks passed"
        if self.warnings:
            count = len(self.warnings)
            summary += f", {count} warning{'s' if count != 1 else ''}"
        lines.append(f"RESULT: {'PASS' if self.passed else 'FAIL'} ({summary})")
        provenance_line = (
            f"PROVENANCE: {self.provenance} ({_PROVENANCE_NOTES[self.provenance]})"
        )
        if self.specimen:
            provenance_line += "; specimen: true (illustrative, not a live track-record entry)"
        lines.append(provenance_line)
        return "\n".join(lines)


def _check_timeline(
    receipt: dict[str, Any], report: VerificationReport, now: datetime
) -> None:
    created = _parse_utc(receipt["created_at"])
    deadline = _parse_utc(receipt["resolution_deadline"])
    horizon = (
        f"created_at {receipt['created_at']} vs "
        f"resolution_deadline {receipt['resolution_deadline']}"
    )
    if created < deadline:
        report.add("timeline.frozen_before_deadline", True, f"{horizon}: frozen before its horizon")
    else:
        report.add(
            "timeline.frozen_before_deadline",
            False,
            f"{horizon}: the prediction was frozen at or after its own horizon",
        )
    if created > now + CLOCK_SKEW_TOLERANCE:
        report.warn(
            "timeline.future_created_at",
            f"created_at {receipt['created_at']} is later than the verifier's clock "
            f"({now.isoformat()})",
        )

    outcome = receipt.get("outcome")
    if outcome is None:
        return
    resolved = _parse_utc(outcome["resolved_at"])
    order = f"created_at {receipt['created_at']} vs outcome.resolved_at {outcome['resolved_at']}"
    if resolved > created:
        report.add("timeline.resolved_after_freeze", True, f"{order}: resolved after freezing")
    else:
        report.add(
            "timeline.resolved_after_freeze",
            False,
            f"{order}: the outcome is recorded at or before the moment the "
            "prediction was frozen",
        )
    if resolved > deadline:
        report.warn(
            "timeline.late_resolution",
            f"outcome.resolved_at {outcome['resolved_at']} is {resolved - deadline} after "
            f"resolution_deadline {receipt['resolution_deadline']}; the verifier cannot "
            "tell resolver latency from an outcome read outside the declared window",
        )
    if resolved > now + CLOCK_SKEW_TOLERANCE:
        report.warn(
            "timeline.future_resolved_at",
            f"outcome.resolved_at {outcome['resolved_at']} is later than the verifier's "
            f"clock ({now.isoformat()})",
        )


def verify_receipt(
    receipt: dict[str, Any],
    receipt_path: str = "<memory>",
    now: datetime | None = None,
) -> VerificationReport:
    """Run every verification check on a parsed receipt.

    ``now`` is the verification time used only for the future-timestamp
    warnings; it defaults to the current UTC time.
    """
    report = VerificationReport(receipt_path=receipt_path)
    if isinstance(receipt, dict):
        declared = receipt.get("provenance")
        if declared in PROVENANCE_VALUES:
            report.provenance = declared
        report.specimen = receipt.get("specimen") is True

    problems = validate_structure(receipt)
    if problems:
        report.add("structure", False, "; ".join(problems))
        return report
    report.add("structure", True, "receipt matches the expected shape")

    recorded_hash = receipt["frozen_hash"]
    recomputed_hash = compute_frozen_hash(receipt)
    if recomputed_hash == recorded_hash:
        report.add("frozen_hash", True, f"recomputed sha256 matches ({recomputed_hash[:16]}...)")
    else:
        report.add(
            "frozen_hash",
            False,
            f"recorded {recorded_hash} != recomputed {recomputed_hash} "
            "(a frozen field was altered after freezing)",
        )

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    _check_timeline(receipt, report, now)

    outcome = receipt.get("outcome")
    if outcome is None:
        report.add("scores", True, "pending: no outcome yet, nothing to score")
        return report

    recorded_scores = receipt.get("scores", {})
    try:
        recomputed = recompute_scores(receipt)
    except ValueError as exc:
        report.add("scores", False, f"could not recompute scores: {exc}")
        return report

    for name, value in sorted(recomputed.items()):
        if name not in recorded_scores:
            report.add(f"scores.{name}", False, f"missing from receipt (recomputed {value!r})")
            continue
        recorded = float(recorded_scores[name])
        if abs(recorded - value) <= SCORE_TOLERANCE:
            report.add(f"scores.{name}", True, f"recomputed {value!r} matches recorded value")
        else:
            report.add(
                f"scores.{name}",
                False,
                f"recorded {recorded!r} != recomputed {value!r}",
            )
    for name in sorted(set(recorded_scores) - set(recomputed)):
        report.add(
            f"scores.{name}",
            False,
            "recorded but not applicable to this prediction type",
        )

    baselines = receipt.get("baseline_scores", {})
    for baseline_name in sorted(baselines):
        baseline = baselines[baseline_name]
        try:
            recomputed_baseline = _recompute_baseline(baseline, outcome)
        except (KeyError, ValueError) as exc:
            report.add(
                f"baseline_scores.{baseline_name}",
                False,
                f"could not recompute: {exc}",
            )
            continue
        if not recomputed_baseline:
            report.add(
                f"baseline_scores.{baseline_name}",
                False,
                "baseline carries no distribution (probabilities/quantiles), not recomputable",
            )
            continue
        mismatches = []
        for name, value in sorted(recomputed_baseline.items()):
            recorded = baseline.get(name)
            if recorded is None or abs(float(recorded) - value) > SCORE_TOLERANCE:
                mismatches.append(f"{name}: recorded {recorded!r} != recomputed {value!r}")
        if mismatches:
            report.add(f"baseline_scores.{baseline_name}", False, "; ".join(mismatches))
        else:
            report.add(
                f"baseline_scores.{baseline_name}",
                True,
                "recomputed scores match recorded values",
            )

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print("usage: python -m omytea_protocol.verify RECEIPT.json", file=sys.stderr)
        return 2
    path = argv[0]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            receipt = json.load(fh)
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    report = verify_receipt(receipt, receipt_path=path)
    print(report.render())
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
