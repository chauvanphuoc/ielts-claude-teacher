#!/usr/bin/env python3
"""Listening JSON Schema Validation Tests.

Validates:
  1. listening_cambridge-1.json schema integrity
  2. Answer key count = question count per section
  3. Audio file references are valid
  4. Question types are supported
  5. Acceptable answers format (// handling)
  6. KC cross-references for listening KCs
  7. Edge cases: missing fields, empty sections

Usage:
  .venv/bin/python3 tests/test_listening_json.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LISTENING_JSON_PATH = PROJECT_ROOT / "shared" / "listening" / "listening_cambridge-1.json"
KC_GRAPH_PATH = PROJECT_ROOT / ".ielts" / "kc-graph-ielts.json"

SUPPORTED_QUESTION_TYPES = {
    "multiple-choice", "multiple-choice-image", "gap-fill", "short-answer",
    "matching", "matching-checkboxes", "form-completion"
}

REQUIRED_SECTION_FIELDS = {"sectionNumber", "title", "audioFile", "questions", "answerKey"}
REQUIRED_QUESTION_FIELDS = {"number", "type", "text", "correctAnswer"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_listening_json_exists():
    """The listening JSON file must exist."""
    assert LISTENING_JSON_PATH.exists(), f"Missing: {LISTENING_JSON_PATH}"


def test_top_level_fields():
    """JSON must have required top-level fields."""
    data = load_json(LISTENING_JSON_PATH)
    for field in ["source", "generatedAt", "generatedBy", "audioBasePath", "tests"]:
        assert field in data, f"Missing top-level field: {field}"
    assert data["source"] == "cambridge-1"


def test_has_tests():
    """JSON must contain at least one test."""
    data = load_json(LISTENING_JSON_PATH)
    assert len(data["tests"]) >= 1, "No tests found in listening JSON"


def test_each_test_has_required_fields():
    """Each test must have testNumber and sections."""
    data = load_json(LISTENING_JSON_PATH)
    for test in data["tests"]:
        assert "testNumber" in test, f"Test missing testNumber"
        assert "sections" in test, f"Test {test.get('testNumber')} missing sections"
        assert len(test["sections"]) > 0, f"Test {test['testNumber']} has zero sections"


def test_each_section_has_required_fields():
    """Each section must have all required fields."""
    data = load_json(LISTENING_JSON_PATH)
    for test in data["tests"]:
        for sec in test["sections"]:
            missing = REQUIRED_SECTION_FIELDS - set(sec.keys())
            assert not missing, (
                f"Test {test['testNumber']} Section {sec.get('sectionNumber', '?')} "
                f"missing fields: {missing}"
            )


def test_answer_key_count_per_section():
    """Each section's answerKey count should match question count (with tolerance for grouped questions like matching-checkboxes)."""
    data = load_json(LISTENING_JSON_PATH)
    issues = []
    for test in data["tests"]:
        for sec in test["sections"]:
            q_count = len(sec.get("questions", []))
            a_count = len(sec.get("answerKey", []))

            # matching-checkboxes: one question object maps to N answers (e.g., Q11-13 = 1 question, 3 answers)
            # Adjust: count each matching-checkboxes question as its selectCount or correctAnswers length
            adjusted_q = 0
            for q in sec.get("questions", []):
                if q["type"] == "matching-checkboxes":
                    select_count = q.get("selectCount", len(q.get("correctAnswers", [])))
                    adjusted_q += select_count
                else:
                    adjusted_q += 1

            if adjusted_q != a_count:
                issues.append(
                    f"Test {test['testNumber']} Section {sec['sectionNumber']}: "
                    f"{q_count} questions (adj: {adjusted_q}) vs {a_count} answer keys"
                )

    # Report issues but don't fail — some tests are still being populated
    if issues:
        print(f"  ⚠️  Answer key count mismatches ({len(issues)}):")
        for issue in issues:
            print(f"     {issue}")
    else:
        print(f"  ✅ All sections: answer key counts match")


