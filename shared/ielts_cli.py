#!/usr/bin/env python3
"""IELTS Claude Teacher — Data Layer CLI.

Single-file, stdlib-only Python script for managing all IELTS data.
Called by SKILL.md prompts and Claude workflows via Bash.

All data lives in .ielts/ at the project root — never in home directory.

Usage:
  .venv/bin/python3 shared/ielts_cli.py init
  .venv/bin/python3 shared/ielts_cli.py migrate-profile
  .venv/bin/python3 shared/ielts_cli.py settings get
  .venv/bin/python3 shared/ielts_cli.py settings set language en
  .venv/bin/python3 shared/ielts_cli.py status
  .venv/bin/python3 shared/ielts_cli.py backup
  .venv/bin/python3 shared/ielts_cli.py lesson-library list
  .venv/bin/python3 shared/ielts_cli.py lesson-library sync
  .venv/bin/python3 shared/ielts_cli.py lesson-library add --id ... --title ... --skill ... --file ...
  .venv/bin/python3 shared/ielts_cli.py lesson-library mark-used --id ...
  .venv/bin/python3 shared/ielts_cli.py migrate-lesson-library
  .venv/bin/python3 shared/ielts_cli.py reset-profile --yes
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime, date, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
# Resolve project root: this file lives at shared/ielts_cli.py
CLI_FILE = Path(__file__).resolve()
PROJECT_ROOT = CLI_FILE.parent.parent
IELTS_DIR = PROJECT_ROOT / ".ielts"
BACKUP_DIR = IELTS_DIR / "backup"
ARCHIVE_DIR = IELTS_DIR / "archive"

ROADMAP_FILE = IELTS_DIR / "roadmap.json"
PROFILE_FILE = IELTS_DIR / "student-profile.json"
KC_GRAPH_FILE = IELTS_DIR / "kc-graph-ielts.json"
SETTINGS_FILE = IELTS_DIR / "settings.json"
LESSON_LIBRARY_FILE = IELTS_DIR / "lesson-library.json"
LESSON_PLANS_DIR = IELTS_DIR / "lesson-plans"
VOCAB_DIR = IELTS_DIR / "vocabulary"
SYNONYMS_FILE = IELTS_DIR / "vocabulary" / "synonyms.json"

# Quality control plane paths (W1 scaffold)
QUALITY_DIR = IELTS_DIR / "quality"
QUALITY_CONFIG_DIR = QUALITY_DIR / "config"
QUALITY_RUNS_DIR = QUALITY_DIR / "runs"
QUALITY_TRACES_DIR = QUALITY_DIR / "traces"
QUALITY_EVALS_DIR = QUALITY_DIR / "evals"
QUALITY_EVAL_REGISTRY_DIR = QUALITY_EVALS_DIR / "registry"
QUALITY_GATES_DIR = QUALITY_DIR / "gates"
QUALITY_GATE_CHECKPOINTS_DIR = QUALITY_GATES_DIR / "checkpoints"
QUALITY_INCIDENTS_DIR = QUALITY_GATES_DIR / "incidents"
QUALITY_GATE_REHEARSALS_DIR = QUALITY_GATES_DIR / "rehearsals"
QUALITY_GATE_PROMOTIONS_DIR = QUALITY_GATES_DIR / "promotions"
QUALITY_OVERRIDES_DIR = QUALITY_GATES_DIR / "overrides"
QUALITY_RECOMMENDATIONS_DIR = QUALITY_DIR / "recommendations"
QUALITY_RUNBOOKS_DIR = QUALITY_DIR / "runbooks"
QUALITY_BASELINES_DIR = QUALITY_DIR / "baselines"
QUALITY_SHADOW_DIR = QUALITY_DIR / "shadow"
QUALITY_SHADOW_WEEKLY_DIR = QUALITY_SHADOW_DIR / "weekly"
QUALITY_WEEKLY_REVIEWS_DIR = QUALITY_RUNBOOKS_DIR / "weekly-reviews"

THRESHOLDS_READING_V1_FILE = QUALITY_CONFIG_DIR / "thresholds-reading-v1.yaml"
TRACE_SCHEMA_V1_FILE = QUALITY_CONFIG_DIR / "trace-schema-v1.json"
ERROR_RESCUE_MAP_FILE = QUALITY_RUNBOOKS_DIR / "error-rescue-map.md"
HARD_GATE_ROLLBACK_PLAYBOOK_FILE = QUALITY_RUNBOOKS_DIR / "hard-gate-rollback-playbook.md"
BASELINE_TEMPLATE_FILE = QUALITY_BASELINES_DIR / "baseline-template.json"
RUN_INDEX_FILE = QUALITY_RUNS_DIR / "index.json"
GATESET_INDEX_FILE = QUALITY_EVAL_REGISTRY_DIR / "index.json"
COVERAGE_MATRIX_READING_V1_FILE = QUALITY_CONFIG_DIR / "coverage-matrix-reading-v1.yaml"
OVERRIDE_CONTRACT_V1_FILE = QUALITY_CONFIG_DIR / "override-contract-v1.yaml"
SOFT_GATE_POLICY_V1_FILE = QUALITY_CONFIG_DIR / "soft-gate-policy-v1.yaml"
PERFORMANCE_BUDGET_READING_V1_FILE = QUALITY_CONFIG_DIR / "performance-budget-reading-v1.yaml"
SHADOW_LANE_POLICY_V1_FILE = QUALITY_CONFIG_DIR / "shadow-lane-policy-v1.json"
SCHEMA_COMPAT_RULES_V1_FILE = QUALITY_CONFIG_DIR / "schema-compat-rules-v1.json"
GATE_MODE_CONTROL_V1_FILE = QUALITY_CONFIG_DIR / "gate-mode-control-v1.json"
HARD_GATE_PROMOTION_CRITERIA_V1_FILE = QUALITY_CONFIG_DIR / "hard-gate-promotion-v1.json"
PHASE_GATES_V1_FILE = QUALITY_CONFIG_DIR / "phase-gates-v1.json"
IMMUTABILITY_LEDGER_FILE = QUALITY_RUNS_DIR / "immutability-ledger.json"
PHASE_GATE_STATE_FILE = QUALITY_RUNBOOKS_DIR / "phase-gate-state.json"
KT_ONBOARDING_FILE = QUALITY_RUNBOOKS_DIR / "onboarding-operator.md"
KT_DECISION_LOG_TEMPLATE_FILE = QUALITY_RUNBOOKS_DIR / "decision-log-template.md"
KT_PACK_MAINTENANCE_LOG_FILE = QUALITY_RUNBOOKS_DIR / "kt-pack-maintenance.md"

REQUIRED_TRACE_FIELDS = {
    "schemaVersion": str,
    "runId": str,
    "timestamp": str,
    "skill": str,
    "decisionType": str,
    "evidenceRefs": list,
    "rubricRefs": list,
    "kcTargets": list,
    "action": str,
    "expectedOutcome": str,
    "confidence": (int, float),
    "sourceVersion": str,
}

ALLOWED_SKILLS = {"general", "reading", "listening", "writing", "speaking"}
ALLOWED_DECISION_TYPES = {"diagnose", "plan", "teach", "evaluate", "close"}
ALLOWED_SCHEMA_VERSIONS = {"trace-v1", "trace-v2", "trace-v3"}
ALLOWED_ENGAGEMENT_LEVELS = {"high", "medium", "low"}
ALLOWED_LANES = {"reading", "listening", "writing", "speaking"}


# ── Utilities ──────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def _tomorrow() -> str:
    return (date.today() + __import__('datetime').timedelta(days=1)).isoformat()


def _days_from_now(n: int) -> str:
    return (date.today() + __import__('datetime').timedelta(days=n)).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_json(path: Path, data):
    _ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)  # atomic on same filesystem


def _backup_file(path: Path):
    """Create a timestamped backup of a file before modifying it."""
    if not path.exists():
        return None
    _ensure_dir(BACKUP_DIR)
    stem = path.stem
    backup_path = BACKUP_DIR / f"{stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(path, backup_path)
    return backup_path


def _slugify(value: str) -> str:
    """Return a filesystem-safe slug."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"


