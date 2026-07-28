"""Shared fixtures and utilities for IELTS DeepEval tests.

Provides:
  - sys.path setup for importing shared/ielts_cli.py
  - KC graph loading from .ielts/kc-graph-ielts.json
  - Fresh profile builder using _build_fresh_profile
  - Formula implementations: error rate, level thresholds, SRS intervals
  - Priority algorithm reference implementation per SKILL.md Phase 2.5

Usage:
    from evals.conftest import (
        compute_error_rate, compute_level, compute_srs_next_review,
        compute_subjective_error_rate, compute_priority_score,
        load_kc_graph, build_kc_index, build_fresh_profile,
    )
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

# Resolve project root for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = str(PROJECT_ROOT / "shared")

# Insert at front so shared/ielts_cli.py is found first
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

# Now import from the project
from ielts_cli import (  # noqa: E402
    _build_fresh_profile,
    _load_json,
    _save_json,
    _today,
    _validate_trace_record,
    _validate_ref_list,
    emit_trace,
    _ensure_dir,
    PROJECT_ROOT as _CLI_PROJECT_ROOT,
    IELTS_DIR,
    KC_GRAPH_FILE,
    PROFILE_FILE,
    QUALITY_TRACES_DIR,
)


# ── KC Graph helpers ────────────────────────────────────────────────

def load_kc_graph() -> dict:
    """Load the KC graph from .ielts/kc-graph-ielts.json."""
    return _load_json(KC_GRAPH_FILE) or {}


def build_kc_index(kc_graph: dict | None = None) -> dict[str, dict]:
    """Build a flat {kc_id: kc_obj} index from the KC graph.

    Each kc_obj has: id, name, dependsOn, commonErrors, exerciseTemplates.
    """
    if kc_graph is None:
        kc_graph = load_kc_graph()
    index = {}
    for skill_name, skill_data in kc_graph.get("skills", {}).items():
        for kc in skill_data.get("kcs", []):
            index[kc["id"]] = kc
    return index


def build_fresh_profile(target_band: float = 6.0,
                        exam_date: str | None = None) -> dict:
    """Build a fresh student profile with all KCs at default state."""
    kc_graph = load_kc_graph()
    return _build_fresh_profile(kc_graph, target_band=target_band,
                                exam_date=exam_date)


# ── KC Mastery Formulas (SKILL.md Phase 5.3) ────────────────────────

def compute_error_rate(attempts: int, current_error_rate: float,
                       session_error_rate: float) -> float:
    """Cumulative error rate per SKILL.md Phase 5.3.

    new_errorRate = (attempts * errorRate + session_errorRate) / (attempts + 1)
    """
    if attempts < 0:
        attempts = 0
    return (attempts * current_error_rate + session_error_rate) / (attempts + 1)


def compute_level(error_rate: float) -> str:
    """Level threshold per SKILL.md Phase 5.3.

    >= 0.40 -> 'weak', 0.15-0.39 -> 'ok', < 0.15 -> 'mastered'
    """
    if error_rate >= 0.40:
        return "weak"
    elif error_rate >= 0.15:
        return "ok"
    else:
        return "mastered"


def compute_srs_next_review(attempts: int, last_tested_date: str) -> str:
    """Spaced repetition per SKILL.md Phase 5.3.

    1 -> 1 day, 2 -> 3 days, 3 -> 7 days, 4+ -> 30 days.
    """
    intervals = {1: 1, 2: 3, 3: 7}
    days = intervals.get(attempts, 30)
    d = date.fromisoformat(last_tested_date) + timedelta(days=days)
    return d.isoformat()


def compute_subjective_error_rate(target_band: float,
                                   scored_band: float) -> float:
    """Per SKILL.md: clamp((targetBand - scoredBand) / targetBand, 0, 1).

    If targetBand <= 0, returns 0 (skip KC update).
    """
    if target_band <= 0:
        return 0.0
    return max(0.0, min(1.0, (target_band - scored_band) / target_band))


# ── Priority Algorithm (SKILL.md Phase 2.5) ─────────────────────────

def compute_priority_score(kc_id: str, kc_index: dict[str, dict],
                           kc_mastery: dict) -> dict:
    """Compute the priority score for a KC per SKILL.md Phase 2.5.

    Steps 1-3 of the algorithm:
      score = reverse_deps + sum(weak_child_boosts) + grammar_bonus + SRS_due + weak_bonus

    Returns dict with score breakdown for assertion.
    """
    kc = kc_index.get(kc_id, {})
    depends_on = kc.get("dependsOn", [])

    # Step 1: reverse_deps = count of KCs that dependOn this one
    reverse_deps = sum(
        1 for other_id, other_kc in kc_index.items()
        if kc_id in other_kc.get("dependsOn", [])
    )

    # Step 2: chain boost — check parents for weak/untested
    chain_boost = 0.0
    for parent_id in depends_on:
        if parent_id in kc_index and parent_id in kc_mastery:
            parent_mastery = kc_mastery[parent_id]
            parent_err = parent_mastery.get("errorRate", 0.0)
            parent_attempts = parent_mastery.get("attempts", 0)
            # Count how many KCs depend on this parent
            parent_rev_deps = sum(
                1 for oid, okc in kc_index.items()
                if parent_id in okc.get("dependsOn", [])
            )
            if parent_err >= 0.40 or parent_attempts == 0:
                chain_boost += parent_rev_deps * 0.5

    # Step 3: bonuses
    mastery = kc_mastery.get(kc_id, {})
    error_rate = mastery.get("errorRate", 0.0)
    attempts_val = mastery.get("attempts", 0)

    srs_due = 0
    next_review = mastery.get("nextReviewDate")
    if next_review and isinstance(next_review, str) and next_review <= _today():
        srs_due = 2

    weak_bonus = 3 if error_rate >= 0.40 else 0
    # grammar_bonus not applicable without full grammar context — skip

    score = reverse_deps + chain_boost + srs_due + weak_bonus

    return {
        "kc_id": kc_id,
        "score": round(score, 2),
        "reverse_deps": reverse_deps,
        "chain_boost": round(chain_boost, 2),
        "srs_due": srs_due,
        "weak_bonus": weak_bonus,
        "error_rate": error_rate,
        "attempts": attempts_val,
        "depends_on": depends_on,
    }


def rank_kcs_by_priority(kc_index: dict[str, dict],
                         kc_mastery: dict,
                         top_n: int = 2) -> list[dict]:
    """Run the full priority ranking per Phase 2.5 Step 4.

    Sort by: score DESC -> errorRate DESC -> untested_parent_count ASC -> attempts ASC.
    Returns top_n results.
    """
    scored = []
    for kc_id in kc_mastery:
        if kc_id not in kc_index:
            continue
        result = compute_priority_score(kc_id, kc_index, kc_mastery)
        # Count untested parents
        kc = kc_index.get(kc_id, {})
        untested_parents = 0
        for parent_id in kc.get("dependsOn", []):
            if parent_id in kc_mastery:
                pm = kc_mastery[parent_id]
                if pm.get("attempts", 0) == 0:
                    untested_parents += 1
        result["untested_parents"] = untested_parents
        scored.append(result)

    scored.sort(key=lambda r: (
        -r["score"],
        -r["error_rate"],
        r["untested_parents"],
        r["attempts"],
    ))
    return scored[:top_n]


# ── Test helpers ────────────────────────────────────────────────────

def make_tmp_ielts_dir(tmp_path: Path) -> Path:
    """Create a temporary .ielts/ directory for isolated testing.

    Returns the path to the temp directory, and patches IELTS_DIR.
    """
    ielts_tmp = tmp_path / ".ielts"
    ielts_tmp.mkdir(parents=True, exist_ok=True)
    return ielts_tmp
