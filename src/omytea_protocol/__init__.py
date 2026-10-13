"""omytea-protocol: receipt schema, scoring math, and verifier for machine predictions.

Predictions are frozen before the fact, resolved by independent sources,
mechanically scored, and packaged as receipts anyone can verify without
trusting the issuer. This package is the public verification half of
that loop: the schema, the scoring rules, and the verifier.
"""

from omytea_protocol.scoring import (
    brier_score,
    calibration_coverage,
    crps_from_quantiles,
    e_process_from_losses,
    e_value_update,
    log_loss,
)

__version__ = "0.1.0"

# Re-exported lazily (PEP 562) so that `python -m omytea_protocol.verify`
# does not import the verify module twice (once via the package, once as
# __main__), which would trigger a spurious RuntimeWarning from runpy.
_VERIFY_EXPORTS = (
    "FROZEN_FIELDS",
    "OPTIONAL_FROZEN_FIELDS",
    "PROVENANCE_VALUES",
    "canonical_frozen_payload",
    "compute_frozen_hash",
    "validate_structure",
    "recompute_scores",
    "verify_receipt",
)

__all__ = [
    "__version__",
    "brier_score",
    "log_loss",
    "crps_from_quantiles",
    "calibration_coverage",
    "e_value_update",
    "e_process_from_losses",
    *_VERIFY_EXPORTS,
]


def __getattr__(name: str):
    if name in _VERIFY_EXPORTS:
        from omytea_protocol import verify

        return getattr(verify, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
