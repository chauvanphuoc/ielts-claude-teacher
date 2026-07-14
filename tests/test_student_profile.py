#!/usr/bin/env python3
"""Student Profile & KC Graph Schema Validation Tests.

Validates:
  1. Student profile JSON schema integrity
  2. KC graph structure and dependency integrity
  3. Cross-reference integrity (profile kcTags exist in KC graph)
  4. errorRate formula and level derivation thresholds
  5. Edge cases (empty state, null fields, max values)

Usage:
  .venv/bin/python3 -m pytest tests/test_student_profile.py -v
  .venv/bin/python3 tests/test_student_profile.py          # no pytest needed
"""

import json
import os
import sys
import copy
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IELTS_DIR = PROJECT_ROOT / ".ielts"
KC_GRAPH_PATH = IELTS_DIR / "kc-graph-ielts.json"
ROADMAP_PATH = IELTS_DIR / "roadmap.json"


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def load_json(path):
    with open(path) as f:
        return json.load(f)


def compute_level(error_rate):
    """Derive mastery level from errorRate per design doc thresholds."""
    if error_rate >= 0.40:
        return "weak"
    elif error_rate >= 0.15:
        return "ok"
    else:
        return "mastered"


def compute_new_error_rate(old_error_rate, attempts, session_error_rate):
    """Cumulative moving average of per-session error rates."""
    return (attempts * old_error_rate + session_error_rate) / (attempts + 1)


def collect_kc_ids(kc_graph):
    """Return set of all KC IDs across all skills."""
    ids = set()
    for skill_name, skill_data in kc_graph.get("skills", {}).items():
        for kc in skill_data.get("kcs", []):
            ids.add(kc["id"])
    return ids


# ══════════════════════════════════════════════════════════════════════
# KC Graph Tests
# ══════════════════════════════════════════════════════════════════════

class TestKCGraph:
    """Validate kc-graph-ielts.json structure and integrity."""

    @classmethod
    def setup_class(cls):
        cls.graph = load_json(KC_GRAPH_PATH)
        cls.all_kcs = []
        for skill_name, skill_data in cls.graph["skills"].items():
            cls.all_kcs.extend(skill_data.get("kcs", []))

    # ── Structure ──

    def test_graph_has_required_top_level_fields(self):
        for field in ["version", "subject", "skills"]:
            assert field in self.graph, f"Missing top-level field: {field}"

    def test_reading_has_kcs(self):
        reading = self.graph["skills"]["reading"]
        assert len(reading["kcs"]) >= 8, (
            f"Reading must have >= 8 KCs, got {len(reading['kcs'])}"
        )

    def test_each_kc_has_required_fields(self):
        required = ["id", "name", "skill", "status", "description",
                    "dependsOn", "difficultyLevel", "commonErrors", "exerciseTemplates"]
        for kc in self.all_kcs:
            for field in required:
                assert field in kc, f"KC '{kc.get('id', '?')}' missing field: {field}"

    def test_each_kc_status_is_draft_or_confirmed(self):
        for kc in self.all_kcs:
            assert kc["status"] in ("draft", "confirmed"), (
                f"KC '{kc['id']}' has invalid status: {kc['status']}"
            )

    def test_difficulty_level_in_range(self):
        for kc in self.all_kcs:
            assert 1 <= kc["difficultyLevel"] <= 5, (
                f"KC '{kc['id']}' difficultyLevel {kc['difficultyLevel']} out of 1-5 range"
            )

    def test_common_errors_have_entries(self):
        for kc in self.all_kcs:
            assert len(kc["commonErrors"]) >= 1, (
                f"KC '{kc['id']}' has no commonErrors defined"
            )

    def test_exercise_templates_have_entries(self):
        for kc in self.all_kcs:
            assert len(kc["exerciseTemplates"]) >= 1, (
                f"KC '{kc['id']}' has no exerciseTemplates defined"
            )

    # ── Dependency Integrity ──

    def test_all_kc_ids_are_unique(self):
        ids = [kc["id"] for kc in self.all_kcs]
        duplicates = {x for x in ids if ids.count(x) > 1}
        assert not duplicates, f"Duplicate KC IDs found: {duplicates}"

    def test_dependencies_reference_real_kcs(self):
        kc_ids = {kc["id"] for kc in self.all_kcs}
        for kc in self.all_kcs:
            for dep in kc["dependsOn"]:
                assert dep in kc_ids, (
                    f"KC '{kc['id']}' depends on non-existent '{dep}'"
                )

    def test_no_circular_dependencies(self):
        """Detect cycles using DFS."""
        kc_map = {kc["id"]: kc for kc in self.all_kcs}

        def has_cycle(kc_id, visited, path):
            visited.add(kc_id)
            path.add(kc_id)
            for dep in kc_map[kc_id].get("dependsOn", []):
                if dep in path:
                    return True  # cycle found
                if dep not in visited:
                    if has_cycle(dep, visited, path):
                        return True
            path.discard(kc_id)
            return False

        visited = set()
        for kc_id in kc_map:
            if kc_id not in visited:
                assert not has_cycle(kc_id, visited, set()), (
                    f"Circular dependency detected involving '{kc_id}'"
                )

    def test_foundational_kcs_have_no_dependencies(self):
        """At least some KCs should be foundational (no dependsOn)."""
        foundational = [kc for kc in self.all_kcs if not kc["dependsOn"]]
        assert len(foundational) >= 2, (
            f"Need at least 2 foundational KCs, got {len(foundational)}"
        )