def _iso_date_from_ts(ts: str) -> str:
    """Extract YYYY-MM-DD from ISO-like timestamp. Falls back to today."""
    if isinstance(ts, str) and len(ts) >= 10:
        maybe = ts[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", maybe):
            return maybe
    return _today()


def _parse_json_or_jsonl(path: Path):
    """Parse a JSON object/list or JSONL file into a list of records."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return []

    # Try JSON first.
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []
    except json.JSONDecodeError:
        pass

    # Fallback to JSONL.
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError as exc:
                records.append({
                    "_parseError": f"JSONL parse error at line {line_num}: {exc}",
                    "_raw": text,
                })
    return records


def _validate_trace_record(record: dict) -> list[str]:
    """Validate one trace record against the W1 contract."""
    errors = []

    if not isinstance(record, dict):
        return ["record must be a JSON object"]

    if "_parseError" in record:
        return [record["_parseError"]]

    for field, expected_type in REQUIRED_TRACE_FIELDS.items():
        if field not in record:
            errors.append(f"missing required field: {field}")
            continue
        if not isinstance(record[field], expected_type):
            errors.append(f"field {field} has wrong type: expected {expected_type}, got {type(record[field]).__name__}")

    skill = record.get("skill")
    if isinstance(skill, str) and skill not in ALLOWED_SKILLS:
        errors.append(f"skill must be one of {sorted(ALLOWED_SKILLS)}, got '{skill}'")

    decision_type = record.get("decisionType")
    if isinstance(decision_type, str) and decision_type not in ALLOWED_DECISION_TYPES:
        errors.append(
            f"decisionType must be one of {sorted(ALLOWED_DECISION_TYPES)}, got '{decision_type}'"
        )

    confidence = record.get("confidence")
    if isinstance(confidence, (int, float)):
        if confidence < 0 or confidence > 1:
            errors.append(f"confidence must be in [0,1], got {confidence}")

    for list_field in ("evidenceRefs", "rubricRefs", "kcTargets"):
        value = record.get(list_field)
        if isinstance(value, list):
            if list_field == "evidenceRefs" and len(value) < 1:
                errors.append("evidenceRefs must contain at least 1 element")
            if any(not isinstance(x, str) or not x.strip() for x in value):
                errors.append(f"{list_field} must contain non-empty strings")

    # Lightweight timestamp shape check.
    ts = record.get("timestamp")
    if isinstance(ts, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*Z", ts):
        errors.append("timestamp should be ISO UTC format, e.g. 2026-07-27T10:00:00Z")

    # ── v2: schema version + optional outcome fields ──
    sv = record.get("schemaVersion")
    if isinstance(sv, str) and sv not in ALLOWED_SCHEMA_VERSIONS:
        errors.append(f"schemaVersion must be one of {sorted(ALLOWED_SCHEMA_VERSIONS)}, got '{sv}'")

    # Validate optional v2 outcome fields (type-check only when present).
    actual = record.get("actualOutcome")
    if actual is not None and not isinstance(actual, str):
        errors.append(f"actualOutcome must be a string, got {type(actual).__name__}")

    matched = record.get("outcomeMatched")
    if matched is not None and not isinstance(matched, bool):
        errors.append(f"outcomeMatched must be a boolean, got {type(matched).__name__}")

    note = record.get("outcomeNote")
    if note is not None and not isinstance(note, str):
        errors.append(f"outcomeNote must be a string, got {type(note).__name__}")

    # ── v3: student response + strategy fields ──
    sresp = record.get("studentResponse")
    if sresp is not None and not isinstance(sresp, str):
        errors.append(f"studentResponse must be a string, got {type(sresp).__name__}")

    eng = record.get("studentEngagement")
    if eng is not None:
        if not isinstance(eng, str) or eng not in ALLOWED_ENGAGEMENT_LEVELS:
            errors.append(f"studentEngagement must be one of {sorted(ALLOWED_ENGAGEMENT_LEVELS)}, got '{eng}'")

    conf = record.get("studentConfusion")
    if conf is not None and not isinstance(conf, str):
        errors.append(f"studentConfusion must be a string, got {type(conf).__name__}")

    strat = record.get("strategy")
    if strat is not None and not isinstance(strat, str):
        errors.append(f"strategy must be a string, got {type(strat).__name__}")

    return errors


def _validate_ref_list(refs, field_name: str) -> list[str]:
    """Validate trace metadata references against security boundary rules."""
    errors = []
    if not isinstance(refs, list):
        return [f"{field_name} must be a list"]
    if field_name == "evidenceRefs" and len(refs) < 1:
        errors.append("evidenceRefs must contain at least 1 element")

    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            errors.append(f"{field_name} must contain non-empty strings")
            continue
        token = ref.strip()
        if len(token) > 512:
            errors.append(f"{field_name} entry too long (max 512): {token[:48]}...")
        if ".." in token:
            errors.append(f"{field_name} cannot contain path traversal '..': {token}")
        if token.startswith("/"):
            errors.append(f"{field_name} cannot be absolute path: {token}")
        if not re.match(r"^(ev://|rubric://|kc://|dataset://|artifact://|ref:|[A-Za-z0-9._/-]+$)", token):
            errors.append(f"{field_name} has unsupported format: {token}")
    return errors


def _validate_run_metadata(run_id: str, correlation_id: str, source_version: str, lane: str | None = None) -> list[str]:
    """Validate run metadata contract with explicit reject behavior."""
    errors = []

    def _check_token(label: str, value: str):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} is required")
            return
        if len(value) > 120:
            errors.append(f"{label} too long (max 120)")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            errors.append(f"{label} must match [A-Za-z0-9._-]+")

    _check_token("runId", run_id)
    _check_token("correlationId", correlation_id)
    _check_token("sourceVersion", source_version)

    if lane is not None and lane not in ALLOWED_LANES:
        errors.append(f"lane must be one of {sorted(ALLOWED_LANES)}, got '{lane}'")

    return errors


# ── Trace Dedup Helpers ────────────────────────────────────────────

def _trace_idempotency_key(record: dict) -> str:
    """Generate an idempotency key from the trace's core decision fields.

    Two traces sharing the same (runId, skill, decisionType, action,
    expectedOutcome) are considered duplicates.  The 16-char hex digest
    is small enough to compare cheaply, large enough to avoid collisions.
    """
    key_fields = (
        record.get("runId", ""),
        record.get("skill", ""),
        record.get("decisionType", ""),
        record.get("action", ""),
        record.get("expectedOutcome", ""),
    )
    key_str = "|".join(key_fields)
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]


def _trace_exists(trace_path: Path, idempotency_key: str) -> bool:
    """Check whether a trace with `idempotency_key` already exists in *trace_path*.

    Scans the JSONL file line-by-line and short-circuits on first match.
    """
    if not trace_path.exists():
        return False
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                    if _trace_idempotency_key(existing) == idempotency_key:
                        return True
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        pass
    return False


# ── Trace Emission ─────────────────────────────────────────────────

def emit_trace(
    skill: str,
    decision_type: str,
    evidence_refs: list[str],
    rubric_refs: list[str],
    kc_targets: list[str],
    action: str,
    expected_outcome: str,
    confidence: float,
    source_version: str = "prompt-v1",
    run_id: str | None = None,
    actual_outcome: str | None = None,
    outcome_matched: bool | None = None,
    outcome_note: str | None = None,
    student_response: str | None = None,
    student_engagement: str | None = None,
    student_confusion: str | None = None,
    strategy: str | None = None,
    teacher_transcript: str | None = None,
    schema_version: str = "trace-v3",
) -> dict:
    """Emit one decision trace record to the quality control plane.

    Appends a JSONL line to .ielts/quality/traces/{date}.jsonl and
    (best-effort) appends a coach note to student-profile.json.

    Returns {"status": "ok", "path": "..."} on success,
            {"status": "error", "errors": [...]} on failure.

    This function is called by the IELTS teacher at each phase boundary
    (diagnose, plan, teach, evaluate, close) in the 6-phase teaching loop.

    v3 (default): adds student response capture + strategy tagging for
    A/B testing and closed-loop teaching quality improvement.
    """
    _ensure_dir(QUALITY_TRACES_DIR)

    # Build trace record
    record = {
        "schemaVersion": schema_version,
        "runId": run_id or f"session-{_today()}",
        "timestamp": _now(),
        "skill": skill,
        "decisionType": decision_type,
        "evidenceRefs": evidence_refs,
        "rubricRefs": rubric_refs,
        "kcTargets": kc_targets,
        "action": action,
        "expectedOutcome": expected_outcome,
        "confidence": confidence,
        "sourceVersion": source_version,
    }

    # ── v2 outcome fields (optional, only written when provided) ──
    if actual_outcome is not None:
        record["actualOutcome"] = actual_outcome
    if outcome_matched is not None:
        record["outcomeMatched"] = outcome_matched
    if outcome_note is not None:
        record["outcomeNote"] = outcome_note

    # ── v3 student response + strategy fields ──
    if student_response is not None:
        record["studentResponse"] = student_response
    if student_engagement is not None:
        record["studentEngagement"] = student_engagement
    if student_confusion is not None:
        record["studentConfusion"] = student_confusion
    if strategy is not None:
        record["strategy"] = strategy

    # ── v4 teacher transcript (for GEval pedagogical scoring) ──
    if teacher_transcript is not None:
        # Truncate to max length for storage efficiency
        record["teacherTranscript"] = teacher_transcript[:8000]

    # Validate
    errors = _validate_trace_record(record)
    if errors:
        # Write invalid trace to separate sink
        invalid_path = QUALITY_TRACES_DIR / "invalid-traces.jsonl"
        with open(invalid_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({**record, "errors": errors}, ensure_ascii=False, default=str) + "\n")
        return {"status": "error", "errors": errors, "record": record}

    # Dedup: skip if an identical decision was already emitted today.
    # Idempotency key covers (runId, skill, decisionType, action, expectedOutcome).
    date_key = _iso_date_from_ts(record["timestamp"])
    trace_path = QUALITY_TRACES_DIR / f"{date_key}.jsonl"
    dedup_key = _trace_idempotency_key(record)
    if _trace_exists(trace_path, dedup_key):
        return {"status": "ok", "path": str(trace_path), "dedup": True, "record": record}

    # Write valid trace
    try:
        with open(trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except (OSError, IOError) as e:
        return {"status": "error", "errors": [f"Failed to write trace: {e}"]}

    # Best-effort dual-write to coach notes
    _emit_coach_note(record)

    return {"status": "ok", "path": str(trace_path), "record": record}


def _emit_coach_note(record: dict):
    """Best-effort: append a coach note to student-profile.json for a trace record.

    If the profile is missing, locked, or the write fails, the trace is still
    valid — the coach note is a convenience, not a requirement.
    """
    try:
        profile = _load_json(PROFILE_FILE)
        if not profile:
            return

        note = {
            "date": record["timestamp"],
            "category": "trace",
            "skill": record["skill"],
            "content": (
                f"[{record['decisionType']}] {record['action']} — "
                f"expected: {record['expectedOutcome']} "
                f"(confidence: {record['confidence']:.0%})"
            ),
            "priority": "low",
        }

        if "coachNotes" not in profile:
            profile["coachNotes"] = []
        profile["coachNotes"].append(note)

        _save_json(PROFILE_FILE, profile)
    except (OSError, IOError, json.JSONDecodeError):
        # Best-effort — trace is already written, coach note is optional
        pass


def _load_thresholds_reading_v1() -> dict:
    """Parse simple YAML threshold file into metric dictionary.

    This parser intentionally supports only the constrained shape we generate.
    """
    if not THRESHOLDS_READING_V1_FILE.exists():
        raise FileNotFoundError(f"Threshold registry missing: {THRESHOLDS_READING_V1_FILE}")

    text = THRESHOLDS_READING_V1_FILE.read_text(encoding="utf-8")

    def _extract(name: str, key: str) -> float:
        # Example block:
        # replay_pass_rate:
        #   min: 0.75
        pattern = rf"{name}:\s*\n\s+{key}:\s*([0-9]+(?:\.[0-9]+)?)"
        m = re.search(pattern, text)
        if not m:
            raise ValueError(f"Cannot parse threshold '{name}.{key}' from registry")
        return float(m.group(1))

    return {
        "replay_pass_rate_min": _extract("replay_pass_rate", "min"),
        "trace_completeness_min": _extract("trace_completeness", "min"),
        "content_fidelity_error_rate_max": _extract("content_fidelity_error_rate", "max"),
        "min_sample_size": int(_extract("min_sample_size", "value")),
    }


def _load_coverage_matrix_reading_v1() -> dict:
    """Parse coverage matrix v1 from constrained YAML shape."""
    if not COVERAGE_MATRIX_READING_V1_FILE.exists():
        raise FileNotFoundError(f"Coverage matrix missing: {COVERAGE_MATRIX_READING_V1_FILE}")

    text = COVERAGE_MATRIX_READING_V1_FILE.read_text(encoding="utf-8")

    def _parse_section(section_name: str) -> dict:
        lines = text.splitlines()
        entries = {}
        in_section = False
        current_key = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped == f"{section_name}:":
                in_section = True
                current_key = None
                continue

            if in_section and not line.startswith(" "):
                break

            if not in_section:
                continue

            if stripped.endswith(":") and stripped not in {"min_pass_rate:", "min_cases:"}:
                key = stripped[:-1]
                if key not in {"min_pass_rate", "min_cases"}:
                    current_key = key
                    entries[current_key] = {}
                continue

            if stripped.startswith("min_pass_rate:") and current_key:
                value = stripped.split(":", 1)[1].strip()
                entries[current_key]["min_pass_rate"] = float(value)
                continue

            if stripped.startswith("min_cases:") and current_key:
                value = stripped.split(":", 1)[1].strip()
                entries[current_key]["min_cases"] = int(value)
                continue

        ready = {
            key: val
            for key, val in entries.items()
            if "min_pass_rate" in val and "min_cases" in val
        }
        if not ready:
            raise ValueError(f"Cannot parse section '{section_name}' in coverage matrix")
        return ready

    return {
        "kc_buckets": _parse_section("kc_buckets"),
        "question_types": _parse_section("question_types"),
    }


def _load_override_contract_v1() -> dict:
    """Parse emergency override contract config from constrained YAML shape."""
    if not OVERRIDE_CONTRACT_V1_FILE.exists():
        raise FileNotFoundError(f"Override contract missing: {OVERRIDE_CONTRACT_V1_FILE}")

    text = OVERRIDE_CONTRACT_V1_FILE.read_text(encoding="utf-8")

    req_fields = []
    in_req = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "required_fields:":
            in_req = True
            continue
        if in_req:
            if stripped.startswith("- "):
                req_fields.append(stripped[2:].strip())
            elif stripped:
                break

    sev_match = re.search(r"severity_allowed:\s*\n\s*-\s*([a-z]+)\s*\n\s*-\s*([a-z]+)\s*\n\s*-\s*([a-z]+)", text)
    if not req_fields or not sev_match:
        raise ValueError("Cannot parse override contract required_fields/severity_allowed")

    return {
        "required_fields": req_fields,
        "severity_allowed": [sev_match.group(1), sev_match.group(2), sev_match.group(3)],
    }


def _load_soft_gate_policy_v1() -> dict:
    """Parse soft-gate approval policy from constrained YAML shape."""
    if not SOFT_GATE_POLICY_V1_FILE.exists():
        raise FileNotFoundError(f"Soft-gate policy missing: {SOFT_GATE_POLICY_V1_FILE}")

    text = SOFT_GATE_POLICY_V1_FILE.read_text(encoding="utf-8")
    mode_match = re.search(r"approval_mode:\s*([a-z_]+)", text)
    if not mode_match:
        raise ValueError("Cannot parse approval_mode from soft-gate policy")

    mode = mode_match.group(1)
    allowed = ["founder_approval", "auto_accepts"]
    if mode not in allowed:
        raise ValueError(f"approval_mode must be one of {allowed}, got '{mode}'")

    return {"approval_mode": mode, "allowed_modes": allowed}


def _save_soft_gate_policy_v1(mode: str):
    if mode not in {"founder_approval", "auto_accepts"}:
        raise ValueError("mode must be founder_approval or auto_accepts")
    SOFT_GATE_POLICY_V1_FILE.write_text(
        (
            "version: v1\n"
            "lane: reading\n"
            f"approval_mode: {mode}\n"
            "notes: yellow/red soft-gate handling mode\n"
        ),
        encoding="utf-8",
    )


def _load_performance_budget_reading_v1() -> dict:
    """Parse performance budget config from constrained YAML shape."""
    if not PERFORMANCE_BUDGET_READING_V1_FILE.exists():
        raise FileNotFoundError(f"Performance budget missing: {PERFORMANCE_BUDGET_READING_V1_FILE}")

    text = PERFORMANCE_BUDGET_READING_V1_FILE.read_text(encoding="utf-8")

    def _extract_int(key: str) -> int:
        m = re.search(rf"{key}:\s*([0-9]+)", text)
        if not m:
            raise ValueError(f"Cannot parse '{key}' from performance budget")
        return int(m.group(1))

    stage_names = ["setup", "replay", "evaluate", "gate", "recommendation"]
    stage_timeouts = {}
    for name in stage_names:
        m = re.search(rf"{name}:\s*([0-9]+)", text)
        if not m:
            raise ValueError(f"Cannot parse stage timeout '{name}' from performance budget")
        stage_timeouts[name] = int(m.group(1))

    return {
        "max_cases_per_run": _extract_int("max_cases_per_run"),
        "memory_ceiling_mb": _extract_int("memory_ceiling_mb"),
        "concurrency_limit": _extract_int("concurrency_limit"),
        "stage_timeouts_sec": stage_timeouts,
    }


def _evaluate_performance_budget(perf_metrics: dict, budget: dict) -> tuple[dict, list[str]]:
    """Evaluate run metrics against performance budget contract."""
    errors = []
    if not isinstance(perf_metrics, dict):
        return {}, ["Performance metrics must be a JSON object"]

    total_cases = perf_metrics.get("totalCasesExecuted")
    peak_memory = perf_metrics.get("peakMemoryMb")
    concurrency = perf_metrics.get("concurrencyUsed")
    stage_durations = perf_metrics.get("stageDurationsSec")

    if not isinstance(total_cases, int) or total_cases < 0:
        errors.append("totalCasesExecuted must be a non-negative integer")
    if not isinstance(peak_memory, (int, float)) or peak_memory < 0:
        errors.append("peakMemoryMb must be a non-negative number")
    if not isinstance(concurrency, int) or concurrency < 0:
        errors.append("concurrencyUsed must be a non-negative integer")
    if not isinstance(stage_durations, dict) or not stage_durations:
        errors.append("stageDurationsSec must be a non-empty object")

    required_stages = sorted(budget["stage_timeouts_sec"].keys())
    if isinstance(stage_durations, dict):
        for stage in required_stages:
            value = stage_durations.get(stage)
            if not isinstance(value, (int, float)) or value < 0:
                errors.append(f"stageDurationsSec.{stage} must be a non-negative number")

    if errors:
        return {}, errors

    stage_checks = {}
    for stage, threshold in budget["stage_timeouts_sec"].items():
        observed = float(stage_durations[stage])
        stage_checks[stage] = {
            "passed": observed <= threshold,
            "thresholdSec": threshold,
            "observedSec": observed,
        }

    checks = {
        "maxCasesPerRun": {
            "passed": total_cases <= budget["max_cases_per_run"],
            "threshold": budget["max_cases_per_run"],
            "observed": total_cases,
        },
        "memoryCeilingMb": {
            "passed": float(peak_memory) <= budget["memory_ceiling_mb"],
            "threshold": budget["memory_ceiling_mb"],
            "observed": float(peak_memory),
        },
        "concurrencyLimit": {
            "passed": concurrency <= budget["concurrency_limit"],
            "threshold": budget["concurrency_limit"],
            "observed": concurrency,
        },
        "stageTimeouts": stage_checks,
    }

    checks["passed"] = (
        checks["maxCasesPerRun"]["passed"]
        and checks["memoryCeilingMb"]["passed"]
        and checks["concurrencyLimit"]["passed"]
        and all(v["passed"] for v in stage_checks.values())
    )
    return checks, []


def _load_shadow_lane_policy_v1() -> dict:
    policy = _load_json(SHADOW_LANE_POLICY_V1_FILE)
    if not policy:
        raise FileNotFoundError(f"Missing shadow lane policy: {SHADOW_LANE_POLICY_V1_FILE}")

    errors = []
    ratio = policy.get("sampleSliceRatio")
    min_cases = policy.get("minCases")
    if not isinstance(ratio, (int, float)) or ratio <= 0 or ratio > 1:
        errors.append("sampleSliceRatio must be in (0,1]")
    if not isinstance(min_cases, int) or min_cases <= 0:
        errors.append("minCases must be a positive integer")
    lane = policy.get("lane")
    if lane not in ALLOWED_LANES:
        errors.append(f"lane must be one of {sorted(ALLOWED_LANES)}")

    if errors:
        raise ValueError("; ".join(errors))
    return policy


def _load_schema_compat_rules_v1() -> dict:
    rules = _load_json(SCHEMA_COMPAT_RULES_V1_FILE)
    if not rules:
        raise FileNotFoundError(f"Missing schema compatibility rules: {SCHEMA_COMPAT_RULES_V1_FILE}")

    artifacts = rules.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("schema-compat-rules artifacts must be an object")
    for artifact_type in ("trace", "eval"):
        spec = artifacts.get(artifact_type)
        if not isinstance(spec, dict):
            raise ValueError(f"schema-compat-rules missing artifacts.{artifact_type}")
        if not isinstance(spec.get("currentVersion"), str) or not spec["currentVersion"].strip():
            raise ValueError(f"artifacts.{artifact_type}.currentVersion must be non-empty")
        if not isinstance(spec.get("allowedVersions"), list) or not spec["allowedVersions"]:
            raise ValueError(f"artifacts.{artifact_type}.allowedVersions must be a non-empty list")
        if not isinstance(spec.get("requiredFields"), list) or not spec["requiredFields"]:
            raise ValueError(f"artifacts.{artifact_type}.requiredFields must be a non-empty list")
        if not isinstance(spec.get("versionField"), str) or not spec["versionField"].strip():
            raise ValueError(f"artifacts.{artifact_type}.versionField must be non-empty")
    return rules


def _load_gate_mode_control_v1() -> dict:
    data = _load_json(GATE_MODE_CONTROL_V1_FILE)
    if not data:
        raise FileNotFoundError(f"Missing gate mode config: {GATE_MODE_CONTROL_V1_FILE}")

    mode = data.get("mode")
    allowed = data.get("allowedModes")
    if not isinstance(allowed, list) or not allowed:
        raise ValueError("allowedModes must be a non-empty list")
    if mode not in allowed:
        raise ValueError(f"mode must be one of {allowed}, got '{mode}'")
    return data


def _save_gate_mode_control_v1(mode: str):
    current = _load_json(
        GATE_MODE_CONTROL_V1_FILE,
        {
            "version": "gate-mode-control-v1",
            "allowedModes": ["report-only", "soft-gate", "hard-gate"],
        },
    )
    allowed = current.get("allowedModes", ["report-only", "soft-gate", "hard-gate"])
    if mode not in allowed:
        raise ValueError(f"mode must be one of {allowed}, got '{mode}'")

    payload = {
        "version": "gate-mode-control-v1",
        "mode": mode,
        "allowedModes": allowed,
        "updatedAt": _now(),
    }
    _save_json(GATE_MODE_CONTROL_V1_FILE, payload)
    return payload


def _load_hard_gate_promotion_criteria_v1() -> dict:
    criteria = _load_json(HARD_GATE_PROMOTION_CRITERIA_V1_FILE)
    if not criteria:
        raise FileNotFoundError(f"Missing hard-gate promotion criteria: {HARD_GATE_PROMOTION_CRITERIA_V1_FILE}")

    required_int_fields = ["stableCyclesRequired", "minSampleSize"]
    required_float_fields = ["traceCompletenessMin", "replayPassRateMin", "contentFidelityErrorRateMax"]
    errors = []
    for field in required_int_fields:
        value = criteria.get(field)
        if not isinstance(value, int) or value <= 0:
            errors.append(f"{field} must be a positive integer")
    for field in required_float_fields:
        value = criteria.get(field)
        if not isinstance(value, (int, float)):
            errors.append(f"{field} must be numeric")

    if criteria.get("founderApprovalRequired") not in {True, False}:
        errors.append("founderApprovalRequired must be boolean")

    if errors:
        raise ValueError("; ".join(errors))
    return criteria


def _iso_week_key(ts: str) -> str:
    """Return ISO week key YYYY-Www from UTC timestamp string."""
    if not isinstance(ts, str):
        dt = datetime.now(timezone.utc)
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    try:
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        dt = datetime.now(timezone.utc)
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_immutability_ledger() -> dict:
    ledger = _load_json(IMMUTABILITY_LEDGER_FILE, {"version": "immutability-ledger-v1", "runs": {}, "lockedPaths": {}})
    ledger.setdefault("runs", {})
    ledger.setdefault("lockedPaths", {})
    return ledger


def _save_immutability_ledger(ledger: dict):
    _save_json(IMMUTABILITY_LEDGER_FILE, ledger)


def _is_artifact_locked(path: Path) -> bool:
    ledger = _load_immutability_ledger()
    return str(path) in ledger.get("lockedPaths", {})


def _lock_run_artifacts(run_id: str, artifact_map: dict, published_by: str | None) -> dict:
    ledger = _load_immutability_ledger()
    now = _now()

    run_entry = {
        "runId": run_id,
        "publishedAt": now,
        "publishedBy": published_by or "operator",
        "artifacts": {},
    }

    for key, value in artifact_map.items():
        if not isinstance(value, str) or not value.strip():
            continue
        path = Path(value)
        if not path.exists() or path.is_dir():
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        run_entry["artifacts"][key] = {"path": str(path), "sha256": sha}
        ledger["lockedPaths"][str(path)] = {
            "runId": run_id,
            "artifact": key,
            "lockedAt": now,
            "sha256": sha,
        }

    ledger["runs"][run_id] = run_entry
    _save_immutability_ledger(ledger)
    return run_entry


def _load_phase_gates_v1() -> dict:
    data = _load_json(PHASE_GATES_V1_FILE)
    if not data:
        raise FileNotFoundError(f"Missing phase gates config: {PHASE_GATES_V1_FILE}")
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases:
        raise ValueError("phase gates config must include non-empty phases list")
    if len(set(phases)) != len(phases):
        raise ValueError("phase gates list must not contain duplicates")
    return data


def _load_phase_gate_state() -> dict:
    return _load_json(PHASE_GATE_STATE_FILE, {"version": "phase-gate-state-v1", "completed": {}})


def _save_phase_gate_state(state: dict):
    _save_json(PHASE_GATE_STATE_FILE, state)


def _phase_prereq_errors(target_phase: str) -> list[str]:
    config = _load_phase_gates_v1()
    phases = config["phases"]
    if target_phase not in phases:
        return [f"Unknown phase '{target_phase}'"]

    state = _load_phase_gate_state()
    completed = state.get("completed", {})
    target_index = phases.index(target_phase)
    missing = []
    for idx in range(target_index):
        phase = phases[idx]
        if phase not in completed:
            missing.append(phase)
    if missing:
        return [f"Missing prerequisite phase completion: {', '.join(missing)}"]
    return []


def _append_kt_pack_update(phase: str, summary: str):
    _ensure_dir(QUALITY_RUNBOOKS_DIR)
    with open(KT_PACK_MAINTENANCE_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"- {_now()} | phase={phase} | {summary}\n")


def _ensure_kt_pack_files():
    if not KT_ONBOARDING_FILE.exists():
        KT_ONBOARDING_FILE.write_text(
            """# Onboarding Operator

1. Run quality init.
2. Create run manifest and execute report-only or soft-gate.
3. Validate gates and record weekly review.
4. Check phase gate status before starting next phase.
""",
            encoding="utf-8",
        )
    if not KT_DECISION_LOG_TEMPLATE_FILE.exists():
        KT_DECISION_LOG_TEMPLATE_FILE.write_text(
            """# Decision Log Template

- Date:
- Phase:
- Decision:
- Context:
- Tradeoffs:
- Owner:
- Follow-up:
""",
            encoding="utf-8",
        )
    if not KT_PACK_MAINTENANCE_LOG_FILE.exists():
        KT_PACK_MAINTENANCE_LOG_FILE.write_text("# KT Pack Maintenance Log\n\n", encoding="utf-8")


def _validate_override_request_payload(request: dict, contract: dict) -> list[str]:
    """Validate override payload against contract fields and enums."""
    errors = []
    if not isinstance(request, dict):
        return ["Override request must be a JSON object"]

    for field in contract["required_fields"]:
        if field not in request:
            errors.append(f"missing required field: {field}")
            continue
        value = request[field]
        if isinstance(value, str) and not value.strip():
            errors.append(f"field {field} must be non-empty")

    severity = request.get("severity")
    if severity is not None and severity not in contract["severity_allowed"]:
        errors.append(
            f"severity must be one of {contract['severity_allowed']}, got '{severity}'"
        )
    return errors


def _load_run_manifest(run_id: str) -> dict:
    """Load one run manifest by run ID."""
    path = QUALITY_RUNS_DIR / run_id / "manifest.json"
    data = _load_json(path)
    if not data:
        raise FileNotFoundError(f"Manifest not found for runId '{run_id}': {path}")
    return data


def _load_run_index() -> dict:
    return _load_json(RUN_INDEX_FILE, {"version": "run-index-v1", "dedupe": {}, "correlations": {}})


def _save_run_index(index_data: dict):
    _save_json(RUN_INDEX_FILE, index_data)


def _dedupe_key(trigger: str, lane: str, source_version: str, explicit_key: str | None) -> str:
    if explicit_key:
        return _slugify(explicit_key)
    basis = f"{trigger}|{lane}|{source_version}|{_today()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def _load_gateset_index() -> dict:
    return _load_json(GATESET_INDEX_FILE, {"version": "gateset-index-v1", "items": {}})


def _save_gateset_index(index_data: dict):
    _save_json(GATESET_INDEX_FILE, index_data)


# ── Lesson Library Helpers ─────────────────────────────────────────

def _scan_lesson_html(filepath: Path) -> dict | None:
    """Extract lesson metadata from an HTML file.

    Reads <title> for the lesson title, looks for <meta name="kc-tags">
    for KC tags, and infers skill from filename or KC tag prefixes.
    Returns None if the file can't be read or isn't a lesson.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(4096)  # first 4KB is enough for head
    except (IOError, OSError):
        return None

    # Extract title from <title> tag
    import re
    title_match = re.search(r"<title>(.*?)</title>", content)
    title = title_match.group(1).strip() if title_match else filepath.stem

    # Strip the " — IELTS Claude Teacher" suffix
    title = re.sub(r"\s*[—–-]\s*IELTS Claude Teacher\s*$", "", title)

    # Extract KC tags from <meta name="kc-tags">
    kc_match = re.search(r'<meta\s+name="kc-tags"\s+content="([^"]*)"', content)
    kc_tags = []
    if kc_match:
        kc_tags = [t.strip() for t in kc_match.group(1).split(",") if t.strip()]

    # Fallback 1: extract kcTags from window.__TEST_CONFIG__ JavaScript block
    if not kc_tags:
        js_kc_match = re.search(
            r'window\.__TEST_CONFIG__\s*=\s*\{[^}]*?kcTags\s*:\s*\[([^\]]*)\]',
            content, re.DOTALL
        )
        if js_kc_match:
            raw_tags = js_kc_match.group(1)
            kc_tags = [
                t.strip().strip('"').strip("'")
                for t in raw_tags.split(",")
                if t.strip().strip('"').strip("'")
            ]

    # Fallback 2: extract kcTags from window.__KC_TAGS__ = [...] (diagnostic template)
    if not kc_tags:
        js_kc_match2 = re.search(
            r'window\.__KC_TAGS__\s*=\s*\[([^\]]*)\]',
            content
        )
        if js_kc_match2:
            raw_tags = js_kc_match2.group(1)
            kc_tags = [
                t.strip().strip('"').strip("'")
                for t in raw_tags.split(",")
                if t.strip().strip('"').strip("'")
            ]

    # Infer skill from KC tags or filename
    skill = "general"
    if kc_tags:
        for tag in kc_tags:
            if tag.startswith("kc-read"):
                skill = "reading"; break
            elif tag.startswith("kc-listen"):
                skill = "listening"; break
            elif tag.startswith("kc-write"):
                skill = "writing"; break
            elif tag.startswith("kc-speak"):
                skill = "speaking"; break
    else:
        # Infer from filename
        name_lower = filepath.stem.lower()
        if "writing" in name_lower:
            skill = "writing"
        elif "listening" in name_lower:
            skill = "listening"
        elif "speaking" in name_lower:
            skill = "speaking"
        elif "reading" in name_lower:
            skill = "reading"
        elif "diagnostic" in name_lower:
            skill = "general"
        elif "dashboard" in name_lower:
            skill = "general"

    # Extract creation date from filename pattern: *-YYYYMMDD-*.html
    date_match = re.search(r"(\d{4})(\d{2})(\d{2})", filepath.stem)
    if date_match:
        created_at = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}T12:00:00Z"
    else:
        # Fall back to file modification time
        from datetime import timezone
        mtime = filepath.stat().st_mtime
        created_at = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lesson_id = filepath.stem

    return {
        "id": lesson_id,
        "title": title,
        "kcTags": kc_tags,
        "skill": skill,
        "file": str(filepath.relative_to(PROJECT_ROOT)),
        "createdAt": created_at,
        "source": "generated",
        "timesUsed": 0,
        "lastUsed": None
    }


# ── Commands ───────────────────────────────────────────────────────

def _build_fresh_profile(kc_graph: dict | None, target_band: float = 0, exam_date: str | None = None) -> dict:
    """Build a fresh student-profile.json v2.0.0 from a KC graph.

    Used by both cmd_migrate_profile (full migration path) and
    cmd_reset_profile. Returns a complete profile dict with all KCs
    at default state (weak, 0 attempts).
    """
    learner = {
        "targetBand": target_band,
        "examDate": exam_date,
        "activeSkills": ["listening", "reading", "writing", "speaking"],
        "startedAt": _now(),
        "lastSessionAt": _now(),
        "sessionsCompleted": 0,
        "diagnosticCompleted": False
    }

    skills = {}
    for skill_name in ["listening", "reading", "writing", "speaking"]:
        skills[skill_name] = {
            "currentBand": 0,
            "bandHistory": [],
            "practiceCount": 0,
            "lastPracticeDate": None,
            "kcMastery": {}
        }

    # Populate kcMastery from KC graph
    if kc_graph:
        for skill_name in ["listening", "reading", "writing", "speaking"]:
            skill_kcs = kc_graph.get("skills", {}).get(skill_name, {}).get("kcs", [])
            for kc in skill_kcs:
                skills[skill_name]["kcMastery"][kc["id"]] = {
                    "level": "weak",
                    "errorRate": 0.0,
                    "attempts": 0,
                    "lastTested": None,
                    "nextReviewDate": None
                }

    profile = {
        "version": "2.0.0",
        "learner": learner,
        "skills": skills,
        "vocabulary": {
            "misspelledWords": [],
            "weakTopics": [],
            "lastVocabReview": None
        },
        "grammar": {
            "weakPoints": []
        },
        "testHistory": [],
        "crossSkillPatterns": [],
        "coachNotes": [
            {
                "date": _now(),
                "category": "system",
                "skill": "general",
                "content": "Fresh profile created via reset.",
                "priority": "low"
            }
        ]
    }

    return profile


def cmd_init():
    """Initialize .ielts/ directory structure."""
    dirs = [
        IELTS_DIR,
        BACKUP_DIR,
        ARCHIVE_DIR,
        IELTS_DIR / "lesson-plans",
        IELTS_DIR / "listening",
        IELTS_DIR / "reading",
        IELTS_DIR / "writing",
        IELTS_DIR / "speaking",
        IELTS_DIR / "listening" / "archive",
        IELTS_DIR / "reading" / "archive",
        IELTS_DIR / "writing" / "archive",
        IELTS_DIR / "speaking" / "archive",
    ]
    for d in dirs:
        _ensure_dir(d)

    # Create settings.json if missing
    if not SETTINGS_FILE.exists():
        _save_json(SETTINGS_FILE, {
            "language": "vi",
            "availableLanguages": ["vi", "en", "zh"],
            "teacherName": "Claude",
            "teacherPersonality": "encouraging"
        })

    # Create roadmap.json if missing (minimal starting state)
    if not ROADMAP_FILE.exists():
        _save_json(ROADMAP_FILE, {
            "version": "1.0.0",
            "learner": {
                "targetBand": 0,
                "examDate": None,
                "activeSkills": ["listening", "reading", "writing", "speaking"],
                "startedAt": _now(),
                "lastSessionAt": _now()
            },
            "skills": {
                "listening": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None},
                "reading": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None},
                "writing": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None},
                "speaking": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None}
            },
            "history": [],
            "crossSkillPatterns": [],
            "coachNotes": []
        })

    # Create lesson-library.json if missing (separate from student profile —
    # survives profile resets, protects the self-reinforcing learning loop)
    if not LESSON_LIBRARY_FILE.exists():
        _save_json(LESSON_LIBRARY_FILE, {
            "version": "1.0.0",
            "totalLessons": 0,
            "lessons": []
        })

    print(json.dumps({"status": "ok", "message": "IELTS data directory initialized", "path": str(IELTS_DIR)}))
    return 0


