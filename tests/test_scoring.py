"""Tests for omytea_protocol.scoring — pin known closed-form values."""

import math

import pytest

from omytea_protocol.scoring import (
    brier_score,
    calibration_coverage,
    crps_from_quantiles,
    e_process_from_losses,
    e_value_update,
    log_loss,
)


# ---------------------------------------------------------------------------
# Brier
# ---------------------------------------------------------------------------


def test_brier_perfect_prediction_is_zero():
    assert brier_score({"a": 1.0, "b": 0.0}, "a") == 0.0


def test_brier_confidently_wrong_is_two():
    assert brier_score({"a": 1.0, "b": 0.0}, "b") == pytest.approx(2.0)


def test_brier_multiclass_closed_form():
    predicted = {"north": 0.55, "south": 0.20, "east": 0.15, "hold": 0.10}
    # (0.55-1)^2 + 0.2^2 + 0.15^2 + 0.1^2 = 0.2025 + 0.04 + 0.0225 + 0.01
    assert brier_score(predicted, "north") == pytest.approx(0.275)


def test_brier_outcome_outside_declared_labels_counts_as_zero_probability():
    predicted = {"a": 0.5, "b": 0.5}
    # (0-1)^2 + 0.5^2 + 0.5^2 = 1.5
    assert brier_score(predicted, "c") == pytest.approx(1.5)


def test_brier_rejects_unnormalized_distribution():
    with pytest.raises(ValueError):
        brier_score({"a": 0.5, "b": 0.4}, "a")


def test_brier_rejects_out_of_range_probability():
    with pytest.raises(ValueError):
        brier_score({"a": 1.2, "b": -0.2}, "a")


# ---------------------------------------------------------------------------
# Log loss
# ---------------------------------------------------------------------------


def test_log_loss_perfect_prediction_is_zero():
    assert log_loss({"a": 1.0, "b": 0.0}, "a") == 0.0


def test_log_loss_uniform_four_way():
    predicted = {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
    assert log_loss(predicted, "a") == pytest.approx(math.log(4.0))


def test_log_loss_zero_probability_is_large_but_finite():
    value = log_loss({"a": 1.0, "b": 0.0}, "b")
    assert math.isfinite(value)
    assert value == pytest.approx(-math.log(1e-12))


# ---------------------------------------------------------------------------
# CRPS from quantiles
# ---------------------------------------------------------------------------


def test_crps_single_median_reduces_to_absolute_error():
    # With the single level tau = 0.5, CRPS ~= |y - q|.
    assert crps_from_quantiles([0.5], [3.0], 7.0) == pytest.approx(4.0)
    assert crps_from_quantiles([0.5], [3.0], -1.0) == pytest.approx(4.0)


def test_crps_zero_when_forecast_is_point_mass_at_observation():
    levels = [0.1, 0.3, 0.5, 0.7, 0.9]
    values = [5.0] * 5
    # Every pinball term has u = 0.
    assert crps_from_quantiles(levels, values, 5.0) == pytest.approx(0.0)


def test_crps_penalizes_distance():
    levels = [0.25, 0.5, 0.75]
    near = crps_from_quantiles(levels, [4.0, 5.0, 6.0], 5.0)
    far = crps_from_quantiles(levels, [4.0, 5.0, 6.0], 15.0)
    assert near < far


def test_crps_matches_hand_computed_pinball_average():
    # levels (0.25, 0.75), values (0, 10), y = 5:
    #   tau=0.25: u = 5,  rho = 5 * 0.25          = 1.25
    #   tau=0.75: u = -5, rho = -5 * (0.75 - 1.0) = 1.25
    # CRPS = 2 * (1.25 + 1.25) / 2 = 2.5
    assert crps_from_quantiles([0.25, 0.75], [0.0, 10.0], 5.0) == pytest.approx(2.5)


def test_crps_rejects_bad_levels_and_values():
    with pytest.raises(ValueError):
        crps_from_quantiles([], [], 0.0)
    with pytest.raises(ValueError):
        crps_from_quantiles([0.5, 0.5], [1.0, 2.0], 0.0)  # not increasing
    with pytest.raises(ValueError):
        crps_from_quantiles([0.0, 0.5], [1.0, 2.0], 0.0)  # level not in (0,1)
    with pytest.raises(ValueError):
        crps_from_quantiles([0.25, 0.75], [2.0, 1.0], 0.0)  # values decreasing
    with pytest.raises(ValueError):
        crps_from_quantiles([0.25, 0.75], [1.0], 0.0)  # length mismatch


# ---------------------------------------------------------------------------
# Calibration coverage
# ---------------------------------------------------------------------------


def test_coverage_counts_inclusive_hits():
    intervals = [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (0.0, 1.0)]
    outcomes = [0.5, 0.0, 1.0, 2.0]  # endpoints count as covered
    assert calibration_coverage(intervals, outcomes) == pytest.approx(0.75)


def test_coverage_rejects_inverted_interval_and_empty_input():
    with pytest.raises(ValueError):
        calibration_coverage([(1.0, 0.0)], [0.5])
    with pytest.raises(ValueError):
        calibration_coverage([], [])
    with pytest.raises(ValueError):
        calibration_coverage([(0.0, 1.0)], [0.5, 0.6])


# ---------------------------------------------------------------------------
# E-value updates
# ---------------------------------------------------------------------------


def test_e_value_unchanged_when_losses_tie():
    assert e_value_update(1.0, 0.4, 0.4, lam=0.5) == pytest.approx(1.0)


def test_e_value_grows_when_forecaster_beats_baseline():
    # d = 1 - 0 = 1, factor = 1 + 0.5 * 1 = 1.5
    assert e_value_update(2.0, 0.0, 1.0, lam=0.5) == pytest.approx(3.0)


def test_e_value_shrinks_when_forecaster_loses():
    assert e_value_update(1.0, 1.0, 0.0, lam=0.5) == pytest.approx(0.5)


def test_e_value_stays_nonnegative():
    # Worst case factor is 1 - lam > 0, so wealth can never go negative.
    e = 1.0
    for _ in range(50):
        e = e_value_update(e, 1.0, 0.0, lam=0.99)
    assert e >= 0.0


def test_e_process_folds_updates():
    direct = e_process_from_losses([0.0, 0.0], [1.0, 1.0], lam=0.5)
    assert direct == pytest.approx(1.5 * 1.5)


def test_e_value_rejects_unnormalized_losses_and_bad_lambda():
    with pytest.raises(ValueError):
        e_value_update(1.0, 1.5, 0.5)
    with pytest.raises(ValueError):
        e_value_update(1.0, 0.5, -0.1)
    with pytest.raises(ValueError):
        e_value_update(1.0, 0.5, 0.5, lam=1.0)
    with pytest.raises(ValueError):
        e_value_update(-1.0, 0.5, 0.5)