# ══════════════════════════════════════════════════════════════════════
# errorRate Formula Tests
# ══════════════════════════════════════════════════════════════════════

class TestErrorRateFormula:
    """Validate errorRate calculation and level derivation."""

    @classmethod
    def setup_class(cls):
        pass

    def test_level_weak_threshold(self):
        """errorRate >= 0.40 must derive to 'weak'."""
        assert compute_level(0.40) == "weak"
        assert compute_level(0.60) == "weak"
        assert compute_level(0.99) == "weak"

    def test_level_ok_threshold(self):
        """errorRate 0.15-0.39 must derive to 'ok'."""
        assert compute_level(0.15) == "ok"
        assert compute_level(0.25) == "ok"
        assert compute_level(0.39) == "ok"

    def test_level_mastered_threshold(self):
        """errorRate < 0.15 must derive to 'mastered'."""
        assert compute_level(0.14) == "mastered"
        assert compute_level(0.05) == "mastered"
        assert compute_level(0.00) == "mastered"

    def test_cumulative_formula_improving_student(self):
        """Student improves: 0.60 over 2 attempts, then 0.20 session."""
        # (2 * 0.60 + 0.20) / 3 = 1.40/3 = 0.467
        result = compute_new_error_rate(0.60, 2, 0.20)
        assert abs(result - 0.467) < 0.001, (
            f"Expected ~0.467, got {result}"
        )
        assert compute_level(result) == "weak"

    def test_cumulative_formula_mastering(self):
        """Student masters: 0.60→0.20→0.00 session."""
        after_2 = compute_new_error_rate(0.60, 2, 0.20)
        after_3 = compute_new_error_rate(after_2, 3, 0.00)
        assert compute_level(after_3) == "ok", (
            f"Expected 'ok' after mastering, got {compute_level(after_3)} (errorRate={after_3:.3f})"
        )

    def test_new_student_first_attempt(self):
        """First attempt: no prior data, 2/5 wrong."""
        # attempts=0, errorRate=0 (no prior data), session=0.40
        result = compute_new_error_rate(0.0, 0, 0.40)
        assert abs(result - 0.40) < 0.001
        assert compute_level(result) == "weak"

    def test_perfect_first_attempt(self):
        result = compute_new_error_rate(0.0, 0, 0.0)
        assert abs(result - 0.0) < 0.001
        assert compute_level(result) == "mastered"


# ══════════════════════════════════════════════════════════════════════
# Student Profile Schema Tests
# ══════════════════════════════════════════════════════════════════════

class TestStudentProfileSchema:
    """Validate student-profile.json structure against design doc schema."""

    @classmethod
    def setup_class(cls):
        # Use roadmap.json as source data since student-profile.json
        # doesn't exist yet (will be created by migration).
        cls.roadmap = load_json(ROADMAP_PATH)

    # ── Top-level structure ──

    def test_roadmap_has_version(self):
        assert "version" in self.roadmap

    def test_roadmap_has_learner(self):
        assert "learner" in self.roadmap
        learner = self.roadmap["learner"]
        for field in ["targetBand", "activeSkills", "startedAt"]:
            assert field in learner, f"learner missing: {field}"

    def test_target_band_in_range(self):
        band = self.roadmap["learner"]["targetBand"]
        assert 0 <= band <= 9.0, f"targetBand {band} out of 0-9 range"

    def test_active_skills_is_non_empty(self):
        skills = self.roadmap["learner"]["activeSkills"]
        assert len(skills) >= 1
        for s in skills:
            assert s in ("listening", "reading", "writing", "speaking"), (
                f"Unknown skill: {s}"
            )

    def test_roadmap_has_all_four_skills(self):
        for skill in ["listening", "reading", "writing", "speaking"]:
            assert skill in self.roadmap["skills"], f"Missing skill: {skill}"

    def test_each_skill_has_required_fields(self):
        required = ["currentBand", "bandHistory", "weakAreas", "practiceCount", "lastPracticeDate"]
        for skill_name, skill_data in self.roadmap["skills"].items():
            for field in required:
                assert field in skill_data, f"skills.{skill_name} missing: {field}"

    def test_current_band_in_range(self):
        for skill_name, skill_data in self.roadmap["skills"].items():
            band = skill_data["currentBand"]
            assert 0 <= band <= 9.0, (
                f"skills.{skill_name}.currentBand {band} out of 0-9 range"
            )

    def test_band_history_is_list(self):
        for skill_name, skill_data in self.roadmap["skills"].items():
            assert isinstance(skill_data["bandHistory"], list), (
                f"skills.{skill_name}.bandHistory must be a list"
            )

    def test_history_and_coach_notes_exist(self):
        assert "history" in self.roadmap
        assert "coachNotes" in self.roadmap
        assert isinstance(self.roadmap["coachNotes"], list)


