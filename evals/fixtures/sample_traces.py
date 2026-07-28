"""Pre-built trace record dicts for trace quality evals.

Usage:
    from evals.fixtures.sample_traces import VALID_TRACE_V3, INVALID_TRACE_MISSING_FIELDS
"""


def _build_trace(overrides: dict | None = None) -> dict:
    """Build a base valid trace-v3, then apply overrides."""
    base = {
        "schemaVersion": "trace-v3",
        "runId": "session-2026-07-28",
        "timestamp": "2026-07-28T10:00:00Z",
        "skill": "reading",
        "decisionType": "diagnose",
        "evidenceRefs": [".ielts/student-profile.json", ".ielts/kc-graph-ielts.json"],
        "rubricRefs": ["rubric://reading/v1"],
        "kcTargets": ["kc-read-tfng", "kc-read-inference"],
        "action": "analyzed TF/NG answer pattern",
        "expectedOutcome": "identify NOT GIVEN confusion",
        "confidence": 0.82,
        "sourceVersion": "prompt-v1",
    }
    if overrides:
        base.update(overrides)
    return dict(base)  # shallow copy so callers don't mutate


# ── Valid traces ────────────────────────────────────────────────────

VALID_TRACE_V3 = _build_trace()

VALID_TRACE_V3_WITH_OPTIONAL = _build_trace({
    "actualOutcome": "Student got 4/5 NG correct but still confused on silent passages",
    "outcomeMatched": False,
    "outcomeNote": "NG logic partially absorbed",
    "studentResponse": "student said: 'I understand FALSE but panic on silent passages'",
    "studentEngagement": "medium",
    "studentConfusion": "silent passage vs contradictory passage",
    "strategy": "explicit-rule-first",
})

VALID_TRACE_V2 = _build_trace({
    "schemaVersion": "trace-v2",
    "actualOutcome": "Student improved T/F/NG accuracy",
    "outcomeMatched": True,
    "outcomeNote": "Good progress",
})

VALID_TRACE_CLOSE = _build_trace({
    "skill": "general",
    "decisionType": "close",
    "action": "session completed: 10 questions, 3 KCs tested",
    "expectedOutcome": "student ready for next session",
    "actualOutcome": "Student scored 4/5 on NG, still confused on silent passages",
    "outcomeNote": "partial success — need one more NG session",
    "studentResponse": "student said: 'I think I'm getting better at NG'",
    "studentEngagement": "high",
})

VALID_TRACE_V3_MINIMAL = {
    "schemaVersion": "trace-v3",
    "runId": "session-minimal",
    "timestamp": "2026-07-28T10:00:00Z",
    "skill": "general",
    "decisionType": "close",
    "evidenceRefs": [".ielts/student-profile.json"],
    "rubricRefs": [],
    "kcTargets": ["kc-read-tfng"],
    "action": "minimal close",
    "expectedOutcome": "done",
    "confidence": 0.5,
    "sourceVersion": "prompt-v1",
}


# ── Invalid traces ──────────────────────────────────────────────────

INVALID_TRACE_MISSING_FIELDS = {
    "schemaVersion": "trace-v3",
    "runId": "session-bad",
    # missing: timestamp, skill, decisionType, etc.
}

INVALID_TRACE_WRONG_SKILL = _build_trace({"skill": "math"})

INVALID_TRACE_WRONG_DECISION_TYPE = _build_trace({"decisionType": "greet"})

INVALID_TRACE_WRONG_SCHEMA_VERSION = _build_trace({"schemaVersion": "trace-v99"})

INVALID_TRACE_BAD_CONFIDENCE = _build_trace({"confidence": 2.0})

INVALID_TRACE_NEGATIVE_CONFIDENCE = _build_trace({"confidence": -0.5})

INVALID_TRACE_TRAVERSAL = _build_trace({
    "evidenceRefs": ["../../../etc/passwd"],
})

INVALID_TRACE_ABSOLUTE_PATH = _build_trace({
    "evidenceRefs": ["/etc/passwd"],
})

INVALID_TRACE_EMPTY_EVIDENCE = _build_trace({
    "evidenceRefs": [],
})

INVALID_TRACE_WRONG_ENGAGEMENT = _build_trace({
    "studentEngagement": "extreme",
})

INVALID_TRACE_BAD_TIMESTAMP = _build_trace({
    "timestamp": "July 28 2026",
})