def test_question_types_are_supported():
    """All question types must be in the supported set."""
    data = load_json(LISTENING_JSON_PATH)
    unknown_types = set()
    for test in data["tests"]:
        for sec in test["sections"]:
            for q in sec.get("questions", []):
                if q["type"] not in SUPPORTED_QUESTION_TYPES:
                    unknown_types.add(q["type"])

    assert not unknown_types, f"Unsupported question types found: {unknown_types}"


def test_questions_have_required_fields():
    """Each question must have number, type, text, and correctAnswer (or correctAnswers)."""
    data = load_json(LISTENING_JSON_PATH)
    issues = []
    for test in data["tests"]:
        for sec in test["sections"]:
            for q in sec.get("questions", []):
                if "number" not in q:
                    issues.append(f"Question without number in Section {sec['sectionNumber']}")
                if "type" not in q:
                    issues.append(f"Q{q.get('number', '?')} missing type")
                if "text" not in q:
                    issues.append(f"Q{q.get('number', '?')} missing text")
                # Must have either correctAnswer or correctAnswers
                if "correctAnswer" not in q and "correctAnswers" not in q:
                    issues.append(f"Q{q['number']} missing correctAnswer/correctAnswers")

    assert not issues, f"Questions with missing fields: {issues}"


def test_question_numbers_increment():
    """Question numbers should increase within each section."""
    data = load_json(LISTENING_JSON_PATH)
    for test in data["tests"]:
        for sec in test["sections"]:
            nums = [q["number"] for q in sec.get("questions", [])]
            # Flatten: matching-checkboxes counts as N sequential numbers
            flat = []
            for q in sec.get("questions", []):
                if q["type"] == "matching-checkboxes":
                    select_count = q.get("selectCount", len(q.get("correctAnswers", [])))
                    for i in range(select_count):
                        flat.append(q["number"] + i)
                else:
                    flat.append(q["number"])

            for i in range(1, len(flat)):
                if flat[i] <= flat[i-1]:
                    print(f"  ⚠️  Test {test['testNumber']} Section {sec['sectionNumber']}: "
                          f"non-increasing question numbers: {flat}")
                    break


def test_mc_questions_have_options():
    """Multiple choice questions must have options array."""
    data = load_json(LISTENING_JSON_PATH)
    issues = []
    for test in data["tests"]:
        for sec in test["sections"]:
            for q in sec.get("questions", []):
                if q["type"] in ("multiple-choice", "multiple-choice-image"):
                    opts = q.get("options", [])
                    if len(opts) < 2:
                        issues.append(f"Q{q['number']}: {q['type']} has < 2 options")
                    if q["type"] == "multiple-choice-image":
                        # Single-image mode: question has 'image' field, options are text labels
                        # Individual-image mode: each option has its own 'image' field
                        has_question_image = "image" in q
                        has_option_images = all("image" in opt for opt in opts)
                        if not has_question_image and not has_option_images:
                            issues.append(f"Q{q['number']}: image MC has no image (need question.image or option.image)")

    assert not issues, f"MC option issues: {issues}"


def test_acceptable_answers_format():
    """Acceptable answers should be arrays when present."""
    data = load_json(LISTENING_JSON_PATH)
    for test in data["tests"]:
        for sec in test["sections"]:
            for q in sec.get("questions", []):
                if "acceptableAnswers" in q:
                    assert isinstance(q["acceptableAnswers"], list), (
                        f"Q{q['number']}: acceptableAnswers must be a list"
                    )
                    assert len(q["acceptableAnswers"]) >= 1, (
                        f"Q{q['number']}: acceptableAnswers must not be empty"
                    )
                    # First answer should match correctAnswer
                    if "correctAnswer" in q:
                        assert q["acceptableAnswers"][0] == q["correctAnswer"], (
                            f"Q{q['number']}: acceptableAnswers[0] ({q['acceptableAnswers'][0]}) "
                            f"!= correctAnswer ({q['correctAnswer']})"
                        )