# ══════════════════════════════════════════════════════════════════════
# Cross-Reference Integrity Tests
# ══════════════════════════════════════════════════════════════════════

class TestCrossReferenceIntegrity:
    """Validate that profile KC tags reference real KCs in the graph."""

    @classmethod
    def setup_class(cls):
        cls.graph = load_json(KC_GRAPH_PATH)
        cls.kc_ids = collect_kc_ids(cls.graph)

    def test_kc_graph_has_reading_kcs(self):
        reading_kcs = [kc for kc in self.kc_ids if kc.startswith("kc-read-")]
        assert len(reading_kcs) >= 8, (
            f"Expected >= 8 reading KCs, got {len(reading_kcs)}"
        )

    def test_kc_ids_follow_naming_convention(self):
        """All KC IDs should follow kc-{skill}-{slug} pattern."""
        for kc_id in self.kc_ids:
            assert kc_id.startswith("kc-"), (
                f"KC ID '{kc_id}' doesn't start with 'kc-'"
            )
            parts = kc_id.split("-", 2)
            assert len(parts) == 3, (
                f"KC ID '{kc_id}' doesn't follow kc-{{skill}}-{{slug}} pattern"
            )

    def test_no_orphaned_vocab_kc_tags(self):
        """If grammar.weakPoints reference kcTags, they must exist in KC graph."""
        roadmap = load_json(ROADMAP_PATH)
        # roadmap.json doesn't have grammar.weakPoints yet — this is a forward test
        # that will activate after migration to student-profile.json

    def test_lesson_kc_tags_exist(self):
        """All kcTags in lesson library entries must reference real KCs."""
        # Placeholder — activates once lesson library has entries.
        # When student-profile.json exists, iterate lessonLibrary.lessons[].kcTags
        # and verify each tag is in kc_ids.


