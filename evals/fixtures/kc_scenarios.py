"""Test vectors for KC mastery update formulas.

Each scenario is a tuple of (input, expected_output) for testing:
- compute_error_rate(attempts, current_error_rate, session_error_rate)
- compute_level(error_rate)
- compute_srs_next_review(attempts, last_tested_date)
- compute_subjective_error_rate(target_band, scored_band)

Usage:
    from evals.fixtures.kc_scenarios import ERROR_RATE_SCENARIOS, LEVEL_SCENARIOS
"""

from datetime import date, timedelta


def _d(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


# ── Error Rate Cumulative Formula ───────────────────────────────────
# Formula: new_errorRate = (attempts * current_errorRate + session_errorRate)
#                        / (attempts + 1)
# Each entry: (attempts, current_errorRate, session_errorRate) -> expected_errorRate
ERROR_RATE_SCENARIOS = [
    # First attempt ever
    ((0, 0.0, 1.0), 1.0),          # all wrong on first try
    ((0, 0.0, 0.0), 0.0),          # perfect first try
    ((0, 0.0, 0.40), 0.40),        # 2/5 correct on first try
    ((0, 0.0, 0.20), 0.20),        # 4/5 correct on first try
    # Cumulative update: error rate improving
    ((1, 1.00, 0.00), 0.50),       # (1*1.0 + 0.0) / 2 = 0.50
    ((1, 1.00, 0.50), 0.75),       # (1*1.0 + 0.5) / 2 = 0.75
    ((1, 0.50, 0.00), 0.25),       # (1*0.5 + 0.0) / 2 = 0.25
    ((2, 0.60, 0.20), 0.467),      # (2*0.6 + 0.2) / 3 ≈ 0.467
    ((2, 0.80, 0.20), 0.60),       # (2*0.8 + 0.2) / 3 = 0.60
    ((2, 0.40, 0.40), 0.40),       # (2*0.4 + 0.4) / 3 = 0.40
    ((3, 0.30, 0.00), 0.225),      # (3*0.3 + 0.0) / 4 = 0.225
    ((3, 0.30, 0.30), 0.30),       # (3*0.3 + 0.3) / 4 = 0.30
    ((5, 0.80, 0.20), 0.70),       # (5*0.8 + 0.2) / 6 = 0.70
    ((5, 0.40, 0.00), 0.333),      # (5*0.4 + 0.0) / 6 ≈ 0.333
    # Edge: session_errorRate > 1.0 (shouldn't happen, but formula works)
    ((1, 0.50, 1.50), 1.0),        # (1*0.5 + 1.5) / 2 = 1.0
    ((1, 1.00, 2.00), 1.50),       # formula produces 1.5 (needs clamp at caller)
    # Edge: large attempts
    ((50, 0.10, 0.00), 0.098),     # (50*0.1 + 0.0) / 51 ≈ 0.098
]


# ── Level Thresholds ────────────────────────────────────────────────
# Each entry: errorRate -> expected_level
LEVEL_SCENARIOS = [
    (0.0, "mastered"),
    (0.01, "mastered"),
    (0.14, "mastered"),
    (0.149, "mastered"),
    (0.15, "ok"),         # boundary: >= 0.15 -> ok
    (0.20, "ok"),
    (0.30, "ok"),
    (0.39, "ok"),
    (0.399, "ok"),
    (0.40, "weak"),       # boundary: >= 0.40 -> weak
    (0.50, "weak"),
    (0.80, "weak"),
    (1.00, "weak"),
    # Edge: above 1.0 (shouldn't happen in practice)
    (1.50, "weak"),
]


# ── SRS Intervals ───────────────────────────────────────────────────
# Each entry: (attempts, last_tested_date_offset_days) -> expected_next_review_offset_days
def _srs_scenario(attempts: int, last_offset: int, expected_next_offset: int):
    return (attempts, _d(last_offset), _d(expected_next_offset))

SRS_SCENARIOS = [
    _srs_scenario(1, 0, 1),    # attempt 1 -> +1 day
    _srs_scenario(2, 0, 3),    # attempt 2 -> +3 days
    _srs_scenario(3, 0, 7),    # attempt 3 -> +7 days
    _srs_scenario(4, 0, 30),   # attempt 4 -> +30 days
    _srs_scenario(5, 0, 30),   # attempt 5 -> +30 days (cap)
    _srs_scenario(10, 0, 30),  # attempt 10 -> +30 days (cap)
]


# ── Subjective Scoring ─────────────────────────────────────────────
# Each entry: (target_band, scored_band) -> expected_errorRate
SUBJECTIVE_SCORING_SCENARIOS = [
    ((7.0, 7.0), 0.0),            # perfect match
    ((7.0, 5.5), 0.214),          # (7.0 - 5.5) / 7.0 ≈ 0.214
    ((7.0, 4.5), 0.357),          # (7.0 - 4.5) / 7.0 ≈ 0.357
    ((7.0, 2.0), 0.714),          # (7.0 - 2.0) / 7.0 ≈ 0.714
    ((6.0, 6.0), 0.0),            # perfect match
    ((6.0, 5.0), 0.167),          # (6.0 - 5.0) / 6.0 ≈ 0.167
    ((9.0, 8.0), 0.111),          # (9.0 - 8.0) / 9.0 ≈ 0.111
    ((9.0, 4.0), 0.556),          # (9.0 - 4.0) / 9.0 ≈ 0.556
    # Edge: targetBand <= 0 -> skip
    ((0.0, 5.0), 0.0),            # targetBand 0 -> return 0
    # Edge: scoredBand > targetBand (shouldn't happen)
    ((7.0, 8.0), 0.0),            # clamp to 0
]


# ── KC Mastery Update Full ──────────────────────────────────────────
# Integration: input state + session result -> expected mastery update
# Each entry: (input_kc, session_errorRate) -> (expected_errorRate, expected_level)
KC_UPDATE_SCENARIOS = [
    # Weak -> gets weaker (more errors)
    ({"attempts": 2, "errorRate": 0.60}, 0.80, 0.667, "weak"),
    # Weak -> improves
    ({"attempts": 2, "errorRate": 0.60}, 0.20, 0.467, "weak"),
    # Ok -> improves to mastered
    ({"attempts": 3, "errorRate": 0.30}, 0.00, 0.225, "ok"),
    # Ok -> drops to weak
    ({"attempts": 1, "errorRate": 0.20}, 0.80, 0.50, "weak"),
    # Mastered -> stays mastered (perfect)
    ({"attempts": 4, "errorRate": 0.10}, 0.00, 0.08, "mastered"),
    # Mastered -> drops to ok
    ({"attempts": 4, "errorRate": 0.10}, 0.40, 0.16, "ok"),
    # First attempt -> perfect
    ({"attempts": 0, "errorRate": 0.0}, 0.00, 0.0, "mastered"),
    # First attempt -> all wrong
    ({"attempts": 0, "errorRate": 0.0}, 1.00, 1.0, "weak"),
]
