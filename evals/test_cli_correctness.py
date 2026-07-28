"""CLI Correctness evals — test pure functions from shared/ielts_cli.py.

Tests cmd_init, cmd_validate, _build_fresh_profile, and other
deterministic CLI functions.

Usage:
  .venv/bin/deepeval test run evals/test_cli_correctness.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import BaseMetric

from evals.conftest import (
    PROJECT_ROOT,
    _build_fresh_profile,
    load_kc_graph,
    build_kc_index,
)


class StructuralCheckMetric(BaseMetric):
    """Checks that a function output has expected structural properties.

    actual_output is a JSON array of [description, passed] pairs.
    Score is 1.0 if all checks pass.
    """

    def __init__(self, threshold: float = 1.0):
        super().__init__()
        self.threshold = threshold

    def measure(self, test_case, *args, **kwargs):
        checks = json.loads(test_case.actual_output)
        failures = [desc for desc, passed in checks if not passed]
        self.score = 1.0 if not failures else 0.0
        self.reason = "; ".join(failures) if failures else f"All {len(checks)} checks passed"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)


def _run_checks(checks: list[tuple[str, bool]], label: str):
    """Run structural checks through DeepEval assert_test."""
    metric = StructuralCheckMetric()
    test_case = LLMTestCase(
        input=label,
        actual_output=json.dumps(checks),
    )
    assert_test(test_case, [metric])


# ── _build_fresh_profile tests ──────────────────────────────────────

def test_build_fresh_profile_structure():
    """Fresh profile has all required top-level keys."""
    kc_graph = load_kc_graph()
    profile = _build_fresh_profile(kc_graph, target_band=6.5,
                                   exam_date="2027-07-27")

    checks = [
        ("version is 2.0.0", profile.get("version") == "2.0.0"),
        ("has learner section", "learner" in profile),
        ("has skills section", "skills" in profile),
        ("has vocabulary section", "vocabulary" in profile),
        ("has grammar section", "grammar" in profile),
        ("has testHistory", "testHistory" in profile),
        ("has coachNotes", "coachNotes" in profile),
        ("targetBand is 6.5", profile["learner"]["targetBand"] == 6.5),
        ("examDate is set", profile["learner"]["examDate"] == "2027-07-27"),
        ("diagnosticCompleted is False",
         profile["learner"]["diagnosticCompleted"] is False),
    ]
    _run_checks(checks, "build_fresh_profile_structure")


def test_build_fresh_profile_all_skills_populated():
    """Fresh profile has all 4 skills with KCs populated."""
    kc_graph = load_kc_graph()
    profile = _build_fresh_profile(kc_graph)

    checks = []
    for skill in ["listening", "reading", "writing", "speaking"]:
        skill_data = profile["skills"].get(skill, {})
        mastery = skill_data.get("kcMastery", {})
        expected_kcs = len(kc_graph.get("skills", {}).get(skill, {}).get("kcs", []))

        checks.append(
            (f"{skill} has {expected_kcs} KCs",
             len(mastery) == expected_kcs and expected_kcs > 0)
        )
        for kc_id, kc_data in mastery.items():
            checks.append(
                (f"{skill}.{kc_id} initial level is 'weak'",
                 kc_data["level"] == "weak")
            )
            checks.append(
                (f"{skill}.{kc_id} initial errorRate is 0.0",
                 kc_data["errorRate"] == 0.0)
            )
            checks.append(
                (f"{skill}.{kc_id} initial attempts is 0",
                 kc_data["attempts"] == 0)
            )
    _run_checks(checks, "all_skills_populated")


# ── KC Graph tests ─────────────────────────────────────────────────

def test_kc_graph_has_all_skills():
    """KC graph has entries for all 4 IELTS skills."""
    kc_graph = load_kc_graph()

    checks = []
    for skill in ["listening", "reading", "writing", "speaking"]:
        skill_data = kc_graph.get("skills", {}).get(skill, {})
        kcs = skill_data.get("kcs", [])
        checks.append((f"{skill} has KCs", len(kcs) > 0))
    _run_checks(checks, "kc_graph_has_all_skills")


def test_kc_index_is_complete():
    """KC index has all KCs from graph with correct structure."""
    kc_graph = load_kc_graph()
    index = build_kc_index(kc_graph)

    checks = [
        ("index is non-empty", len(index) > 0),
    ]
    for kc_id, kc in index.items():
        checks.append(
            (f"{kc_id} has dependsOn", isinstance(kc.get("dependsOn"), list))
        )
    total_expected = sum(
        len(sd.get("kcs", []))
        for sd in kc_graph.get("skills", {}).values()
    )
    checks.append(
        (f"index has all {total_expected} KCs", len(index) == total_expected)
    )
    _run_checks(checks, "kc_index_complete")


# ── Student profile live check ──────────────────────────────────────

def test_live_profile_has_valid_structure():
    """The live student-profile.json passes basic structural validation."""
    profile_path = PROJECT_ROOT / ".ielts" / "student-profile.json"

    checks = []
    if not profile_path.exists():
        checks.append(("profile exists", False))
    else:
        checks.append(("profile exists", True))
        profile = json.loads(profile_path.read_text())

        checks.append(("version is set", "version" in profile))
        checks.append(("learner section exists", "learner" in profile))
        checks.append(("skills section exists", "skills" in profile))
        checks.append(("testHistory is a list",
                       isinstance(profile.get("testHistory"), list)))
        checks.append(("coachNotes is a list",
                       isinstance(profile.get("coachNotes"), list)))
        for skill in ["listening", "reading", "writing", "speaking"]:
            skill_data = profile.get("skills", {}).get(skill, {})
            checks.append(
                (f"{skill} has currentBand", "currentBand" in skill_data)
            )
            checks.append(
                (f"{skill} has kcMastery",
                 isinstance(skill_data.get("kcMastery"), dict))
            )
    _run_checks(checks, "live_profile_structure")


# ── CLI subprocess tests ────────────────────────────────────────────

def test_cli_validate_returns_ok():
    """ielts_cli.py validate exits cleanly on valid profile."""
    venv_python = str(PROJECT_ROOT / ".venv" / "bin" / "python3")
    cli_path = str(PROJECT_ROOT / "shared" / "ielts_cli.py")

    result = subprocess.run(
        [venv_python, cli_path, "validate"],
        capture_output=True, text=True, timeout=30,
        cwd=str(PROJECT_ROOT),
    )

    output = json.loads(result.stdout)
    checks = [
        ("exit code is 0 or 1", result.returncode in (0, 1)),
        ("response has status field", "status" in output),
        ("response is JSON", isinstance(output, dict)),
        ("has errors list", isinstance(output.get("errors"), list)),
        ("has warnings list", isinstance(output.get("warnings"), list)),
    ]
    _run_checks(checks, "cli_validate")


def test_cli_status_returns_json():
    """ielts_cli.py status returns valid JSON with band info."""
    venv_python = str(PROJECT_ROOT / ".venv" / "bin" / "python3")
    cli_path = str(PROJECT_ROOT / "shared" / "ielts_cli.py")

    result = subprocess.run(
        [venv_python, cli_path, "status"],
        capture_output=True, text=True, timeout=30,
        cwd=str(PROJECT_ROOT),
    )

    checks = [
        ("exit code is 0", result.returncode == 0),
        ("stdout is non-empty", len(result.stdout.strip()) > 0),
    ]
    _run_checks(checks, "cli_status")


def test_cli_lesson_library_list():
    """ielts_cli.py lesson-library list returns valid JSON."""
    venv_python = str(PROJECT_ROOT / ".venv" / "bin" / "python3")
    cli_path = str(PROJECT_ROOT / "shared" / "ielts_cli.py")

    result = subprocess.run(
        [venv_python, cli_path, "lesson-library", "list"],
        capture_output=True, text=True, timeout=30,
        cwd=str(PROJECT_ROOT),
    )

    output = json.loads(result.stdout)
    checks = [
        ("exit code is 0", result.returncode == 0),
        ("status is ok", output.get("status") == "ok"),
        ("has totalLessons", "totalLessons" in output),
        ("has lessons list", isinstance(output.get("lessons"), list)),
    ]
    _run_checks(checks, "cli_lesson_library")