def cmd_migrate_profile():
    """Migrate old roadmap.json → new student-profile.json.

    If student-profile.json already exists: only ADD new KCs from KC graph
    without overwriting existing mastery data. Preserves all test history,
    lesson library, vocabulary, grammar, and coach notes.

    If student-profile.json does not exist: full migration from roadmap.json.

    Creates backup before modifying.
    """
    if not ROADMAP_FILE.exists():
        print(json.dumps({"status": "error", "message": f"{ROADMAP_FILE} not found. Run init first."}))
        return 1

    old = _load_json(ROADMAP_FILE)
    if not old:
        print(json.dumps({"status": "error", "message": "roadmap.json is empty or corrupt."}))
        return 1

    kc_graph = _load_json(KC_GRAPH_FILE)

    # ── Incremental mode: profile exists, only sync new KCs ──
    if PROFILE_FILE.exists():
        profile = _load_json(PROFILE_FILE)
        if not profile:
            print(json.dumps({"status": "error", "message": "student-profile.json is corrupt."}))
            return 1

        _backup_file(PROFILE_FILE)
        kcs_added = 0

        for skill_name in ["listening", "reading", "writing", "speaking"]:
            skill_kcs = kc_graph.get("skills", {}).get(skill_name, {}).get("kcs", []) if kc_graph else []
            if skill_name not in profile["skills"]:
                profile["skills"][skill_name] = {"currentBand": 0, "bandHistory": [], "practiceCount": 0, "lastPracticeDate": None, "kcMastery": {}}
            if "kcMastery" not in profile["skills"][skill_name]:
                profile["skills"][skill_name]["kcMastery"] = {}

            mastery = profile["skills"][skill_name]["kcMastery"]
            for kc in skill_kcs:
                if kc["id"] not in mastery:
                    mastery[kc["id"]] = {
                        "level": "weak",
                        "errorRate": 0.0,
                        "attempts": 0,
                        "lastTested": None,
                        "nextReviewDate": None
                    }
                    kcs_added += 1

        _save_json(PROFILE_FILE, profile)

        result = {
            "status": "ok",
            "message": f"Incremental sync: {kcs_added} new KCs added",
            "mode": "incremental",
            "profile": str(PROFILE_FILE),
            "summary": {
                "kcsAdded": kcs_added,
                "totalKCs": sum(len(profile["skills"][s].get("kcMastery", {})) for s in profile["skills"]),
                "testHistoryPreserved": len(profile.get("testHistory", [])),
                "diagnosticPreserved": profile["learner"].get("diagnosticCompleted", False)
            }
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # ── Full migration mode: no profile exists yet ──
    backup_path = _backup_file(ROADMAP_FILE)

    # ── Build new student profile ──────────────────────────────────
    old_learner = old.get("learner", {})
    old_skills = old.get("skills", {})
    old_coach = old.get("coachNotes", [])

    # Map learner section
    learner = {
        "targetBand": old_learner.get("targetBand", 0),
        "examDate": old_learner.get("examDate"),
        "activeSkills": old_learner.get("activeSkills", ["listening", "reading", "writing", "speaking"]),
        "startedAt": old_learner.get("startedAt", _now()),
        "lastSessionAt": old_learner.get("lastSessionAt", _now()),
        "sessionsCompleted": len(old.get("history", [])),
        "diagnosticCompleted": False
    }

    # Map each skill
    skills = {}
    for skill_name in ["listening", "reading", "writing", "speaking"]:
        old_skill = old_skills.get(skill_name, {})
        skills[skill_name] = {
            "currentBand": old_skill.get("currentBand", 0),
            "bandHistory": old_skill.get("bandHistory", []),
            "practiceCount": old_skill.get("practiceCount", 0),
            "lastPracticeDate": old_skill.get("lastPracticeDate"),
            "kcMastery": {}  # no old data — starts empty
        }

    # Convert old weakAreas → coachNotes
    weak_area_notes = []
    for skill_name, skill_data in old_skills.items():
        for area in skill_data.get("weakAreas", []):
            weak_area_notes.append({
                "date": _now(),
                "category": "observation",
                "skill": skill_name,
                "content": f"[Migrated from roadmap.json] Previously identified weak area: {area}",
                "priority": "medium"
            })

    # Map old coachNotes + add migration entry
    migration_note = {
        "date": _now(),
        "category": "system",
        "skill": "general",
        "content": f"Migrated from roadmap.json v{old.get('version', '1.0.0')} to student-profile.json v2.0.0. Backup: {backup_path.name if backup_path else 'none'}",
        "priority": "low"
    }
    coach_notes = [migration_note] + old_coach + weak_area_notes

    # Build new profile
    profile = {
        "version": "2.0.0",
        "learner": learner,
        "skills": skills,
        "vocabulary": {
            "misspelledWords": [],
            "weakTopics": [],
            "lastVocabReview": None
        },
        "grammar": {
            "weakPoints": []
        },
        "lessonLibrary": {
            "totalLessons": 0,
            "lessons": []
        },
        "testHistory": [],
        "crossSkillPatterns": [],
        "coachNotes": coach_notes
    }

    # Load KC graph for initial kcMastery population
    kc_graph = _load_json(KC_GRAPH_FILE)
    if kc_graph:
        for skill_name in ["listening", "reading", "writing", "speaking"]:
            skill_kcs = kc_graph.get("skills", {}).get(skill_name, {}).get("kcs", [])
            for kc in skill_kcs:
                skills[skill_name]["kcMastery"][kc["id"]] = {
                    "level": "weak",        # default — no data yet
                    "errorRate": 0.0,
                    "attempts": 0,
                    "lastTested": None,
                    "nextReviewDate": None  # for spaced repetition
                }

    # Write new profile
    _save_json(PROFILE_FILE, profile)

    result = {
        "status": "ok",
        "message": "Migration complete",
        "backup": str(backup_path) if backup_path else None,
        "profile": str(PROFILE_FILE),
        "summary": {
            "targetBand": learner["targetBand"],
            "sessionsCompleted": learner["sessionsCompleted"],
            "kcMasteryEntries": sum(len(skills[s]["kcMastery"]) for s in skills),
            "coachNotesMigrated": len(old_coach),
            "weakAreasConverted": len(weak_area_notes)
        }
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_settings_get():
    """Read and output settings.json."""
    settings = _load_json(SETTINGS_FILE, {
        "language": "vi",
        "availableLanguages": ["vi", "en", "zh"],
        "teacherName": "Claude",
        "teacherPersonality": "encouraging"
    })
    print(json.dumps(settings, ensure_ascii=False, indent=2))
    return 0


def cmd_settings_set(args):
    """Update settings fields."""
    settings = _load_json(SETTINGS_FILE, {
        "language": "vi",
        "availableLanguages": ["vi", "en", "zh"],
        "teacherName": "Claude",
        "teacherPersonality": "encouraging"
    })

    settable = ["language", "teacherName", "teacherPersonality"]
    updated = False

    for key in settable:
        val = getattr(args, key, None)
        if val is not None:
            if key == "language" and val not in settings.get("availableLanguages", []):
                print(json.dumps({"status": "error", "message": f"Language '{val}' not available. Options: {settings.get('availableLanguages')}"}))
                return 1
            settings[key] = val
            updated = True

    if updated:
        _save_json(SETTINGS_FILE, settings)

    print(json.dumps({"status": "ok", "settings": settings}, ensure_ascii=False))
    return 0


def cmd_validate():
    """Validate data integrity: profile schema, KC cross-references, errorRate formula."""
    errors = []
    warnings = []

    profile = _load_json(PROFILE_FILE)
    kc_graph = _load_json(KC_GRAPH_FILE)

    # ── Profile existence ──
    if not profile:
        errors.append("student-profile.json not found. Run migrate-profile first.")
    else:
        # Required top-level fields (lessonLibrary moved to standalone lesson-library.json)
        for field in ["version", "learner", "skills", "vocabulary", "grammar", "testHistory", "coachNotes"]:
            if field not in profile:
                errors.append(f"student-profile.json missing field: {field}")

        # Learner fields
        learner = profile.get("learner", {})
        for field in ["targetBand", "activeSkills", "startedAt"]:
            if field not in learner:
                errors.append(f"learner missing: {field}")

        # Skill consistency
        for skill_name in ["listening", "reading", "writing", "speaking"]:
            if skill_name not in profile.get("skills", {}):
                errors.append(f"skills missing: {skill_name}")
                continue
            skill = profile["skills"][skill_name]
            for field in ["currentBand", "bandHistory", "practiceCount", "kcMastery"]:
                if field not in skill:
                    errors.append(f"skills.{skill_name} missing: {field}")

    # ── KC graph integrity ──
    if not kc_graph:
        warnings.append("kc-graph-ielts.json not found. KC cross-reference check skipped.")
    elif profile:
        all_kc_ids = set()
        for skill_name, skill_data in kc_graph.get("skills", {}).items():
            for kc in skill_data.get("kcs", []):
                all_kc_ids.add(kc["id"])

        # Check kcMastery tags exist in KC graph
        for skill_name, skill_data in profile.get("skills", {}).items():
            for kc_id in skill_data.get("kcMastery", {}):
                if kc_id not in all_kc_ids:
                    errors.append(f"Orphaned KC tag in kcMastery: '{kc_id}' not found in KC graph")

        # Check level = derived from errorRate
        for skill_name, skill_data in profile.get("skills", {}).items():
            for kc_id, kc_data in skill_data.get("kcMastery", {}).items():
                error_rate = kc_data.get("errorRate", 0)
                stored_level = kc_data.get("level", "")
                if error_rate >= 0.40 and stored_level != "weak":
                    errors.append(f"skills.{skill_name}.kcMastery.{kc_id}: errorRate={error_rate} should derive to 'weak', got '{stored_level}'")
                elif 0.15 <= error_rate < 0.40 and stored_level != "ok":
                    errors.append(f"skills.{skill_name}.kcMastery.{kc_id}: errorRate={error_rate} should derive to 'ok', got '{stored_level}'")
                elif error_rate < 0.15 and stored_level != "mastered" and error_rate > 0:
                    errors.append(f"skills.{skill_name}.kcMastery.{kc_id}: errorRate={error_rate} should derive to 'mastered', got '{stored_level}'")

    result = {
        "status": "ok" if not errors else "issues_found",
        "errors": errors,
        "warnings": warnings
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def cmd_reset_profile(args):
    """Reset student-profile.json to factory-fresh state.

    Backs up current profile (if exists), then writes a fresh v2.0.0
    profile with all KCs at default state. Cleans up legacy auxiliary
    files and transient test results. Does NOT touch lesson-library.json
    or lesson-plans/ — the teaching library survives resets.

    Requires --yes flag to confirm (one-way door — data cannot be
    recovered except from backup).
    """
    if not getattr(args, 'yes', False):
        print(json.dumps({
            "status": "blocked",
            "message": "Reset requires --yes flag. This is a one-way operation. "
                       "Your current profile will be backed up to .ielts/backup/."
        }, ensure_ascii=False))
        return 1

    kc_graph = _load_json(KC_GRAPH_FILE)
    if not kc_graph:
        print(json.dumps({
            "status": "error",
            "message": f"{KC_GRAPH_FILE} not found. Cannot build fresh profile without KC graph."
        }, ensure_ascii=False))
        return 1

    # ── Backup current profile ──
    backup_path = None
    if PROFILE_FILE.exists():
        backup_path = _backup_file(PROFILE_FILE)
        old_profile = _load_json(PROFILE_FILE)
        old_target = (old_profile or {}).get("learner", {}).get("targetBand", 0)
        old_exam = (old_profile or {}).get("learner", {}).get("examDate")
    else:
        old_target = 0
        old_exam = None

    # Preserve target band and exam date from args or old profile
    target_band = getattr(args, 'target_band', None)
    if target_band is None:
        target_band = old_target
    exam_date = getattr(args, 'exam_date', None)
    if exam_date is None:
        exam_date = old_exam

    # ── Build and save fresh profile ──
    profile = _build_fresh_profile(kc_graph, target_band, exam_date)

    # Add reset note to coach notes
    profile["coachNotes"].insert(0, {
        "date": _now(),
        "category": "system",
        "skill": "general",
        "content": f"Profile reset. Backup: {backup_path.name if backup_path else 'none'}",
        "priority": "high"
    })

    _save_json(PROFILE_FILE, profile)

    # ── Cleanup legacy files ──
    legacy_files = [
        IELTS_DIR / "roadmap.json",
        IELTS_DIR / "config.json",
        IELTS_DIR / "progress.json",
        IELTS_DIR / "memories.json",
        IELTS_DIR / "errors.json",
        IELTS_DIR / "vocab.json",
        IELTS_DIR / "synonyms.json",
    ]
    cleaned_legacy = []
    for fp in legacy_files:
        if fp.exists():
            try:
                fp.unlink()
                cleaned_legacy.append(fp.name)
            except OSError:
                pass

    # ── Clear transient latest.json files ──
    transient_skills = ["listening", "reading", "writing", "speaking"]
    cleaned_transient = []
    for skill in transient_skills:
        skill_dir = IELTS_DIR / skill
        if not skill_dir.exists():
            continue
        # Clear latest.json
        latest = skill_dir / "latest.json"
        if latest.exists():
            try:
                latest.unlink()
                cleaned_transient.append(f"{skill}/latest.json")
            except OSError:
                pass
        # Clear latest.webm (speaking)
        latest_webm = skill_dir / "latest.webm"
        if latest_webm.exists():
            try:
                latest_webm.unlink()
                cleaned_transient.append(f"{skill}/latest.webm")
            except OSError:
                pass
        # Clear archive directory
        archive_dir = skill_dir / "archive"
        if archive_dir.exists():
            try:
                for af in archive_dir.iterdir():
                    if af.is_file():
                        af.unlink()
                cleaned_transient.append(f"{skill}/archive/*")
            except OSError:
                pass

    # ── Report ──
    total_kcs = sum(len(profile["skills"][s]["kcMastery"]) for s in profile["skills"])
    result = {
        "status": "ok",
        "message": "Profile reset complete. Diagnostic will run on next session.",
        "backup": str(backup_path) if backup_path else None,
        "profile": str(PROFILE_FILE),
        "summary": {
            "targetBand": target_band,
            "diagnosticCompleted": False,
            "totalKCs": total_kcs,
            "lessonLibraryPreserved": LESSON_LIBRARY_FILE.exists(),
            "cleanedLegacy": cleaned_legacy,
            "cleanedTransient": cleaned_transient
        }
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backup():
    """Create a zip backup of .ielts/."""
    output = PROJECT_ROOT / f"ielts-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(IELTS_DIR):
            for f in files:
                fp = Path(root) / f
                arcname = fp.relative_to(IELTS_DIR.parent)
                zf.write(fp, arcname)

    print(json.dumps({"status": "ok", "path": str(output), "size": output.stat().st_size}))
    return 0


# ── Lesson Library Commands ─────────────────────────────────────────

def cmd_lesson_library_list():
    """List all lessons in the library."""
    lib = _load_json(LESSON_LIBRARY_FILE)
    if not lib:
        print(json.dumps({"status": "ok", "totalLessons": 0, "lessons": []}))
        return 0

    # Verify each lesson's HTML file still exists
    available = []
    missing = []
    for lesson in lib.get("lessons", []):
        fp = PROJECT_ROOT / lesson["file"]
        if fp.exists():
            available.append(lesson)
        else:
            missing.append(lesson["id"])

    result = {
        "status": "ok",
        "totalLessons": len(available),
        "lessons": available
    }
    if missing:
        result["warnings"] = [f"File missing for: {', '.join(missing)}"]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_lesson_library_add(args):
    """Add a lesson entry to the library."""
    lib = _load_json(LESSON_LIBRARY_FILE, {"version": "1.0.0", "totalLessons": 0, "lessons": []})

    # Parse KC tags
    kc_tags = []
    if args.kc_tags:
        kc_tags = [t.strip() for t in args.kc_tags.split(",")]

    lesson = {
        "id": args.id,
        "title": args.title,
        "kcTags": kc_tags,
        "skill": args.skill,
        "file": args.file,
        "createdAt": args.date if args.date else _now(),
        "source": args.source if args.source else "generated",
        "timesUsed": 0,
        "lastUsed": None
    }

    # Add triggerError if provided
    if hasattr(args, 'trigger_error') and args.trigger_error:
        lesson["triggerError"] = args.trigger_error

    # Check for duplicates
    existing_ids = {l["id"] for l in lib["lessons"]}
    if lesson["id"] in existing_ids:
        # Update existing entry
        for i, l in enumerate(lib["lessons"]):
            if l["id"] == lesson["id"]:
                lib["lessons"][i] = lesson
                break
        action = "updated"
    else:
        lib["lessons"].append(lesson)
        action = "added"

    lib["totalLessons"] = len(lib["lessons"])
    _save_json(LESSON_LIBRARY_FILE, lib)

    print(json.dumps({"status": "ok", "action": action, "id": lesson["id"], "totalLessons": lib["totalLessons"]}, ensure_ascii=False))
    return 0


def cmd_lesson_library_mark_used(args):
    """Increment timesUsed for a lesson."""
    lib = _load_json(LESSON_LIBRARY_FILE)
    if not lib:
        print(json.dumps({"status": "error", "message": "lesson-library.json not found. Run init first."}))
        return 1

    for lesson in lib["lessons"]:
        if lesson["id"] == args.id:
            lesson["timesUsed"] = lesson.get("timesUsed", 0) + 1
            lesson["lastUsed"] = _today()
            _save_json(LESSON_LIBRARY_FILE, lib)
            print(json.dumps({"status": "ok", "id": args.id, "timesUsed": lesson["timesUsed"], "lastUsed": lesson["lastUsed"]}, ensure_ascii=False))
            return 0

    print(json.dumps({"status": "error", "message": f"Lesson '{args.id}' not found in library."}))
    return 1


def cmd_lesson_library_sync():
    """Scan .ielts/lesson-plans/ and rebuild lesson-library.json.

    Preserves usage stats (timesUsed, lastUsed) for existing lessons.
    Adds new lessons found on disk. Warns about lessons in the library
    whose HTML files no longer exist.
    """
    lib = _load_json(LESSON_LIBRARY_FILE, {"version": "1.0.0", "totalLessons": 0, "lessons": []})

    # Build lookup of existing lessons by id
    existing = {}
    for l in lib["lessons"]:
        existing[l["id"]] = l

    # Scan disk
    new_lessons = []
    disk_ids = set()

    if LESSON_PLANS_DIR.exists():
        for fp in sorted(LESSON_PLANS_DIR.glob("*.html")):
            meta = _scan_lesson_html(fp)
            if meta is None:
                continue

            disk_ids.add(meta["id"])

            if meta["id"] in existing:
                # Preserve usage stats
                old = existing[meta["id"]]
                meta["timesUsed"] = old.get("timesUsed", 0)
                meta["lastUsed"] = old.get("lastUsed")
                # Update KC tags if newly discovered
                if not meta["kcTags"] and old.get("kcTags"):
                    meta["kcTags"] = old["kcTags"]
                if meta["skill"] == "general" and old.get("skill", "general") != "general":
                    meta["skill"] = old["skill"]
            else:
                # New lesson found on disk
                pass

            new_lessons.append(meta)
    else:
        _ensure_dir(LESSON_PLANS_DIR)

    # Check for orphaned entries (in library but file missing)
    orphaned = set(existing.keys()) - disk_ids
    warnings = []
    if orphaned:
        warnings.append(f"Orphaned entries (file missing): {', '.join(sorted(orphaned))}")

    lib["lessons"] = new_lessons
    lib["totalLessons"] = len(new_lessons)
    _save_json(LESSON_LIBRARY_FILE, lib)

    result = {
        "status": "ok",
        "totalLessons": lib["totalLessons"],
        "added": len(disk_ids - set(existing.keys())),
        "preserved": len(disk_ids & set(existing.keys())),
        "orphaned": len(orphaned)
    }
    if warnings:
        result["warnings"] = warnings

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_migrate_lesson_library():
    """One-time migration: extract lessonLibrary from student-profile.json
    and write to standalone lesson-library.json. Removes lessonLibrary
    from student-profile.json after successful migration.
    """
    profile = _load_json(PROFILE_FILE)
    if not profile:
        print(json.dumps({"status": "error", "message": "student-profile.json not found."}))
        return 1

    old_library = profile.get("lessonLibrary")
    if old_library is None:
        print(json.dumps({"status": "ok", "message": "No lessonLibrary in student-profile.json. Nothing to migrate."}))
        return 0

    # Backup both files
    _backup_file(PROFILE_FILE)
    if LESSON_LIBRARY_FILE.exists():
        _backup_file(LESSON_LIBRARY_FILE)

    # Write standalone lesson library
    lib = {
        "version": "1.0.0",
        "totalLessons": old_library.get("totalLessons", len(old_library.get("lessons", []))),
        "lessons": old_library.get("lessons", [])
    }
    _save_json(LESSON_LIBRARY_FILE, lib)

    # Remove lessonLibrary from profile
    del profile["lessonLibrary"]
    _save_json(PROFILE_FILE, profile)

    # Now sync from disk to find any orphaned lessons
    sync_result = json.loads(json.dumps({"status": "ok"}))  # placeholder
    # Run sync to pick up lessons on disk that weren't tracked
    if LESSON_PLANS_DIR.exists():
        disk_count = len(list(LESSON_PLANS_DIR.glob("*.html")))
    else:
        disk_count = 0

    print(json.dumps({
        "status": "ok",
        "message": "Lesson library migrated to standalone file",
        "migrated": lib["totalLessons"],
        "filesOnDisk": disk_count,
        "note": "Run 'lesson-library sync' to scan disk for orphaned lessons"
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_create_full_test(args):
    """Generate a full mock test HTML with 4 skills in tabs.

    Usage:
      .venv/bin/python3 shared/ielts_cli.py create-full-test --random
      .venv/bin/python3 shared/ielts_cli.py create-full-test --random --seed 42
    """
    import sys as _sys
    _sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import (
        select_random_sections, render_full_test, full_test_output_path, write_html
    )

    try:
        print("Selecting random sections for full mock test...")
        selected = select_random_sections(seed=args.seed)

        print("Selected sections:")
        for skill, sec in selected.items():
            print(f"  {skill}: {sec.get('textbook', '?')} test-{sec.get('testNumber', '?')} "
                  f"section-{sec.get('sectionNumber', '?')} — {sec.get('title', sec.get('path', '?'))}")

        html = render_full_test(selected)
        out = full_test_output_path(selected)
        write_html(out, html, force=args.force)

        print(f"\nOK  {out}")
        print(f"    Skills: reading + listening + speaking + writing")
        print(f"    Open:  open http://localhost:8765/test-html/{out.name}")
        print(f"    (Ensure server is running: lsof -i :8765 | grep LISTEN || .venv/bin/python3 skills/ielts-teacher/server.py &)")
        print()
        print("After completing all 4 sections, return to Claude and say: chấm bài full test")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def cmd_memory_add(args):
    """Append a coach note to student-profile.json.

    Referenced by all SKILL.md files and evaluation phase docs as:
      .venv/bin/python3 shared/ielts_cli.py memory add \\
        --content "..." --category observation --skill writing --priority high
    """
    profile = _load_json(PROFILE_FILE)
    if not profile:
        print(json.dumps({"status": "error", "message": "student-profile.json not found. Run migrate-profile first."}))
        return 1

    valid_categories = ["system", "observation", "weakness", "strength", "strategy"]
    valid_skills = ["general", "listening", "reading", "writing", "speaking"]
    valid_priorities = ["high", "medium", "low"]

    category = args.category if args.category in valid_categories else "observation"
    skill = args.skill if args.skill in valid_skills else "general"
    priority = args.priority if args.priority in valid_priorities else "medium"

    note = {
        "date": _now(),
        "category": category,
        "skill": skill,
        "content": args.content,
        "priority": priority
    }

    if "coachNotes" not in profile:
        profile["coachNotes"] = []

    profile["coachNotes"].append(note)
    _save_json(PROFILE_FILE, profile)

    print(json.dumps({
        "status": "ok",
        "action": "added",
        "category": category,
        "skill": skill,
        "priority": priority,
        "totalNotes": len(profile["coachNotes"])
    }, ensure_ascii=False))
    return 0


# ── Vocabulary Commands ────────────────────────────────────────────

def cmd_vocab_add(args):
    """Add or update a word in vocabulary.words with SRS tracking.

    Usage:
      .venv/bin/python3 shared/ielts_cli.py vocab add \\
        --word "accomodation" --correct "accommodation" \\
        --source listening --context "Q1 — booking form"
    """
    profile = _load_json(PROFILE_FILE)
    if not profile:
        print(json.dumps({"status": "error", "message": "student-profile.json not found."}))
        return 1

    vocab = profile.setdefault("vocabulary", {})
    words = vocab.setdefault("words", {})

    word_key = args.word.lower().strip()

    if word_key in words:
        entry = words[word_key]
        entry["errorCount"] = entry.get("errorCount", 0) + 1
        entry["lastSeen"] = _now()
        entry["attempts"] = 1
        entry["nextReviewDate"] = _tomorrow()
        entry["level"] = "new"
        if args.correct:
            entry["correct"] = args.correct
        if args.source:
            entry["source"] = args.source
        if args.context:
            entry["context"] = args.context
        action = "updated"
    else:
        words[word_key] = {
            "correct": args.correct or word_key,
            "attempts": 0,
            "errorCount": 1,
            "lastSeen": _now(),
            "nextReviewDate": _tomorrow(),
            "source": args.source or "unknown",
            "context": args.context or "",
            "level": "new"
        }
        action = "added"

    _save_json(PROFILE_FILE, profile)

    print(json.dumps({
        "status": "ok",
        "action": action,
        "word": word_key,
        "correct": words[word_key]["correct"],
        "totalWords": len(words)
    }, ensure_ascii=False))
    return 0


def cmd_vocab_review(args):
    """Update SRS data for a reviewed word.

    Usage:
      .venv/bin/python3 shared/ielts_cli.py vocab review \\
        --word "accomodation" --passed true
    """
    profile = _load_json(PROFILE_FILE)
    if not profile:
        print(json.dumps({"status": "error", "message": "student-profile.json not found."}))
        return 1

    words = profile.get("vocabulary", {}).get("words", {})
    word_key = args.word.lower().strip()

    if word_key not in words:
        print(json.dumps({"status": "error", "message": f"Word '{word_key}' not found in vocabulary."}))
        return 1

    entry = words[word_key]
    passed = getattr(args, 'passed', True)

    if passed:
        entry["attempts"] = entry.get("attempts", 0) + 1
        attempts = entry["attempts"]
        if attempts >= 4:
            entry["nextReviewDate"] = _days_from_now(30)
            entry["level"] = "mastered"
        elif attempts == 3:
            entry["nextReviewDate"] = _days_from_now(7)
            entry["level"] = "learning"
        elif attempts == 2:
            entry["nextReviewDate"] = _days_from_now(3)
            entry["level"] = "learning"
        else:
            entry["nextReviewDate"] = _days_from_now(1)
            entry["level"] = "new"
    else:
        entry["attempts"] = 1
        entry["errorCount"] = entry.get("errorCount", 0) + 1
        entry["nextReviewDate"] = _tomorrow()
        entry["level"] = "new"

    entry["lastSeen"] = _now()
    _save_json(PROFILE_FILE, profile)

    # Update lastVocabReview
    vocab = profile.setdefault("vocabulary", {})
    vocab["lastVocabReview"] = _now()
    _save_json(PROFILE_FILE, profile)

    print(json.dumps({
        "status": "ok",
        "word": word_key,
        "attempts": entry["attempts"],
        "level": entry["level"],
        "nextReviewDate": entry["nextReviewDate"],
        "passed": passed
    }, ensure_ascii=False))
    return 0


def cmd_synonym_add(args):
    """Add a synonym pair to the synonym library.

    Usage:
      .venv/bin/python3 shared/ielts_cli.py synonym add \\
        --word "important" --synonym "crucial" --context "Reading Passage 1"
    """
    _ensure_dir(VOCAB_DIR)
    data = _load_json(SYNONYMS_FILE, {"version": "1.0.0", "synonyms": []})

    pair = {
        "word": args.word.strip().lower(),
        "synonym": args.synonym.strip().lower(),
        "context": args.context or "",
        "addedAt": _now()
    }

    # Avoid exact duplicates
    existing = [s for s in data["synonyms"]
                if s["word"] == pair["word"] and s["synonym"] == pair["synonym"]]
    if existing:
        print(json.dumps({"status": "ok", "action": "skipped", "reason": "duplicate",
                          "word": pair["word"], "synonym": pair["synonym"]}, ensure_ascii=False))
        return 0

    data["synonyms"].append(pair)
    _save_json(SYNONYMS_FILE, data)

    print(json.dumps({
        "status": "ok",
        "action": "added",
        "word": pair["word"],
        "synonym": pair["synonym"],
        "totalSynonyms": len(data["synonyms"])
    }, ensure_ascii=False))
    return 0


def cmd_status():
    """Output a brief status summary."""
    profile = _load_json(PROFILE_FILE)
    settings = _load_json(SETTINGS_FILE)

    if not profile:
        print("IELTS: run 'migrate-profile' to set up")
        return 0

    learner = profile.get("learner", {})
    skills = profile.get("skills", {})
    lang = (settings or {}).get("language", "vi")

    parts = []
    target = learner.get("targetBand", 0)
    if target:
        parts.append(f"🎯 {target}")

    for s in ["reading", "listening", "speaking", "writing"]:
        band = skills.get(s, {}).get("currentBand", 0)
        if band:
            parts.append(f"{s[0].upper()}:{band}")

    sessions = learner.get("sessionsCompleted", 0)
    if sessions:
        parts.append(f"📚 {sessions} sessions")

    lesson_lib = _load_json(LESSON_LIBRARY_FILE)
    lesson_count = (lesson_lib or {}).get("totalLessons", 0) if lesson_lib else 0
    if lesson_count:
        parts.append(f"📝 {lesson_count} lessons")

    print("IELTS " + " · ".join(parts) if parts else "IELTS: ready")
    return 0


# ── Quality Commands (W1 thin-slice) ──────────────────────────────

def cmd_quality_init():
    """Initialize quality control plane scaffold under .ielts/quality."""
    dirs = [
        QUALITY_DIR,
        QUALITY_CONFIG_DIR,
        QUALITY_RUNS_DIR,
        QUALITY_TRACES_DIR,
        QUALITY_EVALS_DIR,
        QUALITY_EVAL_REGISTRY_DIR,
        QUALITY_GATES_DIR,
        QUALITY_GATE_CHECKPOINTS_DIR,
        QUALITY_INCIDENTS_DIR,
        QUALITY_GATE_REHEARSALS_DIR,
        QUALITY_GATE_PROMOTIONS_DIR,
        QUALITY_OVERRIDES_DIR,
        QUALITY_RECOMMENDATIONS_DIR,
        QUALITY_RUNBOOKS_DIR,
        QUALITY_BASELINES_DIR,
        QUALITY_SHADOW_DIR,
        QUALITY_SHADOW_WEEKLY_DIR,
        QUALITY_WEEKLY_REVIEWS_DIR,
    ]
    for d in dirs:
        _ensure_dir(d)

    if not THRESHOLDS_READING_V1_FILE.exists():
        THRESHOLDS_READING_V1_FILE.write_text(
            """version: v1\nlane: reading\nowner: founder\nmetrics:\n  replay_pass_rate:\n    min: 0.75\n  trace_completeness:\n    min: 0.80\n  content_fidelity_error_rate:\n    max: 0.05\n  min_sample_size:\n    value: 40\n""",
            encoding="utf-8",
        )

    if not TRACE_SCHEMA_V1_FILE.exists():
        schema = {
            "schemaVersion": "trace-v1",
            "requiredFields": sorted(REQUIRED_TRACE_FIELDS.keys()),
            "allowedSkills": sorted(ALLOWED_SKILLS),
            "allowedDecisionTypes": sorted(ALLOWED_DECISION_TYPES),
            "confidenceRange": [0, 1],
            "notes": "Append-only field evolution. Breaking changes require schemaVersion bump.",
        }
        _save_json(TRACE_SCHEMA_V1_FILE, schema)

    if not ERROR_RESCUE_MAP_FILE.exists():
        ERROR_RESCUE_MAP_FILE.write_text(
            """# Error and Rescue Map (W1)

| Codepath | Exception Class | Rescue Action | Retry Policy | Operator Sees |
| --- | --- | --- | --- | --- |
| replay-runner | TimeoutError | mark run failed, emit recommendation | retry 1x with backoff | timeout in run report |
| replay-runner | JSONDecodeError | reject malformed output, log payload hash | none | malformed-output warning |
| gate-evaluator | ValueError (threshold parse) | block gate, fallback to report-only | none | threshold-parse-error |
| trigger-router | DuplicateRunError | dedupe by run key | none | duplicate-run-skipped |
| snapshot-loader | StaleSnapshotError | abort run, require re-run | none | stale-snapshot-warning |
""",
            encoding="utf-8",
        )

    if not HARD_GATE_ROLLBACK_PLAYBOOK_FILE.exists():
        HARD_GATE_ROLLBACK_PLAYBOOK_FILE.write_text(
            """# Hard-Gate Rollback Playbook (W4)

1. Detect blocker from hard-gate run (red/yellow state with merge blocked).
2. Confirm founder decision and incident ticket reference.
3. Switch gate mode to soft-gate.
4. Re-run report-only/soft-gate verification on same runId.
5. Publish incident note and assign remediation owner.
""",
            encoding="utf-8",
        )

    _ensure_kt_pack_files()

    if not BASELINE_TEMPLATE_FILE.exists():
        _save_json(
            BASELINE_TEMPLATE_FILE,
            {
                "version": "baseline-v1",
                "createdAt": _now(),
                "lane": "reading",
                "metrics": {
                    "traceCompleteness": None,
                    "replayPassRate": None,
                    "contentFidelityErrorRate": None,
                    "mttdHours": None,
                    "mttpHours": None,
                },
                "notes": "Fill values via quality baseline-record command.",
            },
        )

    if not COVERAGE_MATRIX_READING_V1_FILE.exists():
        COVERAGE_MATRIX_READING_V1_FILE.write_text(
            """version: v1
lane: reading
kc_buckets:
    inference:
        min_pass_rate: 0.70
        min_cases: 5
    detail:
        min_pass_rate: 0.72
        min_cases: 5
question_types:
    tfng:
        min_pass_rate: 0.70
        min_cases: 5
    matching:
        min_pass_rate: 0.70
        min_cases: 5
""",
            encoding="utf-8",
        )

    if not OVERRIDE_CONTRACT_V1_FILE.exists():
        OVERRIDE_CONTRACT_V1_FILE.write_text(
            """version: v1
required_fields:
- overrideId
- runId
- requestedBy
- approver
- severity
- justification
- ticketRef
- requestedAt
- expiresAt
- rollbackPlan
- postmortemDueAt
severity_allowed:
- yellow
- red
- emergency
""",
            encoding="utf-8",
        )

    if not SOFT_GATE_POLICY_V1_FILE.exists():
        _save_soft_gate_policy_v1("founder_approval")

    if not PERFORMANCE_BUDGET_READING_V1_FILE.exists():
        PERFORMANCE_BUDGET_READING_V1_FILE.write_text(
            """version: v1
            lane: reading
            max_cases_per_run: 60
            memory_ceiling_mb: 1024
            concurrency_limit: 4
            stage_timeouts_sec:
            setup: 60
            replay: 900
            evaluate: 300
            gate: 60
            recommendation: 60
            """,
            encoding="utf-8",
        )

    if not SHADOW_LANE_POLICY_V1_FILE.exists():
        _save_json(
            SHADOW_LANE_POLICY_V1_FILE,
            {
                "version": "shadow-lane-policy-v1",
                "lane": "writing",
                "sampleSliceRatio": 0.30,
                "minCases": 12,
                "notes": "Read-only shadow lane sampling policy.",
            },
        )

    if not SCHEMA_COMPAT_RULES_V1_FILE.exists():
        _save_json(
            SCHEMA_COMPAT_RULES_V1_FILE,
            {
                "version": "schema-compat-rules-v1",
                "artifacts": {
                "trace": {
                    "versionField": "schemaVersion",
            "currentVersion": "trace-v1",
            "allowedVersions": ["trace-v1"],
            "requiredFields": sorted(REQUIRED_TRACE_FIELDS.keys()),
        },
                    "eval": {
                    "versionField": "version",
            "currentVersion": "eval-summary-v1",
            "allowedVersions": ["eval-summary-v1"],
            "requiredFields": [
                "version",
                "runId",
                "lane",
                "recordedAt",
                "metrics",
                "checks",
            ],
        },
                    },
                },
        )

    if not GATE_MODE_CONTROL_V1_FILE.exists():
        _save_gate_mode_control_v1("soft-gate")

    if not HARD_GATE_PROMOTION_CRITERIA_V1_FILE.exists():
        _save_json(
            HARD_GATE_PROMOTION_CRITERIA_V1_FILE,
            {
                "version": "hard-gate-promotion-v1",
                "stableCyclesRequired": 3,
                "traceCompletenessMin": 0.92,
                "replayPassRateMin": 0.88,
                "contentFidelityErrorRateMax": 0.03,
                "minSampleSize": 40,
                "founderApprovalRequired": True,
            },
        )

    if not PHASE_GATES_V1_FILE.exists():
        _save_json(
            PHASE_GATES_V1_FILE,
            {
                "version": "phase-gates-v1",
                "phases": ["w1", "w2", "w3", "w4"],
                "notes": "Complete phases sequentially.",
            },
        )

    if not PHASE_GATE_STATE_FILE.exists():
        _save_phase_gate_state({"version": "phase-gate-state-v1", "completed": {}})

    if not IMMUTABILITY_LEDGER_FILE.exists():
        _save_immutability_ledger({"version": "immutability-ledger-v1", "runs": {}, "lockedPaths": {}})

    print(
        json.dumps(
            {
                "status": "ok",
                "message": "Quality scaffold initialized",
                "root": str(QUALITY_DIR),
                "created": [
                    str(THRESHOLDS_READING_V1_FILE),
                    str(TRACE_SCHEMA_V1_FILE),
                    str(ERROR_RESCUE_MAP_FILE),
                    str(HARD_GATE_ROLLBACK_PLAYBOOK_FILE),
                    str(BASELINE_TEMPLATE_FILE),
                    str(COVERAGE_MATRIX_READING_V1_FILE),
                    str(OVERRIDE_CONTRACT_V1_FILE),
                    str(SOFT_GATE_POLICY_V1_FILE),
                    str(PERFORMANCE_BUDGET_READING_V1_FILE),
                    str(SHADOW_LANE_POLICY_V1_FILE),
                    str(SCHEMA_COMPAT_RULES_V1_FILE),
                    str(GATE_MODE_CONTROL_V1_FILE),
                    str(HARD_GATE_PROMOTION_CRITERIA_V1_FILE),
                    str(PHASE_GATES_V1_FILE),
                    str(PHASE_GATE_STATE_FILE),
                    str(IMMUTABILITY_LEDGER_FILE),
                    str(KT_ONBOARDING_FILE),
                    str(KT_DECISION_LOG_TEMPLATE_FILE),
                    str(KT_PACK_MAINTENANCE_LOG_FILE),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_gateset_register(args):
    """Register an immutable gate set snapshot for a lane.

    The first write for lane+evalsetId wins; subsequent writes are rejected.
    """
    lane = _slugify(args.lane)
    evalset_id = _slugify(args.evalset_id)
    source_file = Path(args.file)

    metadata_errors = _validate_run_metadata("run-metadata", "corr-metadata", _slugify(args.source_version), lane)
    # Filter out synthetic fields; this call is used to reuse token and lane rules.
    metadata_errors = [e for e in metadata_errors if not e.startswith("runId") and not e.startswith("correlationId")]
    if metadata_errors:
        print(json.dumps({"status": "error", "errors": metadata_errors}, ensure_ascii=False, indent=2))
        return 1

    if not source_file.exists():
        print(json.dumps({"status": "error", "message": f"Gate set source file not found: {source_file}"}, ensure_ascii=False))
        return 1

    _ensure_dir(QUALITY_EVAL_REGISTRY_DIR / lane)

    records = _parse_json_or_jsonl(source_file)
    if not records:
        print(json.dumps({"status": "error", "message": "Gate set source contains no records"}, ensure_ascii=False))
        return 1

    parse_errors = []
    cases = []
    for idx, rec in enumerate(records, start=1):
        if isinstance(rec, dict) and rec.get("_parseError"):
            parse_errors.append(rec.get("_parseError"))
            continue
        if not isinstance(rec, dict):
            parse_errors.append(f"record {idx} must be a JSON object")
            continue
        case = dict(rec)
        if not case.get("caseId"):
            case["caseId"] = f"case-{idx:04d}"
        cases.append(case)

    if parse_errors:
        print(json.dumps({"status": "error", "errors": parse_errors}, ensure_ascii=False, indent=2))
        return 1

    # Immutable key is lane + evalset ID.
    immutable_key = f"{lane}:{evalset_id}"
    index_data = _load_gateset_index()
    if immutable_key in index_data.get("items", {}):
        existing = index_data["items"][immutable_key]
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Gate set already frozen and immutable",
                    "key": immutable_key,
                    "existing": existing,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    payload = {
        "version": "evalset-v1",
        "evalsetId": evalset_id,
        "lane": lane,
        "frozen": True,
        "frozenAt": _now(),
        "source": {
            "file": str(source_file),
            "sourceVersion": _slugify(args.source_version),
        },
        "caseCount": len(cases),
        "checksums": {
            "casesSha256": hashlib.sha256(
                json.dumps(cases, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "rawSourceSha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
        },
        "cases": cases,
    }

    out_path = QUALITY_EVAL_REGISTRY_DIR / lane / f"{evalset_id}.json"
    if out_path.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Gate set artifact already exists and is immutable",
                    "path": str(out_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    _save_json(out_path, payload)

    index_data.setdefault("items", {})[immutable_key] = {
        "path": str(out_path),
        "frozenAt": payload["frozenAt"],
        "caseCount": payload["caseCount"],
        "casesSha256": payload["checksums"]["casesSha256"],
        "sourceVersion": payload["source"]["sourceVersion"],
    }
    _save_gateset_index(index_data)

    print(
        json.dumps(
            {
                "status": "ok",
                "immutable": True,
                "key": immutable_key,
                "path": str(out_path),
                "caseCount": payload["caseCount"],
                "checksums": payload["checksums"],
                "warnings": [] if 40 <= payload["caseCount"] <= 50 else [
                    "Gate set bootstrap target is 40-50 cases; current caseCount is outside target range"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_run_manifest(args):
    """Create a run manifest for one quality run."""
    _ensure_dir(QUALITY_RUNS_DIR)

    run_id = _slugify(args.run_id) if args.run_id else f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    correlation_id = _slugify(args.correlation_id) if args.correlation_id else run_id
    source_version = _slugify(args.source_version)
    lane = _slugify(args.lane)

    metadata_errors = _validate_run_metadata(run_id, correlation_id, source_version, lane)
    if metadata_errors:
        print(json.dumps({"status": "error", "errors": metadata_errors}, ensure_ascii=False, indent=2))
        return 1

    index_data = _load_run_index()
    dedupe_key = _dedupe_key(args.trigger, lane, source_version, args.dedupe_key)
    existing_run_id = index_data.get("dedupe", {}).get(dedupe_key)
    if existing_run_id:
        manifest_path = QUALITY_RUNS_DIR / existing_run_id / "manifest.json"
        print(
            json.dumps(
                {
                    "status": "duplicate_skipped",
                    "runId": existing_run_id,
                    "manifest": str(manifest_path),
                    "dedupeKey": dedupe_key,
                    "message": "Duplicate trigger detected; existing run reused",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    now = _now()
    run_dir = QUALITY_RUNS_DIR / run_id
    _ensure_dir(run_dir)

    manifest = {
        "manifestVersion": "run-manifest-v1",
        "runId": run_id,
        "createdAt": now,
        "lane": lane,
        "trigger": args.trigger,
        "sourceVersion": source_version,
        "correlationId": correlation_id,
        "dedupeKey": dedupe_key,
        "artifactRoots": {
            "traces": str(QUALITY_TRACES_DIR),
            "evals": str(QUALITY_EVALS_DIR),
            "gates": str(QUALITY_GATES_DIR),
            "recommendations": str(QUALITY_RECOMMENDATIONS_DIR),
        },
        "artifacts": {},
        "status": "created",
    }

    manifest_path = run_dir / "manifest.json"
    _save_json(manifest_path, manifest)

    index_data.setdefault("dedupe", {})[dedupe_key] = run_id
    index_data.setdefault("correlations", {})[correlation_id] = run_id
    _save_run_index(index_data)

    print(
        json.dumps(
            {
                "status": "ok",
                "runId": run_id,
                "manifest": str(manifest_path),
                "correlationId": manifest["correlationId"],
                "dedupeKey": dedupe_key,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_baseline_record(args):
    """Record baseline metric values for a lane."""
    _ensure_dir(QUALITY_BASELINES_DIR)

    baseline = {
        "version": "baseline-v1",
        "recordedAt": _now(),
        "lane": args.lane,
        "runId": args.run_id,
        "metrics": {
            "traceCompleteness": args.trace_completeness,
            "replayPassRate": args.replay_pass_rate,
            "contentFidelityErrorRate": args.content_fidelity_error_rate,
            "mttdHours": args.mttd_hours,
            "mttpHours": args.mttp_hours,
        },
        "notes": args.notes or "",
    }

    # Basic bounds guard.
    for pct_key in ("traceCompleteness", "replayPassRate", "contentFidelityErrorRate"):
        val = baseline["metrics"][pct_key]
        if val is not None and (val < 0 or val > 1):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": f"{pct_key} must be in [0,1], got {val}",
                    }
                )
            )
            return 1

    out_name = f"baseline-{args.lane}-{_today()}.json"
    out_path = QUALITY_BASELINES_DIR / out_name
    _save_json(out_path, baseline)

    print(
        json.dumps(
            {
                "status": "ok",
                "path": str(out_path),
                "lane": args.lane,
                "runId": args.run_id,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_trace_validate(args):
    """Validate trace records from a JSON/JSONL file and sink invalid rows."""
    input_path = Path(args.file)
    if not input_path.exists():
        print(json.dumps({"status": "error", "message": f"Trace input file not found: {input_path}"}))
        return 1

    _ensure_dir(QUALITY_TRACES_DIR)
    records = _parse_json_or_jsonl(input_path)

    manifest = None
    manifest_correlation_id = None
    manifest_source_version = None
    if getattr(args, "run_id", None):
        try:
            manifest = _load_run_manifest(_slugify(args.run_id))
            manifest_correlation_id = manifest.get("correlationId")
            manifest_source_version = manifest.get("sourceVersion")
        except FileNotFoundError as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
            return 1

    valid = []
    invalid = []
    for idx, record in enumerate(records, start=1):
        errs = _validate_trace_record(record)
        if not errs:
            errs.extend(_validate_ref_list(record.get("evidenceRefs"), "evidenceRefs"))
            errs.extend(_validate_ref_list(record.get("rubricRefs"), "rubricRefs"))

            run_id = record.get("runId")
            source_version = record.get("sourceVersion")
            correlation_id = record.get("correlationId") or manifest_correlation_id or run_id
            errs.extend(_validate_run_metadata(run_id, correlation_id, source_version))

            if manifest is not None:
                if run_id != manifest.get("runId"):
                    errs.append(
                        f"trace runId '{run_id}' mismatches manifest runId '{manifest.get('runId')}'"
                    )
                if source_version != manifest_source_version:
                    errs.append(
                        f"trace sourceVersion '{source_version}' mismatches manifest sourceVersion '{manifest_source_version}'"
                    )

        if errs:
            invalid.append({
                "line": idx,
                "errors": errs,
                "record": record,
                "validatedAt": _now(),
            })
        else:
            if manifest is not None:
                record["manifestRef"] = str((QUALITY_RUNS_DIR / manifest["runId"] / "manifest.json"))
                record["correlationId"] = manifest_correlation_id
            valid.append(record)

    for rec in valid:
        date_key = _iso_date_from_ts(rec.get("timestamp"))
        valid_path = QUALITY_TRACES_DIR / f"{date_key}.jsonl"
        with open(valid_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    invalid_path = QUALITY_TRACES_DIR / "invalid-traces.jsonl"
    if invalid:
        with open(invalid_path, "a", encoding="utf-8") as f:
            for rec in invalid:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    result = {
        "status": "ok" if not invalid else "issues_found",
        "input": str(input_path),
        "total": len(records),
        "valid": len(valid),
        "invalid": len(invalid),
        "invalidSink": str(invalid_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not invalid else 1


def cmd_quality_report_only(args):
    """Create report-only evaluation, gate, and recommendation artifacts for one run."""
    run_id = _slugify(args.run_id)
    manifest = _load_run_manifest(run_id)
    thresholds = _load_thresholds_reading_v1()

    # Validate metrics input bounds.
    for name, value in {
        "replayPassRate": args.replay_pass_rate,
        "traceCompleteness": args.trace_completeness,
        "contentFidelityErrorRate": args.content_fidelity_error_rate,
    }.items():
        if value < 0 or value > 1:
            print(json.dumps({"status": "error", "message": f"{name} must be in [0,1]"}, ensure_ascii=False))
            return 1
    if args.sample_size < 0:
        print(json.dumps({"status": "error", "message": "sampleSize must be >= 0"}, ensure_ascii=False))
        return 1

    metrics = {
        "traceCompleteness": args.trace_completeness,
        "replayPassRate": args.replay_pass_rate,
        "contentFidelityErrorRate": args.content_fidelity_error_rate,
        "sampleSize": args.sample_size,
    }

    effective_mode = args.mode
    if effective_mode == "auto":
        try:
            effective_mode = _load_gate_mode_control_v1()["mode"]
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 1

    checks = {
        "traceCompleteness": metrics["traceCompleteness"] >= thresholds["trace_completeness_min"],
        "replayPassRate": metrics["replayPassRate"] >= thresholds["replay_pass_rate_min"],
        "contentFidelityErrorRate": metrics["contentFidelityErrorRate"] <= thresholds["content_fidelity_error_rate_max"],
        "sampleSize": metrics["sampleSize"] >= thresholds["min_sample_size"],
    }

    coverage_checks = {
        "kc_buckets": {},
        "question_types": {},
        "enabled": False,
    }
    performance_checks = {
        "enabled": False,
        "checks": None,
    }

    if args.coverage_file:
        coverage_input_path = Path(args.coverage_file)
        if not coverage_input_path.exists():
            print(json.dumps({"status": "error", "message": f"Coverage file not found: {coverage_input_path}"}, ensure_ascii=False))
            return 1

        coverage_records = _load_json(coverage_input_path)
        if not isinstance(coverage_records, dict):
            print(json.dumps({"status": "error", "message": "Coverage file must be a JSON object"}, ensure_ascii=False))
            return 1

        try:
            matrix = _load_coverage_matrix_reading_v1()
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 1

        coverage_checks["enabled"] = True

        for family in ("kc_buckets", "question_types"):
            observed = coverage_records.get(family)
            if observed is None:
                print(json.dumps({"status": "error", "message": f"Coverage input missing section: {family}"}, ensure_ascii=False))
                return 1
            if not isinstance(observed, dict) or not observed:
                print(json.dumps({"status": "error", "message": f"Coverage section '{family}' must be a non-empty object"}, ensure_ascii=False))
                return 1

            for bucket, th in matrix[family].items():
                item = observed.get(bucket)
                if not isinstance(item, dict):
                    coverage_checks[family][bucket] = {
                        "passed": False,
                        "reason": "missing_bucket",
                        "threshold": th,
                    }
                    continue

                pass_rate = item.get("passRate")
                case_count = item.get("caseCount")
                if not isinstance(pass_rate, (int, float)) or not isinstance(case_count, int):
                    coverage_checks[family][bucket] = {
                        "passed": False,
                        "reason": "invalid_shape",
                        "threshold": th,
                        "observed": item,
                    }
                    continue

                passed = pass_rate >= th["min_pass_rate"] and case_count >= th["min_cases"]
                coverage_checks[family][bucket] = {
                    "passed": passed,
                    "threshold": th,
                    "observed": {"passRate": pass_rate, "caseCount": case_count},
                }

        checks["coverageGuardrails"] = all(
            v.get("passed")
            for section in (coverage_checks["kc_buckets"], coverage_checks["question_types"])
            for v in section.values()
        )

    if args.performance_file:
        performance_input_path = Path(args.performance_file)
        if not performance_input_path.exists():
            print(json.dumps({"status": "error", "message": f"Performance file not found: {performance_input_path}"}, ensure_ascii=False))
            return 1

        perf_metrics = _load_json(performance_input_path)
        try:
            budget = _load_performance_budget_reading_v1()
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 1

        perf_eval, perf_errors = _evaluate_performance_budget(perf_metrics, budget)
        if perf_errors:
            print(json.dumps({"status": "error", "errors": perf_errors}, ensure_ascii=False, indent=2))
            return 1

        performance_checks["enabled"] = True
        performance_checks["checks"] = perf_eval
        checks["performanceBudgets"] = perf_eval["passed"]

    fail_count = sum(1 for v in checks.values() if not v)
    if fail_count == 0:
        gate_state = "green"
    elif fail_count == 1:
        gate_state = "yellow"
    else:
        gate_state = "red"

    try:
        gate_policy = _load_soft_gate_policy_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    approval_mode = gate_policy["approval_mode"]
    requires_ack = effective_mode == "soft-gate" and gate_state in {"yellow", "red"} and approval_mode == "founder_approval"
    merge_allowed = not requires_ack
    approval_status = "not_required"
    if effective_mode == "soft-gate" and gate_state in {"yellow", "red"}:
        if approval_mode == "founder_approval":
            approval_status = "pending"
        else:
            approval_status = "auto_accepted"
    if effective_mode == "hard-gate":
        requires_ack = False
        merge_allowed = gate_state == "green"
        approval_status = "auto_pass" if gate_state == "green" else "blocked"

    _ensure_dir(QUALITY_EVALS_DIR / run_id)
    _ensure_dir(QUALITY_GATES_DIR)
    _ensure_dir(QUALITY_RECOMMENDATIONS_DIR)

    eval_path = QUALITY_EVALS_DIR / run_id / "summary.json"
    gate_path = QUALITY_GATES_DIR / f"{run_id}.json"
    reco_path = QUALITY_RECOMMENDATIONS_DIR / f"{run_id}.md"

    for path in (eval_path, gate_path, reco_path):
        if _is_artifact_locked(path):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": f"Artifact is immutable and cannot be overwritten: {path}",
                    },
                    ensure_ascii=False,
                )
            )
            return 1

    eval_payload = {
        "version": "eval-summary-v1",
        "runId": run_id,
        "correlationId": manifest.get("correlationId"),
        "lane": manifest.get("lane"),
        "recordedAt": _now(),
        "metrics": metrics,
        "thresholdsRef": str(THRESHOLDS_READING_V1_FILE),
        "checks": checks,
        "coverage": coverage_checks,
        "performance": performance_checks,
    }
    _save_json(eval_path, eval_payload)

    gate_payload = {
        "version": "gate-v1",
        "mode": effective_mode,
        "runId": run_id,
        "correlationId": manifest.get("correlationId"),
        "recordedAt": _now(),
        "state": gate_state,
        "checks": checks,
        "policy": {
            "reportOnly": effective_mode == "report-only",
            "requiresFounderAcknowledgement": requires_ack,
            "approvalMode": approval_mode,
            "mergeAllowed": merge_allowed,
            "approvalStatus": approval_status,
            "hardGateActive": effective_mode == "hard-gate",
        },
        "approval": {
            "status": approval_status,
            "approvedBy": None,
            "approvedAt": None,
            "note": None,
        },
    }
    _save_json(gate_path, gate_payload)

    reco_lines = [
        f"# Quality Recommendation for {run_id}",
        "",
        f"- mode: {effective_mode}",
        f"- gateState: {gate_state}",
        f"- correlationId: {manifest.get('correlationId')}",
        "",
        "## Checks",
        f"- traceCompleteness: {'PASS' if checks['traceCompleteness'] else 'FAIL'}",
        f"- replayPassRate: {'PASS' if checks['replayPassRate'] else 'FAIL'}",
        f"- contentFidelityErrorRate: {'PASS' if checks['contentFidelityErrorRate'] else 'FAIL'}",
        f"- sampleSize: {'PASS' if checks['sampleSize'] else 'FAIL'}",
        "",
        "## Action",
    ]
    if gate_state == "green":
        reco_lines.append("- Continue rollout.")
    elif gate_state == "yellow":
        reco_lines.append("- Founder acknowledgement required before merge.")
    else:
        reco_lines.append("- Block merge and open remediation task.")

    reco_path.write_text("\n".join(reco_lines) + "\n", encoding="utf-8")

    manifest.setdefault("artifacts", {})
    manifest["artifacts"].update(
        {
            "evalSummary": str(eval_path),
            "gate": str(gate_path),
            "recommendation": str(reco_path),
        }
    )
    manifest["status"] = "reported"
    _save_json(QUALITY_RUNS_DIR / run_id / "manifest.json", manifest)

    print(
        json.dumps(
            {
                "status": "ok",
                "runId": run_id,
                "mode": effective_mode,
                "gateState": gate_state,
                "artifacts": {
                    "evalSummary": str(eval_path),
                    "gate": str(gate_path),
                    "recommendation": str(reco_path),
                },
                "coverageEnabled": coverage_checks["enabled"],
                "performanceEnabled": performance_checks["enabled"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_artifact_publish(args):
    """C1: Mark run artifacts as immutable after publication."""
    run_id = _slugify(args.run_id)
    manifest = _load_run_manifest(run_id)
    artifacts = manifest.get("artifacts", {})
    required = ["evalSummary", "gate", "recommendation"]
    missing = [k for k in required if not artifacts.get(k)]
    if missing:
        print(json.dumps({"status": "error", "message": f"Cannot publish run: missing artifacts {missing}"}, ensure_ascii=False))
        return 1

    locked = _lock_run_artifacts(run_id, artifacts, args.published_by)
    manifest["status"] = "published"
    manifest["publishedAt"] = locked["publishedAt"]
    manifest["publishedBy"] = locked["publishedBy"]
    _save_json(QUALITY_RUNS_DIR / run_id / "manifest.json", manifest)

    print(
        json.dumps(
            {
                "status": "ok",
                "runId": run_id,
                "publishedAt": locked["publishedAt"],
                "publishedBy": locked["publishedBy"],
                "lockedArtifacts": locked["artifacts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_phase_gate(args):
    """C2: Track and enforce thin-slice sequencing gates."""
    try:
        config = _load_phase_gates_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    phases = config["phases"]
    if args.phase and args.phase not in phases:
        print(json.dumps({"status": "error", "message": f"phase must be one of {phases}"}, ensure_ascii=False))
        return 1

    state = _load_phase_gate_state()
    completed = state.setdefault("completed", {})

    if args.action == "status":
        print(
            json.dumps(
                {
                    "status": "ok",
                    "phases": phases,
                    "completed": completed,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not args.phase:
        print(json.dumps({"status": "error", "message": "--phase is required for check/complete"}, ensure_ascii=False))
        return 1

    if args.action == "check":
        errors = _phase_prereq_errors(args.phase)
        print(
            json.dumps(
                {
                    "status": "ok" if not errors else "issues_found",
                    "phase": args.phase,
                    "prerequisiteErrors": errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not errors else 1

    if args.action == "complete":
        errors = _phase_prereq_errors(args.phase)
        if errors:
            print(json.dumps({"status": "error", "phase": args.phase, "errors": errors}, ensure_ascii=False, indent=2))
            return 1

        completed[args.phase] = {
            "completedAt": _now(),
            "owner": args.owner or "founder",
            "note": args.note or "",
        }
        _save_phase_gate_state(state)
        _append_kt_pack_update(args.phase, args.note or "phase checkpoint completed")

        print(
            json.dumps(
                {
                    "status": "ok",
                    "phase": args.phase,
                    "completed": completed[args.phase],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(json.dumps({"status": "error", "message": "Unknown action"}, ensure_ascii=False))
    return 1


def cmd_quality_kt_pack_update(args):
    """C3: Maintain KT pack artifacts after phase checkpoints."""
    _ensure_kt_pack_files()
    phase = _slugify(args.phase)
    summary = args.summary or "kt pack refreshed"
    _append_kt_pack_update(phase, summary)

    if args.note:
        with open(KT_ONBOARDING_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n- {_now()} | phase={phase} | {args.note}\n")

    print(
        json.dumps(
            {
                "status": "ok",
                "phase": phase,
                "updated": [
                    str(KT_ONBOARDING_FILE),
                    str(KT_DECISION_LOG_TEMPLATE_FILE),
                    str(KT_PACK_MAINTENANCE_LOG_FILE),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_weekly_review_log(args):
    """C4: Write one weekly review summary artifact."""
    week_key = args.week_key or _iso_week_key(_now())
    _ensure_dir(QUALITY_WEEKLY_REVIEWS_DIR)
    out_path = QUALITY_WEEKLY_REVIEWS_DIR / f"{week_key}.md"

    if out_path.exists() and not args.overwrite:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Weekly review already exists for {week_key}: {out_path}",
                },
                ensure_ascii=False,
            )
        )
        return 1

    content = "\n".join(
        [
            f"# Weekly Review {week_key}",
            "",
            f"- recordedAt: {_now()}",
            f"- achieved: {args.achieved}",
            f"- misses: {args.misses}",
            f"- risks: {args.risks}",
            f"- nextWeekCommitments: {args.commitments}",
            "",
        ]
    )
    out_path.write_text(content, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "week": week_key,
                "path": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_shadow_dry_run(args):
    """W4-T1: Execute read-only shadow lane sampling and emit disagreement report."""
    prereq_errors = _phase_prereq_errors("w4")
    if prereq_errors:
        print(json.dumps({"status": "error", "errors": prereq_errors}, ensure_ascii=False, indent=2))
        return 1

    run_id = _slugify(args.run_id)
    manifest = _load_run_manifest(run_id)

    source = Path(args.file)
    if not source.exists():
        print(json.dumps({"status": "error", "message": f"Shadow input file not found: {source}"}, ensure_ascii=False))
        return 1

    shadow_input = _load_json(source)
    if not isinstance(shadow_input, dict):
        print(json.dumps({"status": "error", "message": "Shadow input must be a JSON object"}, ensure_ascii=False))
        return 1

    records = shadow_input.get("comparisons")
    if not isinstance(records, list) or not records:
        print(json.dumps({"status": "error", "message": "comparisons must be a non-empty list"}, ensure_ascii=False))
        return 1

    try:
        policy = _load_shadow_lane_policy_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    lane = _slugify(args.lane or policy["lane"])
    if lane not in ALLOWED_LANES:
        print(json.dumps({"status": "error", "message": f"lane must be one of {sorted(ALLOWED_LANES)}"}, ensure_ascii=False))
        return 1

    total_cases = shadow_input.get("totalCases")
    if not isinstance(total_cases, int) or total_cases <= 0:
        total_cases = len(records)

    ratio = args.sample_slice_ratio if args.sample_slice_ratio is not None else float(policy["sampleSliceRatio"])
    min_cases = int(policy["minCases"])
    sample_target = int(max(min_cases, math.ceil(total_cases * ratio)))
    sample_target = min(sample_target, len(records))
    sampled = records[:sample_target]

    parse_errors = []
    per_bucket = {}
    disagreements = []
    for idx, rec in enumerate(sampled, start=1):
        if not isinstance(rec, dict):
            parse_errors.append(f"comparison record {idx} must be an object")
            continue
        kc_bucket = rec.get("kcBucket")
        if not isinstance(kc_bucket, str) or not kc_bucket.strip():
            parse_errors.append(f"comparison record {idx} missing kcBucket")
            continue
        primary = rec.get("primaryOutcome")
        shadow = rec.get("shadowOutcome")
        if not isinstance(primary, str) or not isinstance(shadow, str):
            parse_errors.append(f"comparison record {idx} requires string primaryOutcome and shadowOutcome")
            continue

        bucket = per_bucket.setdefault(kc_bucket, {"compared": 0, "disagreements": 0})
        bucket["compared"] += 1

        disagreed = bool(rec.get("disagreed")) or (primary != shadow)
        if disagreed:
            bucket["disagreements"] += 1
            disagreements.append(
                {
                    "caseId": rec.get("caseId") or f"case-{idx:04d}",
                    "kcBucket": kc_bucket,
                    "primaryOutcome": primary,
                    "shadowOutcome": shadow,
                    "reason": rec.get("reason") or "outcome_mismatch",
                }
            )

    if parse_errors:
        print(json.dumps({"status": "error", "errors": parse_errors}, ensure_ascii=False, indent=2))
        return 1

    bucket_stats = {}
    for bucket, values in per_bucket.items():
        rate = values["disagreements"] / values["compared"] if values["compared"] else 0.0
        bucket_stats[bucket] = {
            "compared": values["compared"],
            "disagreements": values["disagreements"],
            "disagreementRate": round(rate, 4),
        }

    _ensure_dir(QUALITY_SHADOW_DIR)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = QUALITY_SHADOW_DIR / f"{run_id}-{lane}-{timestamp}.json"
    payload = {
        "version": "shadow-dry-run-v1",
        "runId": run_id,
        "lane": lane,
        "recordedAt": _now(),
        "readOnly": True,
        "sample": {
            "totalCases": total_cases,
            "sampleSliceRatio": ratio,
            "minCases": min_cases,
            "sampledCases": sample_target,
        },
        "summary": {
            "comparedCases": sum(v["compared"] for v in per_bucket.values()),
            "disagreementCases": len(disagreements),
            "disagreementRate": round(len(disagreements) / sample_target, 4) if sample_target else 0.0,
        },
        "byKcBucket": bucket_stats,
        "disagreements": disagreements,
        "refs": {
            "manifest": str(QUALITY_RUNS_DIR / run_id / "manifest.json"),
            "sourceInput": str(source),
        },
    }
    _save_json(out_path, payload)

    manifest.setdefault("artifacts", {})
    manifest["artifacts"].setdefault("shadowDisagreementReports", [])
    manifest["artifacts"]["shadowDisagreementReports"].append(str(out_path))
    manifest["status"] = "shadow-evaluated"
    _save_json(QUALITY_RUNS_DIR / run_id / "manifest.json", manifest)

    print(
        json.dumps(
            {
                "status": "ok",
                "runId": run_id,
                "lane": lane,
                "readOnly": True,
                "sampledCases": sample_target,
                "disagreementCases": len(disagreements),
                "artifact": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_shadow_weekly_report(args):
    """W4-T2: Aggregate weekly disagreement trend by KC bucket."""
    prereq_errors = _phase_prereq_errors("w4")
    if prereq_errors:
        print(json.dumps({"status": "error", "errors": prereq_errors}, ensure_ascii=False, indent=2))
        return 1

    week_key = args.week_key
    if not week_key:
        week_key = _iso_week_key(_now())

    shadow_files = [p for p in QUALITY_SHADOW_DIR.glob("*.json") if p.is_file()]
    if not shadow_files:
        print(json.dumps({"status": "error", "message": "No shadow dry-run artifacts found"}, ensure_ascii=False))
        return 1

    this_week = {}
    history = {}

    for path in shadow_files:
        record = _load_json(path)
        if not isinstance(record, dict):
            continue
        record_week = _iso_week_key(record.get("recordedAt"))
        by_bucket = record.get("byKcBucket")
        if not isinstance(by_bucket, dict):
            continue

        for bucket, stats in by_bucket.items():
            compared = stats.get("compared")
            disagreements = stats.get("disagreements")
            if not isinstance(compared, int) or not isinstance(disagreements, int):
                continue
            wk_store = history.setdefault(bucket, {})
            wk_totals = wk_store.setdefault(record_week, {"compared": 0, "disagreements": 0})
            wk_totals["compared"] += compared
            wk_totals["disagreements"] += disagreements

            if record_week == week_key:
                wk_current = this_week.setdefault(bucket, {"compared": 0, "disagreements": 0})
                wk_current["compared"] += compared
                wk_current["disagreements"] += disagreements

    report_buckets = {}
    for bucket, stats in this_week.items():
        compared = stats["compared"]
        disagreements = stats["disagreements"]
        report_buckets[bucket] = {
            "compared": compared,
            "disagreements": disagreements,
            "disagreementRate": round(disagreements / compared, 4) if compared else 0.0,
        }

    trend = {}
    for bucket, per_week in history.items():
        week_points = []
        for wk, totals in sorted(per_week.items()):
            compared = totals["compared"]
            disagreements = totals["disagreements"]
            week_points.append(
                {
                    "week": wk,
                    "compared": compared,
                    "disagreements": disagreements,
                    "disagreementRate": round(disagreements / compared, 4) if compared else 0.0,
                }
            )
        trend[bucket] = week_points

    _ensure_dir(QUALITY_SHADOW_WEEKLY_DIR)
    out_path = QUALITY_SHADOW_WEEKLY_DIR / f"{week_key}.json"
    payload = {
        "version": "shadow-weekly-report-v1",
        "week": week_key,
        "recordedAt": _now(),
        "byKcBucket": report_buckets,
        "trend": trend,
        "sources": sorted(str(p) for p in shadow_files),
    }
    _save_json(out_path, payload)

    print(
        json.dumps(
            {
                "status": "ok",
                "week": week_key,
                "artifact": str(out_path),
                "bucketCount": len(report_buckets),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_schema_compat_check(args):
    """W4-T3: Validate artifact compatibility and block unversioned breaking changes."""
    prereq_errors = _phase_prereq_errors("w4")
    if prereq_errors:
        print(json.dumps({"status": "error", "errors": prereq_errors}, ensure_ascii=False, indent=2))
        return 1

    if args.file:
        try:
            rules = _load_schema_compat_rules_v1()
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 1

        artifact_type = args.artifact_type
        if artifact_type not in {"trace", "eval"}:
            print(json.dumps({"status": "error", "message": "--artifact-type must be trace or eval"}, ensure_ascii=False))
            return 1

        input_path = Path(args.file)
        if not input_path.exists():
            print(json.dumps({"status": "error", "message": f"Artifact file not found: {input_path}"}, ensure_ascii=False))
            return 1

        spec = rules["artifacts"][artifact_type]
        records = _parse_json_or_jsonl(input_path)
        if not records:
            print(json.dumps({"status": "error", "message": "Artifact file is empty"}, ensure_ascii=False))
            return 1

        errors = []
        version_field = spec["versionField"]
        allowed_versions = set(spec["allowedVersions"])
        required_fields = set(spec["requiredFields"])
        for idx, rec in enumerate(records, start=1):
            if not isinstance(rec, dict):
                errors.append(f"record {idx} must be an object")
                continue
            version_value = rec.get(version_field)
            if not isinstance(version_value, str) or version_value not in allowed_versions:
                errors.append(
                    f"record {idx} invalid {version_field}: '{version_value}', allowed {sorted(allowed_versions)}"
                )
            missing = sorted(field for field in required_fields if field not in rec)
            if missing:
                errors.append(f"record {idx} missing required fields: {missing}")

        print(
            json.dumps(
                {
                    "status": "ok" if not errors else "issues_found",
                    "artifactType": artifact_type,
                    "records": len(records),
                    "errors": errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not errors else 1

    if args.old_schema and args.new_schema:
        old_schema_path = Path(args.old_schema)
        new_schema_path = Path(args.new_schema)
        if not old_schema_path.exists() or not new_schema_path.exists():
            print(json.dumps({"status": "error", "message": "Schema files not found"}, ensure_ascii=False))
            return 1

        old_schema = _load_json(old_schema_path)
        new_schema = _load_json(new_schema_path)
        if not isinstance(old_schema, dict) or not isinstance(new_schema, dict):
            print(json.dumps({"status": "error", "message": "Schema files must be JSON objects"}, ensure_ascii=False))
            return 1

        old_required = set(old_schema.get("requiredFields", []))
        new_required = set(new_schema.get("requiredFields", []))
        removed = sorted(old_required - new_required)

        old_version = old_schema.get("schemaVersion") or old_schema.get("version")
        new_version = new_schema.get("schemaVersion") or new_schema.get("version")
        if not isinstance(old_version, str) or not isinstance(new_version, str):
            print(json.dumps({"status": "error", "message": "Both schemas must include schemaVersion or version"}, ensure_ascii=False))
            return 1

        breaking = bool(removed)
        version_bumped = old_version != new_version
        blocked = breaking and not version_bumped

        print(
            json.dumps(
                {
                    "status": "ok" if not blocked else "issues_found",
                    "breakingChangeDetected": breaking,
                    "versionBumped": version_bumped,
                    "blocked": blocked,
                    "removedRequiredFields": removed,
                    "oldVersion": old_version,
                    "newVersion": new_version,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not blocked else 1

    print(
        json.dumps(
            {
                "status": "error",
                "message": "Provide either (--artifact-type + --file) or (--old-schema + --new-schema)",
            },
            ensure_ascii=False,
        )
    )
    return 1


def cmd_quality_gate_mode_switch(args):
    """W4-T4: Get or set active gate mode via config."""
    prereq_errors = _phase_prereq_errors("w4")
    if prereq_errors:
        print(json.dumps({"status": "error", "errors": prereq_errors}, ensure_ascii=False, indent=2))
        return 1

    if args.set_mode:
        try:
            payload = _save_gate_mode_control_v1(args.set_mode)
        except ValueError as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 1
    else:
        try:
            payload = _load_gate_mode_control_v1()
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 1

    print(json.dumps({"status": "ok", **payload}, ensure_ascii=False, indent=2))
    return 0


def cmd_quality_hard_gate_rehearsal(args):
    """W4-T4: Rehearse hard-gate activation and rollback steps with audit artifact."""
    prereq_errors = _phase_prereq_errors("w4")
    if prereq_errors:
        print(json.dumps({"status": "error", "errors": prereq_errors}, ensure_ascii=False, indent=2))
        return 1

    run_id = _slugify(args.run_id)
    gate_path = QUALITY_GATES_DIR / f"{run_id}.json"
    gate_payload = _load_json(gate_path)
    if not gate_payload:
        print(json.dumps({"status": "error", "message": f"Gate artifact not found: {gate_path}"}, ensure_ascii=False))
        return 1

    if not HARD_GATE_ROLLBACK_PLAYBOOK_FILE.exists():
        print(json.dumps({"status": "error", "message": f"Rollback playbook not found: {HARD_GATE_ROLLBACK_PLAYBOOK_FILE}"}, ensure_ascii=False))
        return 1

    try:
        before = _load_gate_mode_control_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    activated = _save_gate_mode_control_v1("hard-gate")
    rollback_to = args.rollback_to or "soft-gate"
    rolled_back = _save_gate_mode_control_v1(rollback_to)

    _ensure_dir(QUALITY_GATE_REHEARSALS_DIR)
    rehearsal_id = f"hard-gate-rehearsal-{run_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out_path = QUALITY_GATE_REHEARSALS_DIR / f"{rehearsal_id}.json"

    payload = {
        "version": "hard-gate-rehearsal-v1",
        "rehearsalId": rehearsal_id,
        "runId": run_id,
        "recordedAt": _now(),
        "steps": [
            {"name": "load_playbook", "status": "completed", "playbook": str(HARD_GATE_ROLLBACK_PLAYBOOK_FILE)},
            {"name": "activate_hard_gate", "status": "completed", "mode": activated["mode"]},
            {"name": "rollback", "status": "completed", "mode": rolled_back["mode"]},
        ],
        "refs": {
            "gate": str(gate_path),
            "playbook": str(HARD_GATE_ROLLBACK_PLAYBOOK_FILE),
        },
        "beforeMode": before["mode"],
        "afterMode": rolled_back["mode"],
    }
    _save_json(out_path, payload)

    print(
        json.dumps(
            {
                "status": "ok",
                "rehearsalId": rehearsal_id,
                "artifact": str(out_path),
                "beforeMode": before["mode"],
                "afterMode": rolled_back["mode"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_hard_gate_promotion_check(args):
    """W4-T5: Validate promotion criteria and optionally activate hard-gate."""
    prereq_errors = _phase_prereq_errors("w4")
    if prereq_errors:
        print(json.dumps({"status": "error", "errors": prereq_errors}, ensure_ascii=False, indent=2))
        return 1

    try:
        criteria = _load_hard_gate_promotion_criteria_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    stable_required = criteria["stableCyclesRequired"]
    eval_files = sorted(
        [p for p in QUALITY_EVALS_DIR.glob("*/summary.json") if p.is_file()],
        key=lambda p: (_load_json(p, {}).get("recordedAt") or ""),
    )
    if len(eval_files) < stable_required:
        print(
            json.dumps(
                {
                    "status": "issues_found",
                    "message": f"Need at least {stable_required} eval cycles, found {len(eval_files)}",
                },
                ensure_ascii=False,
            )
        )
        return 1

    recent = eval_files[-stable_required:]
    cycle_checks = []
    for eval_path in recent:
        payload = _load_json(eval_path, {})
        metrics = payload.get("metrics", {})
        run_id = payload.get("runId")
        gate = _load_json(QUALITY_GATES_DIR / f"{run_id}.json", {}) if isinstance(run_id, str) else {}

        check = {
            "runId": run_id,
            "traceCompleteness": float(metrics.get("traceCompleteness", -1)) >= criteria["traceCompletenessMin"],
            "replayPassRate": float(metrics.get("replayPassRate", -1)) >= criteria["replayPassRateMin"],
            "contentFidelityErrorRate": float(metrics.get("contentFidelityErrorRate", 2)) <= criteria["contentFidelityErrorRateMax"],
            "sampleSize": int(metrics.get("sampleSize", -1)) >= criteria["minSampleSize"],
            "gateGreen": gate.get("state") == "green",
        }
        check["passed"] = all(v for k, v in check.items() if k not in {"runId", "passed"})
        cycle_checks.append(check)

    founder_approved = bool(args.approved_by)
    criteria_met = all(item["passed"] for item in cycle_checks)
    approval_ok = (not criteria["founderApprovalRequired"]) or founder_approved
    promotable = criteria_met and approval_ok

    if promotable and args.promote:
        _save_gate_mode_control_v1("hard-gate")

    _ensure_dir(QUALITY_GATE_PROMOTIONS_DIR)
    out_path = QUALITY_GATE_PROMOTIONS_DIR / f"promotion-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    artifact = {
        "version": "hard-gate-promotion-check-v1",
        "recordedAt": _now(),
        "criteria": criteria,
        "cycleChecks": cycle_checks,
        "founderApproval": {
            "required": criteria["founderApprovalRequired"],
            "approvedBy": args.approved_by or None,
            "approvedAt": _now() if founder_approved else None,
        },
        "promotable": promotable,
        "promoted": bool(promotable and args.promote),
    }
    _save_json(out_path, artifact)

    print(
        json.dumps(
            {
                "status": "ok" if promotable else "issues_found",
                "promotable": promotable,
                "promoted": bool(promotable and args.promote),
                "artifact": str(out_path),
                "stableCyclesRequired": stable_required,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if promotable else 1


def cmd_quality_gate_approval_mode(args):
    """Get or set soft-gate approval mode."""
    if args.set_mode:
        try:
            _save_soft_gate_policy_v1(args.set_mode)
        except ValueError as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 1

    try:
        policy = _load_soft_gate_policy_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "policyFile": str(SOFT_GATE_POLICY_V1_FILE),
                "approvalMode": policy["approval_mode"],
                "allowedModes": policy["allowed_modes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_gate_acknowledge(args):
    """Founder acknowledgement for yellow/red soft-gate runs."""
    run_id = _slugify(args.run_id)
    gate_path = QUALITY_GATES_DIR / f"{run_id}.json"
    gate = _load_json(gate_path)
    if not gate:
        print(json.dumps({"status": "error", "message": f"Gate artifact not found: {gate_path}"}, ensure_ascii=False))
        return 1

    if gate.get("mode") != "soft-gate":
        print(json.dumps({"status": "error", "message": "Only soft-gate runs can be acknowledged"}, ensure_ascii=False))
        return 1

    policy = gate.get("policy", {})
    if not policy.get("requiresFounderAcknowledgement"):
        print(json.dumps({"status": "error", "message": "This gate does not require founder acknowledgement"}, ensure_ascii=False))
        return 1

    gate.setdefault("approval", {})
    gate["approval"].update(
        {
            "status": "approved",
            "approvedBy": args.approved_by,
            "approvedAt": _now(),
            "note": args.note or "",
        }
    )
    policy["mergeAllowed"] = True
    policy["approvalStatus"] = "approved"
    gate["policy"] = policy

    _save_json(gate_path, gate)

    print(
        json.dumps(
            {
                "status": "ok",
                "runId": run_id,
                "gate": str(gate_path),
                "mergeAllowed": True,
                "approvedBy": args.approved_by,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_budget_validate(args):
    """Validate runner performance metrics against configured budget."""
    metrics_file = Path(args.file)
    if not metrics_file.exists():
        print(json.dumps({"status": "error", "message": f"Performance metrics file not found: {metrics_file}"}, ensure_ascii=False))
        return 1

    perf_metrics = _load_json(metrics_file)
    try:
        budget = _load_performance_budget_reading_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    checks, errors = _evaluate_performance_budget(perf_metrics, budget)
    if errors:
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {
                "status": "ok" if checks["passed"] else "issues_found",
                "passed": checks["passed"],
                "budgetRef": str(PERFORMANCE_BUDGET_READING_V1_FILE),
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if checks["passed"] else 1


def cmd_quality_week3_checkpoint(args):
    """Evaluate Week-3 acceptance checkpoint for one run.

    Acceptance:
      - traceCompleteness >= 0.80
      - replayPassRate >= 0.75
      - contentFidelityErrorRate < 0.05
      - soft-gate flow operational
    """
    run_id = _slugify(args.run_id)
    manifest = _load_run_manifest(run_id)

    artifacts = manifest.get("artifacts", {})
    eval_path = Path(artifacts.get("evalSummary", str(QUALITY_EVALS_DIR / run_id / "summary.json")))
    gate_path = Path(artifacts.get("gate", str(QUALITY_GATES_DIR / f"{run_id}.json")))

    eval_data = _load_json(eval_path)
    gate_data = _load_json(gate_path)
    if not eval_data:
        print(json.dumps({"status": "error", "message": f"Eval summary not found: {eval_path}"}, ensure_ascii=False))
        return 1
    if not gate_data:
        print(json.dumps({"status": "error", "message": f"Gate artifact not found: {gate_path}"}, ensure_ascii=False))
        return 1

    metrics = eval_data.get("metrics", {})
    trace_completeness = metrics.get("traceCompleteness")
    replay_pass_rate = metrics.get("replayPassRate")
    fidelity_error_rate = metrics.get("contentFidelityErrorRate")

    metric_errors = []
    for name, value in {
        "traceCompleteness": trace_completeness,
        "replayPassRate": replay_pass_rate,
        "contentFidelityErrorRate": fidelity_error_rate,
    }.items():
        if not isinstance(value, (int, float)):
            metric_errors.append(f"{name} must be numeric in eval summary")

    if metric_errors:
        print(json.dumps({"status": "error", "errors": metric_errors}, ensure_ascii=False, indent=2))
        return 1

    policy = gate_data.get("policy")
    soft_gate_operational = (
        gate_data.get("mode") == "soft-gate"
        and isinstance(policy, dict)
        and all(
            key in policy
            for key in [
                "approvalMode",
                "requiresFounderAcknowledgement",
                "mergeAllowed",
                "approvalStatus",
            ]
        )
    )

    checks = {
        "traceCompleteness": {
            "passed": float(trace_completeness) >= 0.80,
            "threshold": ">=0.80",
            "observed": float(trace_completeness),
        },
        "replayPassRate": {
            "passed": float(replay_pass_rate) >= 0.75,
            "threshold": ">=0.75",
            "observed": float(replay_pass_rate),
        },
        "contentFidelityErrorRate": {
            "passed": float(fidelity_error_rate) < 0.05,
            "threshold": "<0.05",
            "observed": float(fidelity_error_rate),
        },
        "softGateOperational": {
            "passed": soft_gate_operational,
            "threshold": "soft-gate policy fields present",
            "observed": {
                "mode": gate_data.get("mode"),
                "policyKeys": sorted(policy.keys()) if isinstance(policy, dict) else [],
            },
        },
    }

    accepted = all(v["passed"] for v in checks.values())
    _ensure_dir(QUALITY_GATE_CHECKPOINTS_DIR)
    out_path = QUALITY_GATE_CHECKPOINTS_DIR / f"week3-{run_id}.json"
    payload = {
        "version": "week3-checkpoint-v1",
        "runId": run_id,
        "recordedAt": _now(),
        "accepted": accepted,
        "checks": checks,
        "refs": {
            "manifest": str(QUALITY_RUNS_DIR / run_id / "manifest.json"),
            "evalSummary": str(eval_path),
            "gate": str(gate_path),
        },
    }
    _save_json(out_path, payload)

    print(
        json.dumps(
            {
                "status": "ok" if accepted else "issues_found",
                "accepted": accepted,
                "runId": run_id,
                "checkpoint": str(out_path),
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if accepted else 1


def cmd_quality_incident_dry_run(args):
    """Run a full incident simulation: detect -> adjudicate -> override/reject -> report."""
    run_id = _slugify(args.run_id)
    decision = args.decision
    adjudicator = (args.adjudicator or "founder").strip()

    manifest = _load_run_manifest(run_id)
    artifacts = manifest.get("artifacts", {})
    gate_path = Path(artifacts.get("gate", str(QUALITY_GATES_DIR / f"{run_id}.json")))
    eval_path = Path(artifacts.get("evalSummary", str(QUALITY_EVALS_DIR / run_id / "summary.json")))
    checkpoint_path = Path(QUALITY_GATE_CHECKPOINTS_DIR / f"week3-{run_id}.json")

    gate_data = _load_json(gate_path)
    if not gate_data:
        print(json.dumps({"status": "error", "message": f"Gate artifact not found: {gate_path}"}, ensure_ascii=False))
        return 1

    eval_data = _load_json(eval_path)
    if not eval_data:
        print(json.dumps({"status": "error", "message": f"Eval artifact not found: {eval_path}"}, ensure_ascii=False))
        return 1

    detected = gate_data.get("state") in {"yellow", "red"}
    detect_step = {
        "name": "detect",
        "status": "completed",
        "detectedRegression": detected,
        "evidence": {
            "gateState": gate_data.get("state"),
            "failedChecks": [k for k, v in (gate_data.get("checks") or {}).items() if v is False],
        },
        "at": _now(),
    }

    adjudicate_step = {
        "name": "adjudicate",
        "status": "completed",
        "adjudicator": adjudicator,
        "riskLevel": gate_data.get("state"),
        "reason": args.reason or "incident dry-run review",
        "at": _now(),
    }

    action_step = {
        "name": "action",
        "status": "completed",
        "decision": decision,
        "at": _now(),
    }
    override_artifact = None

    if decision == "override":
        if not args.override_file:
            print(json.dumps({"status": "error", "message": "--override-file is required when decision=override"}, ensure_ascii=False))
            return 1
        override_file = Path(args.override_file)
        if not override_file.exists():
            print(json.dumps({"status": "error", "message": f"Override file not found: {override_file}"}, ensure_ascii=False))
            return 1

        contract = _load_override_contract_v1()
        request = _load_json(override_file)
        errors = _validate_override_request_payload(request, contract)
        if errors:
            print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False, indent=2))
            return 1

        override_id = _slugify(str(request["overrideId"]))
        override_artifact = QUALITY_OVERRIDES_DIR / f"{override_id}.json"
        _ensure_dir(QUALITY_OVERRIDES_DIR)
        _save_json(
            override_artifact,
            {
                "version": "override-v1",
                "validatedAt": _now(),
                "contractRef": str(OVERRIDE_CONTRACT_V1_FILE),
                "request": request,
                "incidentDryRun": True,
            },
        )
        action_step["result"] = {
            "mergeOutcome": "override_approved",
            "overrideArtifact": str(override_artifact),
        }
    else:
        action_step["result"] = {
            "mergeOutcome": "rejected",
            "rejectionReason": args.reason or "founder rejected in incident simulation",
        }

    report_step = {
        "name": "report",
        "status": "completed",
        "at": _now(),
        "summary": {
            "runId": run_id,
            "decision": decision,
            "gateState": gate_data.get("state"),
            "week3CheckpointExists": checkpoint_path.exists(),
        },
    }

    _ensure_dir(QUALITY_INCIDENTS_DIR)
    incident_id = f"{run_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    incident_path = QUALITY_INCIDENTS_DIR / f"{incident_id}.json"

    incident_payload = {
        "version": "incident-dry-run-v1",
        "incidentId": incident_id,
        "runId": run_id,
        "recordedAt": _now(),
        "completed": True,
        "steps": [detect_step, adjudicate_step, action_step, report_step],
        "refs": {
            "manifest": str(QUALITY_RUNS_DIR / run_id / "manifest.json"),
            "eval": str(eval_path),
            "gate": str(gate_path),
            "week3Checkpoint": str(checkpoint_path) if checkpoint_path.exists() else None,
            "override": str(override_artifact) if override_artifact else None,
        },
    }
    _save_json(incident_path, incident_payload)

    manifest.setdefault("artifacts", {})
    manifest["artifacts"].setdefault("incidentDryRuns", [])
    manifest["artifacts"]["incidentDryRuns"].append(str(incident_path))
    manifest["status"] = "incident-simulated"
    _save_json(QUALITY_RUNS_DIR / run_id / "manifest.json", manifest)

    print(
        json.dumps(
            {
                "status": "ok",
                "runId": run_id,
                "incidentId": incident_id,
                "decision": decision,
                "incidentArtifact": str(incident_path),
                "completed": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_override_validate(args):
    """Validate and persist emergency override requests against contract v1."""
    override_file = Path(args.file)
    if not override_file.exists():
        print(json.dumps({"status": "error", "message": f"Override request file not found: {override_file}"}, ensure_ascii=False))
        return 1

    try:
        contract = _load_override_contract_v1()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    request = _load_json(override_file)
    if not isinstance(request, dict):
        print(json.dumps({"status": "error", "message": "Override request must be a JSON object"}, ensure_ascii=False))
        return 1

    errors = _validate_override_request_payload(request, contract)

    if errors:
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    override_id = _slugify(str(request["overrideId"]))
    out_path = QUALITY_OVERRIDES_DIR / f"{override_id}.json"
    _ensure_dir(QUALITY_OVERRIDES_DIR)

    persisted = {
        "version": "override-v1",
        "validatedAt": _now(),
        "contractRef": str(OVERRIDE_CONTRACT_V1_FILE),
        "request": request,
    }
    _save_json(out_path, persisted)

    print(
        json.dumps(
            {
                "status": "ok",
                "overrideId": override_id,
                "path": str(out_path),
                "severity": request["severity"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_quality_trace_emit(args):
    """CLI wrapper for emit_trace() — called by the teacher from SKILL.md."""
    # Convert --outcome-matched "true"/"false" to bool
    raw_matched = getattr(args, "outcome_matched", None)
    outcome_matched_bool = None
    if raw_matched is not None:
        outcome_matched_bool = raw_matched == "true"

    result = emit_trace(
        skill=args.skill,
        decision_type=args.decision_type,
        evidence_refs=[r.strip() for r in (args.evidence_refs or "").split(",") if r.strip()],
        rubric_refs=[r.strip() for r in (args.rubric_refs or "").split(",") if r.strip()],
        kc_targets=[r.strip() for r in (args.kc_targets or "").split(",") if r.strip()],
        action=args.action,
        expected_outcome=args.expected_outcome,
        confidence=args.confidence,
        source_version=args.source_version or "prompt-v1",
        run_id=args.run_id if args.run_id else None,
        actual_outcome=getattr(args, "actual_outcome", None) or None,
        outcome_matched=outcome_matched_bool,
        outcome_note=getattr(args, "outcome_note", None) or None,
        student_response=getattr(args, "student_response", None) or None,
        student_engagement=getattr(args, "student_engagement", None) or None,
        student_confusion=getattr(args, "student_confusion", None) or None,
        strategy=getattr(args, "strategy", None) or None,
        teacher_transcript=getattr(args, "teacher_transcript", None) or None,
        schema_version=getattr(args, "schema_version", "trace-v3") or "trace-v3",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


def cmd_quality_trace_evaluate(args):
    """Summarize expected outcomes for a session run to guide close evaluation.

    Reads today's trace file (or the date specified), finds all traces for
    the given runId, and prints a summary the teacher can use to evaluate
    actual outcomes at session close.
    """
    run_id = args.run_id
    date_key = args.date if args.date else _today()
    trace_file = QUALITY_TRACES_DIR / f"{date_key}.jsonl"

    if not trace_file.exists():
        print(json.dumps({
            "status": "ok",
            "runId": run_id,
            "message": "No traces found for this date. Nothing to evaluate.",
            "traces": [],
        }, ensure_ascii=False, indent=2))
        return 0

    records = _parse_json_or_jsonl(trace_file)
    session_traces = [r for r in records if isinstance(r, dict) and r.get("runId") == run_id]

    if not session_traces:
        print(json.dumps({
            "status": "ok",
            "runId": run_id,
            "message": f"No traces found for runId '{run_id}' on {date_key}.",
            "traces": [],
        }, ensure_ascii=False, indent=2))
        return 0

    # Summarize expected outcomes by decision type
    from collections import Counter
    decision_counts = Counter(r.get("decisionType") for r in session_traces)
    already_evaluated = [r for r in session_traces if r.get("actualOutcome")]
    pending = [r for r in session_traces if not r.get("actualOutcome")]

    summary = []
    for r in pending:
        summary.append({
            "decisionType": r.get("decisionType"),
            "skill": r.get("skill"),
            "action": r.get("action"),
            "expectedOutcome": r.get("expectedOutcome"),
            "confidence": r.get("confidence"),
            "kcTargets": r.get("kcTargets", []),
            "idempotencyKey": _trace_idempotency_key(r),
        })

    print(json.dumps({
        "status": "ok",
        "runId": run_id,
        "date": date_key,
        "totalTraces": len(session_traces),
        "alreadyEvaluated": len(already_evaluated),
        "pendingEvaluation": len(pending),
        "decisionBreakdown": dict(decision_counts.most_common()),
        "expectedOutcomesToEvaluate": summary,
        "hint": "For each pending trace, determine if expectedOutcome was achieved. Then emit a close trace with --actual-outcome summarizing the session's actual results.",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_quality_prompt_tune(args):
    """Analyze trace patterns and suggest SKILL.md teaching improvements.

    Reads the last N weeks of traces, identifies teaching weaknesses,
    and outputs concrete, actionable prompt-tuning suggestions.
    """
    from collections import Counter

    weeks = args.weeks
    today = date.today()
    from datetime import timedelta

    # Collect traces
    all_records = []
    for i in range(weeks * 7):
        d = today - timedelta(days=i)
        trace_file = QUALITY_TRACES_DIR / f"{d.isoformat()}.jsonl"
        if trace_file.exists():
            records = _parse_json_or_jsonl(trace_file)
            all_records.extend([r for r in records if isinstance(r, dict) and "_parseError" not in r])

    if not all_records:
        result = {"status": "ok", "message": "No trace data to analyze. Start teaching sessions to generate tuning suggestions."}
        if args.output:
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # ── Pattern detection ──
    suggestions = []

    # 1. Confidence calibration pattern
    evaluated = [r for r in all_records if r.get("actualOutcome")]
    if evaluated:
        confidences = [r["confidence"] for r in evaluated if "confidence" in r]
        overconf = [r for r in evaluated if r.get("confidence", 0) >= 0.7 and r.get("outcomeMatched") is False]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            if avg_conf > 0.8 and len(overconf) > 0:
                suggestions.append({
                    "priority": "high",
                    "section": "TRACE ENFORCEMENT / Close Phase",
                    "finding": f"Average confidence is {avg_conf:.2f} but {len(overconf)} decisions were overconfident (≥0.7 confidence, outcome failed).",
                    "suggestion": "Add to SKILL.md: 'When confidence ≥ 0.8, ask yourself: what evidence contradicts my assessment? Lower confidence to 0.6-0.7 unless you have 3+ confirming data points.'",
                })

    # 2. Phase balance pattern
    decision_counts = Counter(r.get("decisionType") for r in all_records)
    diagnose_n = decision_counts.get("diagnose", 0)
    teach_n = decision_counts.get("teach", 0)
    evaluate_n = decision_counts.get("evaluate", 0)
    if diagnose_n > 0 and teach_n == 0:
        suggestions.append({
            "priority": "high",
            "section": "PHASE 4 (Teach)",
            "finding": f"{diagnose_n} diagnoses but 0 teachings — pure analysis without action.",
            "suggestion": "Add to SKILL.md Phase 4: 'CRITICAL: If you diagnosed in Phase 2 and planned in Phase 3, you MUST execute Phase 4 (Teach). A diagnosis without a lesson is a broken teaching loop.'",
        })
    if teach_n > 0 and evaluate_n == 0:
        suggestions.append({
            "priority": "high",
            "section": "PHASE 5 (Evaluate)",
            "finding": f"{teach_n} teachings but 0 evaluations — no outcome measurement.",
            "suggestion": "Add to SKILL.md Phase 5: 'MANDATORY after teaching: ask student for results, score answers, update KC mastery. Skipping evaluation = blind teaching.'",
        })

    # 3. Student response gap
    with_student_response = [r for r in all_records if r.get("studentResponse")]
    if len(with_student_response) == 0:
        suggestions.append({
            "priority": "medium",
            "section": "All Phases",
            "finding": "No traces include studentResponse — we see the teacher's view but not the student's.",
            "suggestion": "Add to trace-emit calls: '--student-response \"student said: ...\" --student-engagement high|medium|low'. Capture what the student actually said or did after each teaching action.'",
        })

    # 4. KC stagnation pattern
    kc_by_week = {}
    for r in all_records:
        week = r.get("timestamp", "")[:10]
        week_key_str = _iso_week_from_date(week) if week else None
        if week_key_str:
            if week_key_str not in kc_by_week:
                kc_by_week[week_key_str] = set()
            for kc in r.get("kcTargets", []):
                kc_by_week[week_key_str].add(kc)
    # Detect if same KCs repeat every week without cycling
    all_weeks = sorted(kc_by_week.keys())
    if len(all_weeks) >= 3:
        intersection = kc_by_week[all_weeks[0]]
        for w in all_weeks[1:]:
            intersection = intersection & kc_by_week[w]
        if len(intersection) >= 3:
            suggestions.append({
                "priority": "medium",
                "section": "PHASE 2 (Diagnose) / Phase 3 (Plan)",
                "finding": f"KCs {', '.join(sorted(intersection)[:3])} appear every week — possible stagnation.",
                "suggestion": "Add to SKILL.md Phase 2: 'If the same KC has been targeted for 3+ consecutive sessions without mastery improvement, flag it as a plateau KC and switch teaching strategy.'",
            })

    # 5. Schema version migration
    v1_count = sum(1 for r in all_records if r.get("schemaVersion") == "trace-v1")
    v2_count = sum(1 for r in all_records if r.get("schemaVersion") == "trace-v2")
    if v1_count > 0:
        suggestions.append({
            "priority": "low",
            "section": "TRACE ENFORCEMENT",
            "finding": f"{v1_count} traces still use schema v1 (no outcome evaluation).",
            "suggestion": "Update all trace-emit calls to use --schema-version trace-v3. Outcome evaluation is required for teaching quality improvement.",
        })

    result = {
        "status": "ok",
        "tracesAnalyzed": len(all_records),
        "weeksAnalyzed": weeks,
        "dateRange": f"{(today - timedelta(days=weeks*7-1)).isoformat()} to {today.isoformat()}",
        "suggestions": suggestions,
        "nextStep": "Review suggestions above. Apply the high-priority ones to SKILL.md first. Re-run prompt-tune next week to measure improvement.",
    }

    if args.output:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _iso_week_from_date(date_str: str) -> str | None:
    """Convert 'YYYY-MM-DD' to 'YYYY-Www'."""
    try:
        parts = date_str.split("-")
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    except (ValueError, IndexError):
        return None


def cmd_quality_strategy_compare(args):
    """Compare teaching strategies by actual outcome rates.

    Groups traces tagged with --strategy, compares outcomeMatched rates,
    and identifies which strategies work best per KC.
    """
    from collections import defaultdict
    from datetime import timedelta

    weeks = args.weeks
    today = date.today()
    filter_kc = args.kc

    # Collect traces
    all_records = []
    for i in range(weeks * 7):
        d = today - timedelta(days=i)
        trace_file = QUALITY_TRACES_DIR / f"{d.isoformat()}.jsonl"
        if trace_file.exists():
            records = _parse_json_or_jsonl(trace_file)
            all_records.extend([r for r in records if isinstance(r, dict) and "_parseError" not in r])

    # Filter to traces with strategy tag and actualOutcome
    tagged = [r for r in all_records if r.get("strategy") and r.get("actualOutcome")]
    if filter_kc:
        tagged = [r for r in tagged if filter_kc in r.get("kcTargets", [])]

    if len(tagged) < 2:
        result = {
            "status": "ok",
            "message": "Not enough strategy-tagged traces with actualOutcome for comparison. Tag traces with --strategy and include --actual-outcome at close.",
            "tracesFound": len(tagged),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Group by strategy
    by_strategy = defaultdict(list)
    for r in tagged:
        by_strategy[r["strategy"]].append(r)

    strategies = []
    for strat_name, traces in sorted(by_strategy.items()):
        total = len(traces)
        matched = sum(1 for t in traces if t.get("outcomeMatched") is True)
        failed = sum(1 for t in traces if t.get("outcomeMatched") is False)
        unknown = total - matched - failed
        success_rate = matched / max(total - unknown, 1) if (total - unknown) > 0 else None
        avg_confidence = sum(t.get("confidence", 0) for t in traces) / total if total > 0 else 0

        # Per-KC breakdown
        kc_results = defaultdict(lambda: {"total": 0, "matched": 0, "failed": 0})
        for t in traces:
            for kc in t.get("kcTargets", []):
                kc_results[kc]["total"] += 1
                if t.get("outcomeMatched") is True:
                    kc_results[kc]["matched"] += 1
                elif t.get("outcomeMatched") is False:
                    kc_results[kc]["failed"] += 1

        kc_breakdown = {}
        for kc, counts in sorted(kc_results.items()):
            kc_evaluated = counts["matched"] + counts["failed"]
            kc_rate = counts["matched"] / kc_evaluated if kc_evaluated > 0 else None
            kc_breakdown[kc] = {
                "total": counts["total"],
                "successRate": round(kc_rate, 3) if kc_rate is not None else None,
                "matched": counts["matched"],
                "failed": counts["failed"],
            }

        # Student engagement by strategy
        eng_counts = Counter(t.get("studentEngagement") for t in traces if t.get("studentEngagement"))

        strategies.append({
            "strategy": strat_name,
            "totalTraces": total,
            "successRate": round(success_rate, 3) if success_rate is not None else None,
            "matched": matched,
            "failed": failed,
            "unknown": unknown,
            "avgConfidence": round(avg_confidence, 3),
            "perKC": kc_breakdown,
            "engagement": dict(eng_counts.most_common()),
        })

    # Determine winner per KC
    kc_winners = {}
    all_kcs = set()
    for s in strategies:
        all_kcs.update(s["perKC"].keys())
    for kc in all_kcs:
        best_strat = None
        best_rate = -1
        for s in strategies:
            kc_data = s["perKC"].get(kc)
            if kc_data and kc_data["successRate"] is not None and kc_data["successRate"] > best_rate:
                best_rate = kc_data["successRate"]
                best_strat = s["strategy"]
        if best_strat:
            kc_winners[kc] = {"bestStrategy": best_strat, "successRate": best_rate}

    # Overall winner
    overall_winner = max(strategies, key=lambda s: s["successRate"] or -1) if strategies else None

    result = {
        "status": "ok",
        "strategies": strategies,
        "kcWinners": kc_winners,
        "overallBest": {
            "strategy": overall_winner["strategy"],
            "successRate": overall_winner["successRate"],
        } if overall_winner else None,
        "recommendation": f"Use strategy '{overall_winner['strategy']}' for best outcomes." if overall_winner else "Tag more traces with --strategy to enable comparison.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_quality_weekly_digest(args):
    """Generate a weekly teaching quality digest from trace files."""
    week_key = args.week
    if not week_key:
        from datetime import timedelta
        today = date.today()
        iso = today.isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"

    # Parse week into date range
    import re
    m = re.match(r"(\d{4})-W(\d{2})", week_key)
    if not m:
        print(json.dumps({"status": "error", "message": f"Invalid week format: {week_key}. Use YYYY-Www."}, ensure_ascii=False))
        return 1

    year, week_num = int(m.group(1)), int(m.group(2))
    from datetime import timedelta
    # ISO week 1 is the week containing Jan 4
    jan4 = date(year, 1, 4)
    monday = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week_num - 1)
    sunday = monday + timedelta(days=6)

    # Collect traces for each day
    all_records = []
    errors_by_day = {}
    d = monday
    while d <= sunday:
        trace_file = QUALITY_TRACES_DIR / f"{d.isoformat()}.jsonl"
        if trace_file.exists():
            records = _parse_json_or_jsonl(trace_file)
            valid = [r for r in records if isinstance(r, dict) and "_parseError" not in r]
            malformed = len(records) - len(valid)
            all_records.extend(valid)
            if malformed > 0:
                errors_by_day[d.isoformat()] = malformed
        d += timedelta(days=1)

    if not all_records:
        _ensure_dir(QUALITY_RECOMMENDATIONS_DIR)
        out_path = QUALITY_RECOMMENDATIONS_DIR / f"weekly-{week_key}.md"
        out_path.write_text(
            f"# Weekly Digest — {week_key}\n\n"
            f"**No teaching sessions this week.**\n\n"
            f"Start a session with your IELTS teacher to begin tracking.\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "ok", "week": week_key, "totalTraces": 0, "report": str(out_path), "message": "No sessions this week"}, ensure_ascii=False, indent=2))
        return 0

    # Decision type distribution
    from collections import Counter
    decision_counts = Counter(r.get("decisionType") for r in all_records)
    skill_counts = Counter(r.get("skill") for r in all_records)
    kc_all = [kc for r in all_records for kc in r.get("kcTargets", [])]
    kc_counts = Counter(kc_all)

    # Trace completeness
    expected_fields = {
        "schemaVersion", "runId", "timestamp", "skill", "decisionType",
        "evidenceRefs", "rubricRefs", "kcTargets", "action",
        "expectedOutcome", "confidence", "sourceVersion",
    }
    complete_count = sum(
        1 for r in all_records if expected_fields.issubset(r.keys())
    )
    completeness = complete_count / len(all_records) if all_records else 0

    # ── v2: calibration analysis ──
    evaluated = [r for r in all_records if r.get("actualOutcome")]
    calibrated = 0
    overconfident = 0
    underconfident = 0
    calibration_score_total = 0.0
    for r in evaluated:
        conf = r.get("confidence", 0.5)
        matched = r.get("outcomeMatched")
        if matched is True:
            calibration_score_total += conf  # right to be confident
            calibrated += 1
        elif matched is False:
            calibration_score_total += (1 - conf)  # should have been less confident
            if conf >= 0.7:
                overconfident += 1
            else:
                underconfident += 1
    cal_score = calibration_score_total / len(evaluated) if evaluated else None

    # ── Trend: compare with previous week ──
    prev_week_num = week_num - 1
    prev_year = year
    if prev_week_num < 1:
        prev_year -= 1
        prev_week_num = 52  # approximate — ISO weeks are 52 or 53
    prev_week_key = f"{prev_year}-W{prev_week_num:02d}"
    prev_json = QUALITY_RECOMMENDATIONS_DIR / f"weekly-{prev_week_key}.json"
    trend = None
    if prev_json.exists():
        prev = _load_json(prev_json)
        if prev and prev.get("totalTraces", 0) > 0:
            delta = len(all_records) - prev["totalTraces"]
            pct = (delta / prev["totalTraces"]) * 100 if prev["totalTraces"] else 0
            trend = {
                "previousWeek": prev_week_key,
                "previousTotal": prev["totalTraces"],
                "delta": delta,
                "deltaPct": round(pct, 1),
                "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
            }

    # ── KC heatmap: attention vs gaps ──
    # Load KC taxonomy to detect neglected KCs
    kc_taxonomy = _load_json(KC_GRAPH_FILE, {})
    all_kc_ids = set()
    if isinstance(kc_taxonomy, dict) and "kcs" in kc_taxonomy:
        all_kc_ids = {kc.get("id", "") for kc in kc_taxonomy["kcs"] if kc.get("id")}
    tested_kc_ids = set(kc_counts.keys())
    neglected_kcs = sorted(all_kc_ids - tested_kc_ids)
    top_kcs = [{"kc": kc, "count": c} for kc, c in kc_counts.most_common(10)]

    # ── Actionable recommendations ──
    recommendations = []
    # Completeness
    if completeness < 0.8:
        recommendations.append({
            "priority": "high",
            "area": "traceCompleteness",
            "message": f"Trace completeness is {completeness:.0%} — below 80% threshold. Ensure every phase emits a trace record.",
        })
    # Decision balance: diagnose without plan/teach/evaluate is reactive
    diagnose_n = decision_counts.get("diagnose", 0)
    plan_n = decision_counts.get("plan", 0)
    teach_n = decision_counts.get("teach", 0)
    evaluate_n = decision_counts.get("evaluate", 0)
    close_n = decision_counts.get("close", 0)
    if diagnose_n > 0 and (plan_n == 0 or teach_n == 0):
        recommendations.append({
            "priority": "high",
            "area": "decisionBalance",
            "message": f"{diagnose_n} diagnoses but {plan_n} plans, {teach_n} teachings. Diagnoses without follow-through don't improve student outcomes.",
        })
    # Calibration
    if evaluated and cal_score is not None:
        if cal_score < 0.6:
            recommendations.append({
                "priority": "high",
                "area": "calibration",
                "message": f"Calibration score {cal_score:.2f} — teacher confidence is poorly aligned with actual outcomes. Consider lowering confidence or improving diagnosis accuracy.",
            })
        if overconfident > 0:
            recommendations.append({
                "priority": "medium",
                "area": "calibration",
                "message": f"{overconfident} overconfident decisions (confidence ≥ 0.7 but outcome didn't match). Review these traces in the JSON summary.",
            })
    # Neglected KCs
    if neglected_kcs:
        sample = neglected_kcs[:5]
        recommendations.append({
            "priority": "medium",
            "area": "kcCoverage",
            "message": f"{len(neglected_kcs)} KCs have never been tested. Examples: {', '.join(sample)}. Consider broadening coverage.",
        })
    # Outcome evaluation gaps
    unevaluated = len(all_records) - len(evaluated)
    if unevaluated > 0:
        recommendations.append({
            "priority": "low",
            "area": "outcomeEvaluation",
            "message": f"{unevaluated} traces have no actualOutcome. Use trace-evaluate at session close to close the feedback loop.",
        })

    # ── TQS: Teacher Quality Score (0-100 composite) ──
    # Components: calibration(30) + completeness(25) + follow-through(20)
    #             + outcome-eval(15) + session-hygiene(10)
    tqs_cal = (cal_score or 0.5) * 30  # 0-30
    tqs_comp = completeness * 25  # 0-25
    tqs_follow = (min(teach_n / max(diagnose_n, 1), 1.0)) * 20  # 0-20
    tqs_outcome = (len(evaluated) / max(len(all_records), 1)) * 15  # 0-15
    tqs_hygiene = (min(close_n / max(max(diagnose_n, plan_n, teach_n, evaluate_n) / 4, 1), 1.0)) * 10  # 0-10
    tqs = round(tqs_cal + tqs_comp + tqs_follow + tqs_outcome + tqs_hygiene, 1)

    tqs_breakdown = {
        "total": tqs,
        "components": {
            "calibration": {"score": round(tqs_cal, 1), "weight": 30, "details": f"cal_score={cal_score}" if cal_score else "no evaluated traces"},
            "completeness": {"score": round(tqs_comp, 1), "weight": 25, "details": f"{completeness:.0%} field coverage"},
            "followThrough": {"score": round(tqs_follow, 1), "weight": 20, "details": f"teach/diagnose = {teach_n}/{diagnose_n}"},
            "outcomeEvaluation": {"score": round(tqs_outcome, 1), "weight": 15, "details": f"{len(evaluated)}/{len(all_records)} evaluated"},
            "sessionHygiene": {"score": round(tqs_hygiene, 1), "weight": 10, "details": f"{close_n} close traces"},
        },
    }

    tqs_grade = "A" if tqs >= 80 else ("B" if tqs >= 65 else ("C" if tqs >= 50 else ("D" if tqs >= 35 else "F")))
    tqs_grade_label = {
        "A": "Excellent — well-calibrated, complete, high follow-through",
        "B": "Good — solid teaching with some gaps",
        "C": "Fair — needs improvement in 2+ areas",
        "D": "Weak — significant gaps in teaching quality",
        "F": "Critical — teaching loop is broken, fix fundamentals first",
    }[tqs_grade]

    if tqs < 50:
        recommendations.append({
            "priority": "high",
            "area": "teacherQuality",
            "message": f"TQS is {tqs} (Grade {tqs_grade}). Focus on the lowest component scores to improve teaching quality.",
        })

    # ── Write JSON summary ──
    _ensure_dir(QUALITY_RECOMMENDATIONS_DIR)
    json_path = QUALITY_RECOMMENDATIONS_DIR / f"weekly-{week_key}.json"
    summary = {
        "week": week_key,
        "range": f"{monday.isoformat()} to {sunday.isoformat()}",
        "totalTraces": len(all_records),
        "traceCompleteness": round(completeness, 3),
        "decisionDistribution": dict(decision_counts.most_common()),
        "skillDistribution": dict(skill_counts.most_common()),
        "topKCs": top_kcs,
        "neglectedKCs": neglected_kcs[:20],
        "malformedRecords": {k: v for k, v in errors_by_day.items()},
        "calibration": {
            "evaluatedTraces": len(evaluated),
            "calibrationScore": round(cal_score, 3) if cal_score is not None else None,
            "calibratedCount": calibrated,
            "overconfidentCount": overconfident,
            "underconfidentCount": underconfident,
        },
        "teacherQualityScore": {
            "score": tqs,
            "grade": tqs_grade,
            "gradeLabel": tqs_grade_label,
            "breakdown": tqs_breakdown["components"],
        },
        "trend": trend,
        "recommendations": recommendations,
        "generatedAt": _now(),
    }
    _save_json(json_path, summary)

    # ── Write Markdown report ──
    md_path = QUALITY_RECOMMENDATIONS_DIR / f"weekly-{week_key}.md"
    lines = [
        f"# Weekly Digest — {week_key}",
        f"**{monday.isoformat()} to {sunday.isoformat()}**",
        "",
        f"## Overview",
        f"- **Total teaching decisions:** {len(all_records)}",
        f"- **Trace completeness:** {completeness:.1%}",
    ]
    if trend:
        dir_icon = "📈" if trend["direction"] == "up" else ("📉" if trend["direction"] == "down" else "➡️")
        lines.append(f"- **vs last week:** {dir_icon} {trend['deltaPct']:+.1f}% ({trend['delta']:+d} traces)")
    lines.append(f"- **Skills:** {', '.join(f'{k} ({v})' for k, v in skill_counts.most_common())}")
    lines.extend([
        "",
        f"## Decision Distribution",
    ])
    for dt, count in decision_counts.most_common():
        lines.append(f"- **{dt}:** {count}")
    if evaluate_n == 0 and close_n > 0:
        lines.append("")
        lines.append("⚠️ **Missing evaluate phase** — sessions close without evaluating outcomes. This breaks the feedback loop.")

    lines.extend([
        "",
        f"## Top KCs Tested",
    ])
    for kc, count in kc_counts.most_common(10):
        lines.append(f"- `{kc}`: {count}")
    if neglected_kcs:
        lines.extend([
            "",
            f"## ⚠️ Neglected KCs ({len(neglected_kcs)} never tested)",
        ])
        for kc in neglected_kcs[:10]:
            lines.append(f"- `{kc}`")

    # Calibration section
    if evaluated:
        lines.extend([
            "",
            f"## 🎯 Calibration",
            f"- **Evaluated traces:** {len(evaluated)}/{len(all_records)}",
            f"- **Calibration score:** {cal_score:.2f}" if cal_score is not None else "- **Calibration score:** N/A",
        ])
        if overconfident:
            lines.append(f"- **Overconfident decisions:** {overconfident} (confidence ≥ 0.7, outcome failed)")
        if calibrated:
            lines.append(f"- **Well-calibrated decisions:** {calibrated}")

    # ── TQS section ──
    tqs_icon = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🟠", "F": "🔴"}[tqs_grade]
    lines.extend([
        "",
        f"## {tqs_icon} Teacher Quality Score: {tqs}/100 (Grade {tqs_grade})",
        f"*{tqs_grade_label}*",
        "",
        f"| Component | Score | Weight |",
        f"|-----------|-------|--------|",
        f"| Calibration | {tqs_breakdown['components']['calibration']['score']}/30 | 30% |",
        f"| Completeness | {tqs_breakdown['components']['completeness']['score']}/25 | 25% |",
        f"| Follow-through | {tqs_breakdown['components']['followThrough']['score']}/20 | 20% |",
        f"| Outcome Eval | {tqs_breakdown['components']['outcomeEvaluation']['score']}/15 | 15% |",
        f"| Session Hygiene | {tqs_breakdown['components']['sessionHygiene']['score']}/10 | 10% |",
    ])

    # Recommendations
    if recommendations:
        lines.extend([
            "",
            f"## 💡 Recommendations",
        ])
        for rec in recommendations:
            prio = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(rec["priority"], "⚪")
            lines.append(f"- {prio} **[{rec['area']}]** {rec['message']}")

    if errors_by_day:
        lines.extend([
            "",
            f"## ⚠️ Malformed Records",
        ])
        for day, n in errors_by_day.items():
            lines.append(f"- {day}: {n} malformed trace(s) skipped")
    lines.extend([
        "",
        f"---",
        f"*Generated {_now()}*",
    ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "week": week_key,
        "totalTraces": len(all_records),
        "traceCompleteness": round(completeness, 3),
        "teacherQualityScore": {"score": tqs, "grade": tqs_grade},
        "report": str(md_path),
        "jsonSummary": str(json_path),
    }, ensure_ascii=False, indent=2))
    return 0


# ── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="IELTS Claude Teacher — Data Layer CLI")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sub.add_parser("init", help="Initialize .ielts/ directory structure")

    # migrate-profile
    sub.add_parser("migrate-profile", help="Migrate roadmap.json → student-profile.json v2")

    # validate
    sub.add_parser("validate", help="Validate data integrity (profile + KC graph)")

    # settings
    p_settings = sub.add_parser("settings", help="Settings management")
    p_settings_sub = p_settings.add_subparsers(dest="settings_action")
    p_settings_sub.add_parser("get", help="Read settings")
    p_set = p_settings_sub.add_parser("set", help="Update settings")
    p_set.add_argument("--language", choices=["vi", "en", "zh"])
    p_set.add_argument("--teacher-name")
    p_set.add_argument("--teacher-personality")

    # backup
    sub.add_parser("backup", help="Create zip backup of .ielts/")

    # status
    sub.add_parser("status", help="Show brief status summary")

    # lesson-library
    p_ll = sub.add_parser("lesson-library", help="Lesson library management")
    p_ll_sub = p_ll.add_subparsers(dest="ll_action")
    p_ll_sub.add_parser("list", help="List all lessons")
    p_ll_sub.add_parser("sync", help="Scan lesson-plans/ and rebuild library")
    p_ll_add = p_ll_sub.add_parser("add", help="Add a lesson entry")
    p_ll_add.add_argument("--id", required=True, help="Lesson ID (e.g., lesson-20260713-001)")
    p_ll_add.add_argument("--title", required=True, help="Lesson title")
    p_ll_add.add_argument("--skill", required=True, choices=["reading", "listening", "writing", "speaking", "general"])
    p_ll_add.add_argument("--file", required=True, help="Relative path to HTML file")
    p_ll_add.add_argument("--kc-tags", help="Comma-separated KC tag IDs")
    p_ll_add.add_argument("--date", help="Creation date (ISO format)")
    p_ll_add.add_argument("--source", help="Source (generated/cambridge/manual)")
    p_ll_add.add_argument("--trigger-error", help="Error that triggered this lesson")
    p_ll_mark = p_ll_sub.add_parser("mark-used", help="Increment timesUsed for a lesson")
    p_ll_mark.add_argument("--id", required=True, help="Lesson ID")

    # reset-profile
    p_reset = sub.add_parser("reset-profile", help="Factory reset student-profile.json to initial state")
    p_reset.add_argument("--yes", action="store_true", help="Confirm reset (required — one-way operation)")
    p_reset.add_argument("--target-band", type=float, help="Target band for new profile (default: preserve from old)")
    p_reset.add_argument("--exam-date", help="Exam date for new profile (default: preserve from old)")

    # memory
    p_mem = sub.add_parser("memory", help="Coach memory management")
    p_mem_sub = p_mem.add_subparsers(dest="memory_action")
    p_mem_add = p_mem_sub.add_parser("add", help="Append a coach note to student-profile.json")
    p_mem_add.add_argument("--content", required=True, help="Note content")
    p_mem_add.add_argument("--category", default="observation", choices=["system", "observation", "weakness", "strength", "strategy"])
    p_mem_add.add_argument("--skill", default="general", choices=["general", "listening", "reading", "writing", "speaking"])
    p_mem_add.add_argument("--priority", default="medium", choices=["high", "medium", "low"])

    # migrate-lesson-library (one-time)
    sub.add_parser("migrate-lesson-library", help="Migrate lessonLibrary from student-profile.json to standalone file")

    # vocab
    p_vocab = sub.add_parser("vocab", help="Vocabulary management with SRS")
    p_vocab_sub = p_vocab.add_subparsers(dest="vocab_action")
    p_vocab_add = p_vocab_sub.add_parser("add", help="Add or update a word with SRS tracking")
    p_vocab_add.add_argument("--word", required=True, help="The misspelled word")
    p_vocab_add.add_argument("--correct", help="Correct spelling")
    p_vocab_add.add_argument("--source", choices=["listening", "reading", "writing", "speaking", "unknown"])
    p_vocab_add.add_argument("--context", help="Where the error occurred")
    p_vocab_review = p_vocab_sub.add_parser("review", help="Update SRS after reviewing a word")
    p_vocab_review.add_argument("--word", required=True)
    p_vocab_review.add_argument("--passed", type=lambda x: x.lower() == 'true', default=True)

    # synonym
    p_synonym = sub.add_parser("synonym", help="Synonym pair management")
    p_synonym_sub = p_synonym.add_subparsers(dest="synonym_action")
    p_syn_add = p_synonym_sub.add_parser("add", help="Add a synonym pair")
    p_syn_add.add_argument("--word", required=True, help="Original word")
    p_syn_add.add_argument("--synonym", required=True, help="Synonym/paraphrase")
    p_syn_add.add_argument("--context", help="Where the synonym was found")

    # quality
    p_quality = sub.add_parser("quality", help="Quality control plane (W1 scaffold)")
    p_quality_sub = p_quality.add_subparsers(dest="quality_action")

    p_quality_sub.add_parser("init", help="Initialize .ielts/quality scaffold")

    p_manifest = p_quality_sub.add_parser("run-manifest", help="Create run manifest")
    p_manifest.add_argument("--run-id", help="Run identifier (optional)")
    p_manifest.add_argument("--lane", default="reading", help="Lane name, e.g. reading")
    p_manifest.add_argument(
        "--trigger",
        default="manual",
        choices=["manual", "pr", "nightly"],
        help="Trigger source",
    )
    p_manifest.add_argument("--source-version", default="unknown", help="Prompt/policy snapshot version")
    p_manifest.add_argument("--correlation-id", help="Correlation ID override")
    p_manifest.add_argument("--dedupe-key", help="Optional idempotency key")

    p_baseline = p_quality_sub.add_parser("baseline-record", help="Record baseline metric values")
    p_baseline.add_argument("--lane", default="reading")
    p_baseline.add_argument("--run-id", required=True)
    p_baseline.add_argument("--trace-completeness", type=float, required=True)
    p_baseline.add_argument("--replay-pass-rate", type=float, required=True)
    p_baseline.add_argument("--content-fidelity-error-rate", type=float, required=True)
    p_baseline.add_argument("--mttd-hours", type=float, required=True)
    p_baseline.add_argument("--mttp-hours", type=float, required=True)
    p_baseline.add_argument("--notes", help="Optional note")

    p_trace = p_quality_sub.add_parser("trace-validate", help="Validate trace JSON/JSONL file")
    p_trace.add_argument("--file", required=True, help="Path to trace input file")
    p_trace.add_argument("--run-id", help="Optional run ID to enforce manifest lineage")

    p_report = p_quality_sub.add_parser("report-only", help="Generate report-only gate artifacts from metrics")
    p_report.add_argument("--run-id", required=True)
    p_report.add_argument("--trace-completeness", type=float, required=True)
    p_report.add_argument("--replay-pass-rate", type=float, required=True)
    p_report.add_argument("--content-fidelity-error-rate", type=float, required=True)
    p_report.add_argument("--sample-size", type=int, required=True)
    p_report.add_argument("--mode", choices=["report-only", "soft-gate", "hard-gate", "auto"], default="report-only")
    p_report.add_argument("--coverage-file", help="Optional JSON coverage metrics file for guardrail checks")
    p_report.add_argument("--performance-file", help="Optional JSON performance metrics file for budget checks")

    p_gateset = p_quality_sub.add_parser("gateset-register", help="Register immutable gate set snapshot")
    p_gateset.add_argument("--lane", default="reading", choices=["reading", "listening", "writing", "speaking"])
    p_gateset.add_argument("--evalset-id", required=True, help="Gate set identifier, e.g. evalset-v1")
    p_gateset.add_argument("--file", required=True, help="Source JSON/JSONL file for gate cases")
    p_gateset.add_argument("--source-version", default="unknown", help="Source version tag for audit lineage")

    # -- trace-emit: called by teacher from SKILL.md at each phase boundary
    p_trace_emit = p_quality_sub.add_parser("trace-emit", help="Emit one decision trace record from the teaching loop")
    p_trace_emit.add_argument("--skill", required=True, choices=["reading", "listening", "writing", "speaking", "general"])
    p_trace_emit.add_argument("--decision-type", required=True, choices=["diagnose", "plan", "teach", "evaluate", "close"])
    p_trace_emit.add_argument("--evidence-refs", default="", help="Comma-separated evidence references")
    p_trace_emit.add_argument("--rubric-refs", default="", help="Comma-separated rubric references")
    p_trace_emit.add_argument("--kc-targets", default="", help="Comma-separated KC IDs")
    p_trace_emit.add_argument("--action", required=True, help="One-line description of the decision")
    p_trace_emit.add_argument("--expected-outcome", required=True, help="What should improve")
    p_trace_emit.add_argument("--confidence", type=float, required=True, help="Confidence in [0,1]")
    p_trace_emit.add_argument("--source-version", help="Prompt/policy snapshot version")
    p_trace_emit.add_argument("--run-id", help="Session run ID (auto-generated if omitted)")
    # v2: closed-loop outcome evaluation
    p_trace_emit.add_argument("--actual-outcome", help="What actually happened (v2+)")
    p_trace_emit.add_argument("--outcome-matched", choices=["true", "false"], help="Did outcome match expected? true/false (v2+)")
    p_trace_emit.add_argument("--outcome-note", help="Why did/didn't the outcome match? (v2+)")
    p_trace_emit.add_argument("--schema-version", default="trace-v3", choices=["trace-v1", "trace-v2", "trace-v3"], help="Trace schema version")
    # v3: student response + strategy
    p_trace_emit.add_argument("--student-response", help="What did the student say or do? (v3)")
    p_trace_emit.add_argument("--student-engagement", choices=["high", "medium", "low"], help="Student engagement level (v3)")
    p_trace_emit.add_argument("--student-confusion", help="What specifically confused the student? (v3)")
    p_trace_emit.add_argument("--strategy", help="Teaching strategy tag for A/B comparison (v3)")
    p_trace_emit.add_argument("--teacher-transcript", help="Verbatim teacher response text for GEval scoring (v4)")

    # -- trace-evaluate: summarize expected outcomes for a session to guide close evaluation
    p_trace_eval = p_quality_sub.add_parser("trace-evaluate", help="Summarize expected outcomes for a run to guide close evaluation")
    p_trace_eval.add_argument("--run-id", required=True, help="Session run ID to evaluate")
    p_trace_eval.add_argument("--date", help="Date override (default: today)")

    # -- prompt-tune: analyze traces and suggest SKILL.md improvements
    p_prompt_tune = p_quality_sub.add_parser("prompt-tune", help="Analyze traces and suggest SKILL.md teaching improvements")
    p_prompt_tune.add_argument("--weeks", type=int, default=4, help="Number of weeks of trace data to analyze (default: 4)")
    p_prompt_tune.add_argument("--output", help="Write suggestions to file instead of stdout")

    # -- strategy-compare: A/B compare teaching strategies
    p_strategy = p_quality_sub.add_parser("strategy-compare", help="Compare teaching strategies by outcome")
    p_strategy.add_argument("--kc", help="Filter to a specific KC ID")
    p_strategy.add_argument("--weeks", type=int, default=8, help="Number of weeks to analyze (default: 8)")

    # -- weekly-digest: aggregate weekly traces into human-readable report
    p_digest = p_quality_sub.add_parser("weekly-digest", help="Generate weekly teaching quality digest from traces")
    p_digest.add_argument("--week", help="Week key in YYYY-Www format (default: current week)")

    p_override = p_quality_sub.add_parser("override-validate", help="Validate emergency override request")
    p_override.add_argument("--file", required=True, help="Override request JSON file")

    p_approval_mode = p_quality_sub.add_parser("gate-approval-mode", help="Get/set soft-gate approval mode")
    p_approval_mode.add_argument("--set-mode", choices=["founder_approval", "auto_accepts"], help="Set approval mode")

    p_ack = p_quality_sub.add_parser("gate-acknowledge", help="Founder acknowledge yellow/red soft-gate")
    p_ack.add_argument("--run-id", required=True)
    p_ack.add_argument("--approved-by", required=True)
    p_ack.add_argument("--note", help="Optional acknowledgement note")

    p_budget = p_quality_sub.add_parser("budget-validate", help="Validate performance metrics against budget")
    p_budget.add_argument("--file", required=True, help="Performance metrics JSON file")

    p_w3 = p_quality_sub.add_parser("week3-checkpoint", help="Evaluate Week-3 acceptance checkpoint")
    p_w3.add_argument("--run-id", required=True)

    p_incident = p_quality_sub.add_parser("incident-dry-run", help="Run end-to-end incident simulation")
    p_incident.add_argument("--run-id", required=True)
    p_incident.add_argument("--decision", choices=["override", "reject"], required=True)
    p_incident.add_argument("--adjudicator", default="founder")
    p_incident.add_argument("--reason", help="Reason for adjudication")
    p_incident.add_argument("--override-file", help="Required when decision=override")

    p_publish = p_quality_sub.add_parser("artifact-publish", help="Lock published run artifacts (append-only)")
    p_publish.add_argument("--run-id", required=True)
    p_publish.add_argument("--published-by", help="Publisher identifier")

    p_phase = p_quality_sub.add_parser("phase-gate", help="Manage phase sequencing gates")
    p_phase.add_argument("--action", choices=["status", "check", "complete"], required=True)
    p_phase.add_argument("--phase", choices=["w1", "w2", "w3", "w4"], help="Phase name")
    p_phase.add_argument("--owner", help="Owner for completion record")
    p_phase.add_argument("--note", help="Completion note")

    p_kt = p_quality_sub.add_parser("kt-pack-update", help="Update KT maintenance artifacts")
    p_kt.add_argument("--phase", required=True)
    p_kt.add_argument("--summary", required=True)
    p_kt.add_argument("--note", help="Optional onboarding note")

    p_weekly = p_quality_sub.add_parser("weekly-review-log", help="Write weekly review summary")
    p_weekly.add_argument("--week-key", help="ISO week key, e.g. 2026-W31")
    p_weekly.add_argument("--achieved", required=True)
    p_weekly.add_argument("--misses", required=True)
    p_weekly.add_argument("--risks", required=True)
    p_weekly.add_argument("--commitments", required=True)
    p_weekly.add_argument("--overwrite", action="store_true")

    p_shadow = p_quality_sub.add_parser("shadow-dry-run", help="Run read-only shadow lane sample and disagreement report")
    p_shadow.add_argument("--run-id", required=True)
    p_shadow.add_argument("--lane", help="Shadow lane name, default from policy")
    p_shadow.add_argument("--file", required=True, help="Shadow comparison JSON input")
    p_shadow.add_argument("--sample-slice-ratio", type=float, help="Override policy ratio in (0,1]")

    p_shadow_weekly = p_quality_sub.add_parser("shadow-weekly-report", help="Aggregate weekly shadow disagreement trend")
    p_shadow_weekly.add_argument("--week-key", help="ISO week key e.g. 2026-W31")

    p_schema_compat = p_quality_sub.add_parser("schema-compat-check", help="Validate artifact compatibility and schema evolution")
    p_schema_compat.add_argument("--artifact-type", choices=["trace", "eval"], help="Artifact type for --file mode")
    p_schema_compat.add_argument("--file", help="Artifact JSON/JSONL file to validate")
    p_schema_compat.add_argument("--old-schema", help="Old schema JSON for evolution check")
    p_schema_compat.add_argument("--new-schema", help="New schema JSON for evolution check")

    p_gate_mode = p_quality_sub.add_parser("gate-mode-switch", help="Get/set active gate mode config")
    p_gate_mode.add_argument("--set-mode", choices=["report-only", "soft-gate", "hard-gate"], help="Set active gate mode")

    p_rehearsal = p_quality_sub.add_parser("hard-gate-rehearsal", help="Rehearse hard-gate activation and rollback")
    p_rehearsal.add_argument("--run-id", required=True)
    p_rehearsal.add_argument("--rollback-to", choices=["report-only", "soft-gate"], default="soft-gate")

    p_promote = p_quality_sub.add_parser("hard-gate-promotion-check", help="Check promotion criteria and optionally activate hard-gate")
    p_promote.add_argument("--approved-by", help="Founder approver ID")
    p_promote.add_argument("--promote", action="store_true", help="Activate hard-gate when promotable")

    # create-full-test
    p_full_test = sub.add_parser("create-full-test", help="Generate a full mock test with 4 skills in tabs")
    p_full_test.add_argument("--random", action="store_true", default=True,
                             help="Randomly select sections (default: True)")
    p_full_test.add_argument("--seed", type=int, default=None,
                             help="Random seed for reproducible selection")
    p_full_test.add_argument("--force", action="store_true",
                             help="Overwrite existing output file")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init":
        return cmd_init()
    elif args.command == "migrate-profile":
        return cmd_migrate_profile()
    elif args.command == "validate":
        return cmd_validate()
    elif args.command == "settings":
        if args.settings_action == "get":
            return cmd_settings_get()
        elif args.settings_action == "set":
            return cmd_settings_set(args)
        else:
            print("Usage: ielts_cli.py settings [get|set]")
            return 1
    elif args.command == "backup":
        return cmd_backup()
    elif args.command == "status":
        return cmd_status()
    elif args.command == "lesson-library":
        if args.ll_action == "list":
            return cmd_lesson_library_list()
        elif args.ll_action == "sync":
            return cmd_lesson_library_sync()
        elif args.ll_action == "add":
            return cmd_lesson_library_add(args)
        elif args.ll_action == "mark-used":
            return cmd_lesson_library_mark_used(args)
        else:
            print("Usage: ielts_cli.py lesson-library [list|sync|add|mark-used]")
            return 1
    elif args.command == "memory":
        if args.memory_action == "add":
            return cmd_memory_add(args)
        else:
            print("Usage: ielts_cli.py memory add --content \"...\" --category ... --skill ... --priority ...")
            return 1
    elif args.command == "reset-profile":
        return cmd_reset_profile(args)
    elif args.command == "vocab":
        if args.vocab_action == "add":
            return cmd_vocab_add(args)
        elif args.vocab_action == "review":
            return cmd_vocab_review(args)
        else:
            print("Usage: ielts_cli.py vocab [add|review]")
            return 1
    elif args.command == "synonym":
        if args.synonym_action == "add":
            return cmd_synonym_add(args)
        else:
            print("Usage: ielts_cli.py synonym add --word ... --synonym ... --context ...")
            return 1
    elif args.command == "quality":
        if args.quality_action == "init":
            return cmd_quality_init()
        elif args.quality_action == "run-manifest":
            return cmd_quality_run_manifest(args)
        elif args.quality_action == "baseline-record":
            return cmd_quality_baseline_record(args)
        elif args.quality_action == "trace-validate":
            return cmd_quality_trace_validate(args)
        elif args.quality_action == "report-only":
            return cmd_quality_report_only(args)
        elif args.quality_action == "gateset-register":
            return cmd_quality_gateset_register(args)
        elif args.quality_action == "override-validate":
            return cmd_quality_override_validate(args)
        elif args.quality_action == "gate-approval-mode":
            return cmd_quality_gate_approval_mode(args)
        elif args.quality_action == "gate-acknowledge":
            return cmd_quality_gate_acknowledge(args)
        elif args.quality_action == "trace-emit":
            return cmd_quality_trace_emit(args)
        elif args.quality_action == "trace-evaluate":
            return cmd_quality_trace_evaluate(args)
        elif args.quality_action == "prompt-tune":
            return cmd_quality_prompt_tune(args)
        elif args.quality_action == "strategy-compare":
            return cmd_quality_strategy_compare(args)
        elif args.quality_action == "weekly-digest":
            return cmd_quality_weekly_digest(args)
        elif args.quality_action == "budget-validate":
            return cmd_quality_budget_validate(args)
        elif args.quality_action == "week3-checkpoint":
            return cmd_quality_week3_checkpoint(args)
        elif args.quality_action == "incident-dry-run":
            return cmd_quality_incident_dry_run(args)
        elif args.quality_action == "artifact-publish":
            return cmd_quality_artifact_publish(args)
        elif args.quality_action == "phase-gate":
            return cmd_quality_phase_gate(args)
        elif args.quality_action == "kt-pack-update":
            return cmd_quality_kt_pack_update(args)
        elif args.quality_action == "weekly-review-log":
            return cmd_quality_weekly_review_log(args)
        elif args.quality_action == "shadow-dry-run":
            return cmd_quality_shadow_dry_run(args)
        elif args.quality_action == "shadow-weekly-report":
            return cmd_quality_shadow_weekly_report(args)
        elif args.quality_action == "schema-compat-check":
            return cmd_quality_schema_compat_check(args)
        elif args.quality_action == "gate-mode-switch":
            return cmd_quality_gate_mode_switch(args)
        elif args.quality_action == "hard-gate-rehearsal":
            return cmd_quality_hard_gate_rehearsal(args)
        elif args.quality_action == "hard-gate-promotion-check":
            return cmd_quality_hard_gate_promotion_check(args)
        else:
            print("Usage: ielts_cli.py quality [init|run-manifest|baseline-record|trace-validate|report-only|gateset-register|override-validate|gate-approval-mode|gate-acknowledge|budget-validate|week3-checkpoint|incident-dry-run|artifact-publish|phase-gate|kt-pack-update|weekly-review-log|shadow-dry-run|shadow-weekly-report|schema-compat-check|gate-mode-switch|hard-gate-rehearsal|hard-gate-promotion-check]")
            return 1
    elif args.command == "create-full-test":
        return cmd_create_full_test(args)
    elif args.command == "migrate-lesson-library":
        return cmd_migrate_lesson_library()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
