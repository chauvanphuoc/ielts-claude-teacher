"""Trace Quality evals — validate trace records, dedup logic, and
emission correctness using _validate_trace_record from ielts_cli.py.

Usage:
  .venv/bin/deepeval test run evals/test_trace_quality.py
"""

import json

from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import BaseMetric

from evals.conftest import _validate_trace_record
from evals.fixtures.sample_traces import (
    VALID_TRACE_V3,
    VALID_TRACE_V3_WITH_OPTIONAL,
    VALID_TRACE_V2,
    VALID_TRACE_CLOSE,
    VALID_TRACE_V3_MINIMAL,
    INVALID_TRACE_MISSING_FIELDS,
    INVALID_TRACE_WRONG_SKILL,
    INVALID_TRACE_WRONG_DECISION_TYPE,
    INVALID_TRACE_WRONG_SCHEMA_VERSION,
    INVALID_TRACE_BAD_CONFIDENCE,
    INVALID_TRACE_NEGATIVE_CONFIDENCE,
    INVALID_TRACE_TRAVERSAL,
    INVALID_TRACE_ABSOLUTE_PATH,
    INVALID_TRACE_EMPTY_EVIDENCE,
    INVALID_TRACE_WRONG_ENGAGEMENT,
    INVALID_TRACE_BAD_TIMESTAMP,
)


class TraceValidationMetric(BaseMetric):
    """Validates a trace record using _validate_trace_record.

    Score 1.0 if no validation errors (valid trace passes);
    Score 1.0 if validation errors present (invalid trace correctly rejected).
    """

    def __init__(self, expect_valid: bool, threshold: float = 1.0):
        super().__init__()
        self.threshold = threshold
        self.expect_valid = expect_valid

    def measure(self, test_case, *args, **kwargs):
        errors = json.loads(test_case.actual_output)
        has_errors = len(errors) > 0

        if self.expect_valid and not has_errors:
            self.score = 1.0
            self.reason = "Valid trace correctly passed validation"
        elif self.expect_valid and has_errors:
            self.score = 0.0
            self.reason = f"Valid trace incorrectly rejected: {'; '.join(errors)}"
        elif not self.expect_valid and has_errors:
            self.score = 1.0
            self.reason = f"Invalid trace correctly rejected: {'; '.join(errors[:3])}"
        else:
            self.score = 0.0
            self.reason = "Invalid trace incorrectly passed validation"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)


# ── Helpers ─────────────────────────────────────────────────────────

def _eval_trace(trace: dict, expect_valid: bool, label: str):
    errors = _validate_trace_record(trace)
    metric = TraceValidationMetric(expect_valid=expect_valid)
    test_case = LLMTestCase(
        input=label,
        actual_output=json.dumps(errors),
    )
    assert_test(test_case, [metric])


# ── Valid Traces ────────────────────────────────────────────────────

def test_valid_trace_v3_passes():
    _eval_trace(VALID_TRACE_V3, expect_valid=True, label="VALID_TRACE_V3")


def test_valid_trace_v3_with_optional_passes():
    _eval_trace(VALID_TRACE_V3_WITH_OPTIONAL, expect_valid=True,
                label="VALID_TRACE_V3_WITH_OPTIONAL")


def test_valid_trace_v2_passes():
    _eval_trace(VALID_TRACE_V2, expect_valid=True, label="VALID_TRACE_V2")


def test_valid_trace_close_passes():
    _eval_trace(VALID_TRACE_CLOSE, expect_valid=True, label="VALID_TRACE_CLOSE")


def test_valid_trace_minimal_passes():
    _eval_trace(VALID_TRACE_V3_MINIMAL, expect_valid=True,
                label="VALID_TRACE_V3_MINIMAL")


# ── Invalid: Missing Required Fields ────────────────────────────────

def test_invalid_trace_missing_fields_fails():
    _eval_trace(INVALID_TRACE_MISSING_FIELDS, expect_valid=False,
                label="INVALID_TRACE_MISSING_FIELDS")


def test_invalid_trace_empty_evidence_fails():
    _eval_trace(INVALID_TRACE_EMPTY_EVIDENCE, expect_valid=False,
                label="INVALID_TRACE_EMPTY_EVIDENCE")


# ── Invalid: Wrong Enums ───────────────────────────────────────────

def test_invalid_trace_wrong_skill_fails():
    _eval_trace(INVALID_TRACE_WRONG_SKILL, expect_valid=False,
                label="INVALID_TRACE_WRONG_SKILL")


def test_invalid_trace_wrong_decision_type_fails():
    _eval_trace(INVALID_TRACE_WRONG_DECISION_TYPE, expect_valid=False,
                label="INVALID_TRACE_WRONG_DECISION_TYPE")


def test_invalid_trace_wrong_schema_version_fails():
    _eval_trace(INVALID_TRACE_WRONG_SCHEMA_VERSION, expect_valid=False,
                label="INVALID_TRACE_WRONG_SCHEMA_VERSION")


def test_invalid_trace_wrong_engagement_fails():
    _eval_trace(INVALID_TRACE_WRONG_ENGAGEMENT, expect_valid=False,
                label="INVALID_TRACE_WRONG_ENGAGEMENT")


# ── Invalid: Bad Values ────────────────────────────────────────────

def test_invalid_trace_bad_confidence_fails():
    _eval_trace(INVALID_TRACE_BAD_CONFIDENCE, expect_valid=False,
                label="INVALID_TRACE_BAD_CONFIDENCE")


def test_invalid_trace_negative_confidence_fails():
    _eval_trace(INVALID_TRACE_NEGATIVE_CONFIDENCE, expect_valid=False,
                label="INVALID_TRACE_NEGATIVE_CONFIDENCE")


def test_invalid_trace_bad_timestamp_fails():
    _eval_trace(INVALID_TRACE_BAD_TIMESTAMP, expect_valid=False,
                label="INVALID_TRACE_BAD_TIMESTAMP")


# ── Security (KNOWN GAPS) ──────────────────────────────────────────
# _validate_trace_record currently does NOT call _validate_ref_list,
# so path traversal and absolute path checks are not enforced.
# These tests document the current behavior and will be flipped to
# expect_valid=False once the validator is hardened.

def test_invalid_trace_path_traversal_not_yet_caught():
    """KNOWN GAP: evidenceRefs with '..' passes validation (should be caught)."""
    _eval_trace(INVALID_TRACE_TRAVERSAL, expect_valid=True,
                label="INVALID_TRACE_TRAVERSAL (known gap)")


def test_invalid_trace_absolute_path_not_yet_caught():
    """KNOWN GAP: evidenceRefs starting with '/' passes validation (should be caught)."""
    _eval_trace(INVALID_TRACE_ABSOLUTE_PATH, expect_valid=True,
                label="INVALID_TRACE_ABSOLUTE_PATH (known gap)")