# ══════════════════════════════════════════════════════════════════════
# Edge Case Tests
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Validate behavior at boundaries."""

    @classmethod
    def setup_class(cls):
        pass

    def test_empty_band_history_is_valid(self):
        """New student has empty bandHistory — should not crash."""
        roadmap = load_json(ROADMAP_PATH)
        for skill_name, skill_data in roadmap["skills"].items():
            assert skill_data["bandHistory"] == [], (
                f"skills.{skill_name}.bandHistory should be empty for new student"
            )

    def test_null_exam_date_is_valid(self):
        """No exam date set — should be null, not crash."""
        roadmap = load_json(ROADMAP_PATH)
        assert roadmap["learner"]["examDate"] is None

    def test_practice_count_starts_at_zero(self):
        roadmap = load_json(ROADMAP_PATH)
        for skill_name, skill_data in roadmap["skills"].items():
            assert skill_data["practiceCount"] == 0, (
                f"skills.{skill_name}.practiceCount should start at 0"
            )

    def test_reading_kc_inference_has_correct_deps(self):
        """kc-read-inference must depend on main-idea AND detail."""
        graph = load_json(KC_GRAPH_PATH)
        reading_kcs = {kc["id"]: kc for kc in graph["skills"]["reading"]["kcs"]}
        inference = reading_kcs["kc-read-inference"]
        assert "kc-read-main-idea" in inference["dependsOn"]
        assert "kc-read-detail" in inference["dependsOn"]

    def test_kc_tfng_depends_on_inference(self):
        """kc-read-tfng must depend on kc-read-inference."""
        graph = load_json(KC_GRAPH_PATH)
        reading_kcs = {kc["id"]: kc for kc in graph["skills"]["reading"]["kcs"]}
        tfng = reading_kcs["kc-read-tfng"]
        assert "kc-read-inference" in tfng["dependsOn"]

    def test_kc_ynng_is_higher_difficulty_than_tfng(self):
        """Y/N/NG is harder than T/F/NG."""
        graph = load_json(KC_GRAPH_PATH)
        reading_kcs = {kc["id"]: kc for kc in graph["skills"]["reading"]["kcs"]}
        assert reading_kcs["kc-read-ynng"]["difficultyLevel"] > reading_kcs["kc-read-tfng"]["difficultyLevel"], (
            "Y/N/NG should be higher difficulty than T/F/NG"
        )

    # ── Listening KC tests ──

    def test_listening_has_seven_kcs(self):
        """Listening skill should have exactly 7 KCs."""
        graph = load_json(KC_GRAPH_PATH)
        kcs = graph["skills"]["listening"]["kcs"]
        assert len(kcs) == 7, f"Expected 7 listening KCs, got {len(kcs)}"

    def test_listening_kc_ids_follow_convention(self):
        """Listening KC IDs must follow kc-listen-{slug} pattern."""
        graph = load_json(KC_GRAPH_PATH)
        for kc in graph["skills"]["listening"]["kcs"]:
            assert kc["id"].startswith("kc-listen-"), (
                f"{kc['id']} does not follow kc-listen-{{slug}} convention"
            )

    def test_listening_kc_dependencies_are_intra_skill(self):
        """Listening KCs must only depend on other listening KCs (no cross-skill dependencies)."""
        graph = load_json(KC_GRAPH_PATH)
        listening_ids = {kc["id"] for kc in graph["skills"]["listening"]["kcs"]}
        for kc in graph["skills"]["listening"]["kcs"]:
            for dep in kc.get("dependsOn", []):
                assert dep in listening_ids, (
                    f"{kc['id']} has cross-skill dependency: {dep}"
                )

    def test_listening_foundational_kcs_are_lower_difficulty(self):
        """Foundational listening KCs (spelling, numbers, distractor) should be L1-L3."""
        graph = load_json(KC_GRAPH_PATH)
        kcs = {kc["id"]: kc for kc in graph["skills"]["listening"]["kcs"]}
        for kc_id in ["kc-listen-spelling", "kc-listen-numbers", "kc-listen-distractor"]:
            assert kcs[kc_id]["difficultyLevel"] <= 3, (
                f"{kc_id} is foundational, should be L1-L3, got L{kcs[kc_id]['difficultyLevel']}"
            )

    def test_listening_gapfill_depends_on_spelling_and_numbers(self):
        """kc-listen-gapfill should depend on both spelling and numbers KCs."""
        graph = load_json(KC_GRAPH_PATH)
        kcs = {kc["id"]: kc for kc in graph["skills"]["listening"]["kcs"]}
        deps = kcs["kc-listen-gapfill"]["dependsOn"]
        assert "kc-listen-spelling" in deps, "gapfill should depend on spelling"
        assert "kc-listen-numbers" in deps, "gapfill should depend on numbers"

    def test_listening_all_have_common_errors(self):
        """Every listening KC must have at least 3 common errors."""
        graph = load_json(KC_GRAPH_PATH)
        for kc in graph["skills"]["listening"]["kcs"]:
            errors = kc.get("commonErrors", [])
            assert len(errors) >= 3, (
                f"{kc['id']} has only {len(errors)} commonErrors, need at least 3"
            )

    def test_listening_total_kcs_is_23(self):
        """Combined total: 9 Reading + 7 Writing + 7 Listening = 23 KCs."""
        graph = load_json(KC_GRAPH_PATH)
        total = sum(len(skill["kcs"]) for skill in graph["skills"].values())
        assert total == 23, f"Expected 23 total KCs, got {total}"


# ══════════════════════════════════════════════════════════════════════
# Run standalone (no pytest needed)
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestKCGraph,
        TestErrorRateFormula,
        TestStudentProfileSchema,
        TestCrossReferenceIntegrity,
        TestEdgeCases,
    ]

    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        print(f"\n{'='*60}")
        print(f"  {cls.__name__}")
        print(f"{'='*60}")
        try:
            cls.setup_class()
        except Exception as e:
            print(f"  SETUP ERROR: {e}")
            failed += 1
            continue

        for name in sorted(dir(cls)):
            if not name.startswith("test_"):
                continue
            method = getattr(cls(), name)
            try:
                method()
                print(f"  ✓ {name}")
                passed += 1
            except AssertionError as e:
                print(f"  ✗ {name}")
                print(f"    {e}")
                failed += 1
                errors.append(f"{cls.__name__}.{name}: {e}")
            except Exception as e:
                print(f"  ✗ {name} (ERROR: {e})")
                failed += 1
                errors.append(f"{cls.__name__}.{name}: {e}")

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
    print(f"{'='*60}")
    if errors:
        print("\nFAILURES:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("All tests passed.")
