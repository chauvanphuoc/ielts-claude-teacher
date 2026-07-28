"""KC Mastery Update evals — test cumulative error rate, level thresholds,
SRS intervals, and subjective scoring per SKILL.md Phase 5.3.

Usage:
  .venv/bin/deepeval test run evals/test_kc_mastery.py
"""

import json

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import BaseMetric

from evals.conftest import (
    compute_error_rate,
    compute_level,
    compute_srs_next_review,
    compute_subjective_error_rate,
)
from evals.fixtures.kc_scenarios import (
    ERROR_RATE_SCENARIOS,
    LEVEL_SCENARIOS,
    SRS_SCENARIOS,
    SUBJECTIVE_SCORING_SCENARIOS,
    KC_UPDATE_SCENARIOS,
)


# ── Custom Metrics ──────────────────────────────────────────────────

class ErrorRateMetric(BaseMetric):
    """Check cumulative error rate formula produces expected value."""

    def __init__(self, expected: float, tolerance: float = 0.001,
                 threshold: float = 1.0):
        super().__init__()
        self.threshold = threshold
        self.expected = expected
        self.tolerance = tolerance

    def measure(self, test_case, *args, **kwargs):
        actual = float(test_case.actual_output)
        if abs(actual - self.expected) > self.tolerance:
            self.score = 0.0
            self.reason = f"Expected errorRate={self.expected}, got {actual}"
        else:
            self.score = 1.0
            self.reason = f"errorRate={actual} matches expected={self.expected}"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)


class LevelThresholdMetric(BaseMetric):
    """Check errorRate -> level derivation."""

    def __init__(self, expected_level: str, threshold: float = 1.0):
        super().__init__()
        self.threshold = threshold
        self.expected_level = expected_level

    def measure(self, test_case, *args, **kwargs):
        actual = test_case.actual_output
        if actual != self.expected_level:
            self.score = 0.0
            self.reason = f"Expected level='{self.expected_level}', got '{actual}'"
        else:
            self.score = 1.0
            self.reason = f"level='{actual}' matches expected"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)


class KCMasteryUpdateMetric(BaseMetric):
    """Full KC update: apply formula, check both errorRate and level."""

    def __init__(self, expected_error_rate: float, expected_level: str,
                 tolerance: float = 0.001, threshold: float = 1.0):
        super().__init__()
        self.threshold = threshold
        self.expected_error_rate = expected_error_rate
        self.expected_level = expected_level
        self.tolerance = tolerance

    def measure(self, test_case, *args, **kwargs):
        data = json.loads(test_case.actual_output)
        actual_err = data["errorRate"]
        actual_level = data["level"]
        failures = []
        if abs(actual_err - self.expected_error_rate) > self.tolerance:
            failures.append(
                f"Expected errorRate={self.expected_error_rate}, got {actual_err}"
            )
        if actual_level != self.expected_level:
            failures.append(
                f"Expected level='{self.expected_level}', got '{actual_level}'"
            )
        self.score = 1.0 if not failures else 0.0
        self.reason = "; ".join(failures) if failures else \
            f"errorRate={actual_err}, level='{actual_level}' — all correct"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)


# ── Error Rate Tests ────────────────────────────────────────────────

@pytest.mark.parametrize("scenario", ERROR_RATE_SCENARIOS)
def test_error_rate_formula(scenario):
    """Test cumulative error rate formula with various inputs."""
    (attempts, cur_err, sess_err), expected = scenario
    actual = compute_error_rate(attempts, cur_err, sess_err)
    metric = ErrorRateMetric(expected=expected)
    test_case = LLMTestCase(
        input=f"attempts={attempts}, cur_err={cur_err}, sess_err={sess_err}",
        actual_output=str(actual),
    )
    assert_test(test_case, [metric])


# ── Level Threshold Tests ───────────────────────────────────────────

@pytest.mark.parametrize("scenario", LEVEL_SCENARIOS)
def test_level_threshold(scenario):
    """Test errorRate -> level derivation at boundaries."""
    error_rate, expected_level = scenario
    actual = compute_level(error_rate)
    metric = LevelThresholdMetric(expected_level=expected_level)
    test_case = LLMTestCase(
        input=f"errorRate={error_rate}",
        actual_output=str(actual),
    )
    assert_test(test_case, [metric])