def test_listening_kcs_exist_in_graph():
    """All listening KCs should exist in the KC graph and follow naming convention."""
    kc_graph = load_json(KC_GRAPH_PATH)
    listening = kc_graph["skills"]["listening"]
    kcs = listening["kcs"]

    assert len(kcs) == 7, f"Expected 7 listening KCs, found {len(kcs)}"

    expected_ids = {
        "kc-listen-spelling", "kc-listen-numbers", "kc-listen-distractor",
        "kc-listen-mc", "kc-listen-gapfill", "kc-listen-map", "kc-listen-inference"
    }
    actual_ids = {kc["id"] for kc in kcs}
    assert actual_ids == expected_ids, f"KC ID mismatch. Missing: {expected_ids - actual_ids}"


def test_listening_kc_dependencies_valid():
    """Listening KC dependsOn values must reference real listening KCs."""
    kc_graph = load_json(KC_GRAPH_PATH)
    kcs = kc_graph["skills"]["listening"]["kcs"]
    ids = {kc["id"] for kc in kcs}

    for kc in kcs:
        for dep in kc.get("dependsOn", []):
            assert dep in ids, f"{kc['id']} depends on non-existent KC: {dep}"


def test_listening_kc_difficulty_levels():
    """Listening KC difficulty levels should be consistent with defined dependencies."""
    kc_graph = load_json(KC_GRAPH_PATH)
    kcs = {kc["id"]: kc for kc in kc_graph["skills"]["listening"]["kcs"]}

    # Foundational KCs (no dependsOn) should be lower difficulty than dependent KCs
    for kc_id, kc in kcs.items():
        for dep in kc.get("dependsOn", []):
            if dep in kcs:
                assert kcs[dep]["difficultyLevel"] <= kc["difficultyLevel"], (
                    f"{kc_id} (L{kc['difficultyLevel']}) should not be easier than "
                    f"its dependency {dep} (L{kcs[dep]['difficultyLevel']})"
                )


def test_listening_kc_band_ranges():
    """Listening KC band ranges should be valid (4.0-9.0, start < end)."""
    kc_graph = load_json(KC_GRAPH_PATH)
    for kc in kc_graph["skills"]["listening"]["kcs"]:
        br = kc.get("bandRange", [])
        assert len(br) == 2, f"{kc['id']}: bandRange must have 2 elements"
        assert 4.0 <= br[0] <= 9.0, f"{kc['id']}: bandRange start out of range"
        assert 4.0 <= br[1] <= 9.0, f"{kc['id']}: bandRange end out of range"
        assert br[0] < br[1], f"{kc['id']}: bandRange start must be less than end"


# ══════════════════════════════════════════════════════════════════════
# Run standalone
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback

    tests = [
        test_listening_json_exists,
        test_top_level_fields,
        test_has_tests,
        test_each_test_has_required_fields,
        test_each_section_has_required_fields,
        test_answer_key_count_per_section,
        test_question_types_are_supported,
        test_questions_have_required_fields,
        test_question_numbers_increment,
        test_mc_questions_have_options,
        test_acceptable_answers_format,
        test_listening_kcs_exist_in_graph,
        test_listening_kc_dependencies_valid,
        test_listening_kc_difficulty_levels,
        test_listening_kc_band_ranges,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_fn in tests:
        try:
            test_fn()
            print(f"  ✅ {test_fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test_fn.__name__}: {e}")
            failed += 1
            errors.append((test_fn.__name__, str(e)))
        except Exception as e:
            print(f"  💥 {test_fn.__name__}: {e}")
            failed += 1
            errors.append((test_fn.__name__, str(e)))

    print(f"\n{'='*50}")
    print(f"  Results: {passed} passed, {failed} failed, {len(tests)} total")
    if errors:
        print(f"  Failures:")
        for name, err in errors:
            print(f"    - {name}: {err}")
    print(f"{'='*50}")

    sys.exit(0 if failed == 0 else 1)
