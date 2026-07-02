"""Proper scoring rules and verification math for prediction receipts.

Everything here is textbook, self-contained, and pure standard library.
Lower is better for every scoring rule in this module.

References
----------
- Brier, "Verification of Forecasts Expressed in Terms of Probability",
  Monthly Weather Review (1950).
- Gneiting & Raftery, "Strictly Proper Scoring Rules, Prediction, and
  Estimation", JASA (2007).
- Gneiting & Ranjan, "Comparing Density Forecasts Using Threshold- and
  Quantile-Weighted Scoring Rules", JBES (2011).
- Vovk, Gammerman & Shafer, "Algorithmic Learning in a Random World",
  Springer (2005); Angelopoulos & Bates, "Conformal Prediction: A Gentle
  Introduction", Foundations and Trends in ML (2023).
- Ville, "Etude critique de la notion de collectif" (1939); Shafer,
  "Testing by Betting", JRSS-A (2021); Ramdas, Grunwald, Vovk & Shafer,
  "Game-Theoretic Statistics and Safe Anytime-Valid Inference",
  Statistical Science (2023).
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

__all__ = [
    "brier_score",
    "log_loss",
    "crps_from_quantiles",
    "calibration_coverage",
    "e_value_update",
    "e_process_from_losses",
]


# ---------------------------------------------------------------------------
# Discrete (branch) predictions
# ---------------------------------------------------------------------------


def brier_score(predicted: Mapping[str, float], outcome_label: str) -> float:
    """Multi-category Brier score of a discrete distribution.

    BS = sum_k (p_k - o_k)^2

    where ``p_k`` is the predicted probability of category ``k`` and
    ``o_k`` is 1 for the realized category, 0 otherwise. A category
    absent from ``predicted`` is treated as probability 0. Lower is
    better; 0 is a perfect prediction; the worst possible value is 2
    (all mass on a wrong category).

    Reference: Brier (1950); Gneiting & Raftery (2007), Example 1.
    """
    if not predicted:
        raise ValueError("predicted distribution must be non-empty")
    _check_probabilities(predicted)
    total = 0.0
    labels = set(predicted) | {outcome_label}
    for label in sorted(labels):
        p = float(predicted.get(label, 0.0))
        o = 1.0 if label == outcome_label else 0.0
        total += (p - o) ** 2
    return total


def log_loss(
    predicted: Mapping[str, float],
    outcome_label: str,
    epsilon: float = 1e-12,
) -> float:
    """Logarithmic score of a discrete distribution.

    LogLoss = -ln p(outcome)

    The probability assigned to the realized category is clipped to
    ``[epsilon, 1]`` so a confidently wrong prediction receives a large
    finite penalty instead of infinity. Lower is better; 0 means the
    realized category was predicted with probability 1.

    Reference: Good (1952); Gneiting & Raftery (2007), Section 4.1.
    """
    if not predicted:
        raise ValueError("predicted distribution must be non-empty")
    if not 0.0 < epsilon < 1.0:
        raise ValueError("epsilon must be in (0, 1)")
    _check_probabilities(predicted)
    p = float(predicted.get(outcome_label, 0.0))
    p = min(1.0, max(epsilon, p))
    return -math.log(p)


def _check_probabilities(predicted: Mapping[str, float]) -> None:
    for label, p in predicted.items():
        if not 0.0 <= float(p) <= 1.0:
            raise ValueError(f"probability for {label!r} must be in [0, 1]; got {p}")
    total = sum(float(p) for p in predicted.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"probabilities must sum to 1 (tolerance 1e-6); got {total}")


# ---------------------------------------------------------------------------
# Continuous (quantile) predictions
# ---------------------------------------------------------------------------


def crps_from_quantiles(
    levels: Sequence[float],
    values: Sequence[float],
    observed: float,
) -> float:
    """CRPS of a quantile-represented predictive distribution.

    The continuous ranked probability score admits the quantile
    decomposition

        CRPS(F, y) = integral_0^1 2 * rho_tau(y - Q(tau)) d tau

    where ``Q`` is the quantile function of ``F`` and ``rho_tau`` is the
    pinball (quantile) loss ``rho_tau(u) = u * (tau - 1{u < 0})``. Given
    a finite grid of quantiles this integral is approximated by the
    average over the reported levels:

        CRPS ~= (2 / n) * sum_i rho_{tau_i}(y - q_i)

    which is exact in the limit of a dense level grid. With the single
    level ``tau = 0.5`` it reduces to the absolute error ``|y - q|``.
    Lower is better.

    Reference: Gneiting & Ranjan (2011), eq. (3)-(4); Gneiting &
    Raftery (2007), Section 4.2.
    """
    n = len(levels)
    if n == 0:
        raise ValueError("at least one quantile level is required")
    if len(values) != n:
        raise ValueError("levels and values must have the same length")
    prev_level = 0.0
    for tau in levels:
        tau = float(tau)
        if not 0.0 < tau < 1.0:
            raise ValueError(f"quantile levels must be in (0, 1); got {tau}")
        if tau <= prev_level:
            raise ValueError("quantile levels must be strictly increasing")
        prev_level = tau
    for a, b in zip(values, values[1:]):
        if float(b) < float(a):
            raise ValueError("quantile values must be non-decreasing")

    total = 0.0
    for tau, q in zip(levels, values):
        u = float(observed) - float(q)
        indicator = 1.0 if u < 0.0 else 0.0
        total += u * (float(tau) - indicator)
    return 2.0 * total / n


# ---------------------------------------------------------------------------
# Calibration: empirical interval coverage
# ---------------------------------------------------------------------------


def calibration_coverage(
    intervals: Sequence[tuple[float, float]],
    outcomes: Sequence[float],
) -> float:
    """Empirical coverage of prediction intervals.

    coverage = (1 / n) * sum_i 1{ lower_i <= y_i <= upper_i }

    For intervals produced by split conformal prediction at miscoverage
    level ``alpha``, the expected coverage is at least ``1 - alpha`` by
    construction (finite-sample, distribution-free), so the honest
    reading of a track record compares this empirical number against
    the nominal level and treats interval WIDTH as the discriminator of
    forecast quality, not coverage alone. Lower deviation from the
    nominal level is better; 1.0 with very wide intervals is not a
    merit.

    Reference: Vovk, Gammerman & Shafer (2005); Angelopoulos & Bates
    (2023), Section 1.
    """
    n = len(intervals)
    if n == 0:
        raise ValueError("at least one interval is required")
    if len(outcomes) != n:
        raise ValueError("intervals and outcomes must have the same length")
    hits = 0
    for (lower, upper), y in zip(intervals, outcomes):
        lower, upper, y = float(lower), float(upper), float(y)
        if lower > upper:
            raise ValueError(f"interval lower bound {lower} exceeds upper bound {upper}")
        if lower <= y <= upper:
            hits += 1
    return hits / n


# ---------------------------------------------------------------------------
# Anytime-valid comparison: e-value betting updates
# ---------------------------------------------------------------------------


def e_value_update(
    e_value: float,
    forecaster_loss: float,
    baseline_loss: float,
    lam: float = 0.1,
) -> float:
    """One betting-style e-value update for "forecaster beats baseline".

    Per resolved prediction, with both losses normalized to [0, 1],
    define the score differential ``d = baseline_loss -
    forecaster_loss`` (positive when the forecaster did better). The
    wealth update is

        E_new = E * (1 + lam * d),        lam in (0, 1)

    Under the null hypothesis "the forecaster is not better than the
    baseline" (``E[d | past] <= 0``), the wealth process is a
    nonnegative supermartingale with initial value 1, so by Ville's
    inequality ``P(sup_t E_t >= 1/alpha) <= alpha``. Reading the
    e-value at ANY time — including data-dependent stopping, i.e.
    glancing at a growing track record whenever you feel like it — is
    valid: e >= 20 is evidence at the 0.05 level that the forecaster
    beats the baseline. Boundedness of the losses is the only
    distributional assumption.

    Reference: Ville (1939); Shafer (2021); Ramdas, Grunwald, Vovk &
    Shafer (2023), Section 2 ("testing by betting").
    """
    if e_value < 0.0:
        raise ValueError("e_value must be nonnegative")
    if not 0.0 < lam < 1.0:
        raise ValueError(f"lam must be in (0, 1); got {lam}")
    for name, loss in (("forecaster_loss", forecaster_loss), ("baseline_loss", baseline_loss)):
        if not 0.0 <= float(loss) <= 1.0:
            raise ValueError(
                f"{name}={loss}; losses must be normalized to [0, 1] "
                "(boundedness is the validity condition)"
            )
    d = float(baseline_loss) - float(forecaster_loss)
    return e_value * (1.0 + lam * d)


def e_process_from_losses(
    forecaster_losses: Sequence[float],
    baseline_losses: Sequence[float],
    lam: float = 0.1,
) -> float:
    """Cumulative e-value over a sequence of resolved predictions.

    Folds :func:`e_value_update` over aligned loss sequences, starting
    from wealth 1. See :func:`e_value_update` for the validity
    guarantee and references.
    """
    if len(forecaster_losses) != len(baseline_losses):
        raise ValueError("loss sequences must have the same length")
    e = 1.0
    for f_loss, b_loss in zip(forecaster_losses, baseline_losses):
        e = e_value_update(e, f_loss, b_loss, lam=lam)
    return e