# ── SRS Interval Tests ──────────────────────────────────────────────

@pytest.mark.parametrize("scenario", SRS_SCENARIOS)
def test_srs_interval(scenario):
    """Test spaced repetition nextReviewDate per attempt count."""
    attempts, last_tested, expected_next = scenario
    actual = compute_srs_next_review(attempts, last_tested)
    assert actual == expected_next, \
        f"SRS interval wrong: attempt {attempts}, expected {expected_next}, got {actual}"


# ── Subjective Scoring Tests ────────────────────────────────────────

@pytest.mark.parametrize("scenario", SUBJECTIVE_SCORING_SCENARIOS)
def test_subjective_scoring(scenario):
    """Test subjective error rate for speaking/writing."""
    (target, scored), expected = scenario
    actual = compute_subjective_error_rate(target, scored)
    metric = ErrorRateMetric(expected=expected)
    test_case = LLMTestCase(
        input=f"targetBand={target}, scoredBand={scored}",
        actual_output=str(actual),
    )
    assert_test(test_case, [metric])


# ── Full KC Update Tests ───────────────────────────────────────────

@pytest.mark.parametrize("scenario", KC_UPDATE_SCENARIOS)
def test_kc_mastery_update(scenario):
    """Test full KC mastery update: input state + session -> expected outcome."""
    kc_input, session_err, expected_err, expected_level = scenario
    attempts = kc_input["attempts"]
    cur_err = kc_input["errorRate"]

    new_err = compute_error_rate(attempts, cur_err, session_err)
    new_level = compute_level(new_err)

    metric = KCMasteryUpdateMetric(
        expected_error_rate=expected_err,
        expected_level=expected_level,
    )
    test_case = LLMTestCase(
        input=f"attempts={attempts}, cur_err={cur_err}, session_err={session_err}",
        actual_output=json.dumps({"errorRate": new_err, "level": new_level}),
    )
    assert_test(test_case, [metric])


# ── Specific Named Tests ────────────────────────────────────────────

def test_error_rate_cumulative_first_attempt():
    """First attempt: (0*0 + 1.0) / 1 = 1.0"""
    actual = compute_error_rate(0, 0.0, 1.0)
    assert actual == 1.0, f"Expected 1.0, got {actual}"


def test_error_rate_cumulative_improvement():
    """Improving: (1*1.0 + 0.0) / 2 = 0.5"""
    actual = compute_error_rate(1, 1.0, 0.0)
    assert actual == 0.5, f"Expected 0.5, got {actual}"


def test_level_weak_boundary():
    """errorRate >= 0.40 -> weak"""
    assert compute_level(0.40) == "weak"
    assert compute_level(0.80) == "weak"
    assert compute_level(1.00) == "weak"


def test_level_ok_boundary():
    """errorRate 0.15-0.39 -> ok"""
    assert compute_level(0.15) == "ok"
    assert compute_level(0.30) == "ok"
    assert compute_level(0.39) == "ok"


def test_level_mastered_boundary():
    """errorRate < 0.15 -> mastered"""
    assert compute_level(0.0) == "mastered"
    assert compute_level(0.10) == "mastered"
    assert compute_level(0.14) == "mastered"


def test_srs_interval_attempt_1():
    """1st attempt -> review in 1 day"""
    from datetime import date
    today = date.today().isoformat()
    expected = (date.today() + __import__('datetime').timedelta(days=1)).isoformat()
    assert compute_srs_next_review(1, today) == expected


def test_srs_interval_attempt_4():
    """4th attempt -> review in 30 days"""
    from datetime import date
    today = date.today().isoformat()
    expected = (date.today() + __import__('datetime').timedelta(days=30)).isoformat()
    assert compute_srs_next_review(4, today) == expected


def test_subjective_scoring_standard():
    """target 7.0, scored 5.5 -> errorRate = (7-5.5)/7 = 0.214"""
    actual = compute_subjective_error_rate(7.0, 5.5)
    assert abs(actual - 0.214) < 0.001, f"Expected ~0.214, got {actual}"
