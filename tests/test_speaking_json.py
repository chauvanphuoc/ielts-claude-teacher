#!/usr/bin/env python3
"""Speaking JSON Schema Validation Tests.

Validates:
  1. speaking_cambridge-1.json schema integrity
  2. 4 tests extracted with modern 3-part format
  3. Each part has required fields by type
  4. Legacy tasks preserved with correct content
  5. Content spot-check against textbook
  6. KC cross-references for speaking KCs
  7. Edge cases: missing fields, empty parts

Usage:
  .venv/bin/python3 tests/test_speaking_json.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEAKING_JSON_PATH = PROJECT_ROOT / "shared" / "speaking" / "speaking_cambridge-1.json"
KC_GRAPH_PATH = PROJECT_ROOT / ".ielts" / "kc-graph-ielts.json"

SUPPORTED_PART_TYPES = {"interview", "long-turn", "discussion"}
INTERVIEW_REQUIRED = {"partNumber", "partType", "topic", "questions"}
LONG_TURN_REQUIRED = {"partNumber", "partType", "cueCard", "preparationTime", "speakingTime"}
DISCUSSION_REQUIRED = {"partNumber", "partType", "topic", "questions"}
CUE_CARD_REQUIRED = {"topic", "bullets"}
LEGACY_REQUIRED = {"partType", "title", "scenario", "role", "topicsToAsk", "interviewerNotes"}

EXPECTED_LEGACY_TITLES = {
    1: "University Clubs and Associations",
    2: "Asking for an Extension",
    3: "The Public Holiday",
    4: "The Excursion",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── File existence ──

def test_speaking_json_exists():
    """The speaking JSON file must exist."""
    assert SPEAKING_JSON_PATH.exists(), f"Missing: {SPEAKING_JSON_PATH}"


# ── Top-level schema ──

def test_top_level_fields():
    """JSON must have required top-level fields."""
    data = load_json(SPEAKING_JSON_PATH)
    for field in ["source", "generatedAt", "generatedBy", "tests", "_validation"]:
        assert field in data, f"Missing top-level field: {field}"
    assert data["source"] == "cambridge-1"
    assert data["generatedBy"] == "/init-textbook-speaking"


def test_has_four_tests():
    """JSON must contain exactly 4 speaking tests."""
    data = load_json(SPEAKING_JSON_PATH)
    assert len(data["tests"]) == 4, f"Expected 4 tests, got {len(data['tests'])}"


def test_test_numbers_sequential():
    """Test numbers must be 1, 2, 3, 4."""
    data = load_json(SPEAKING_JSON_PATH)
    numbers = [t["testNumber"] for t in data["tests"]]
    assert numbers == [1, 2, 3, 4], f"Expected [1,2,3,4], got {numbers}"


# ── Modern parts ──

def test_each_test_has_three_parts():
    """Each test must have exactly 3 modern parts."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        parts = test.get("parts", [])
        assert len(parts) == 3, f"Test {test['testNumber']}: expected 3 parts, got {len(parts)}"


def test_part_types_are_correct():
    """Parts must be interview, long-turn, discussion in order."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        types = [p["partType"] for p in test["parts"]]
        assert types == ["interview", "long-turn", "discussion"], \
            f"Test {test['testNumber']}: expected interview/long-turn/discussion, got {types}"


def test_part_numbers_sequential():
    """Part numbers must be 1, 2, 3."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        numbers = [p["partNumber"] for p in test["parts"]]
        assert numbers == [1, 2, 3], f"Test {test['testNumber']}: expected [1,2,3], got {numbers}"


def test_interview_parts_have_required_fields():
    """Each interview part must have required fields with valid content."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        part = test["parts"][0]
        for field in INTERVIEW_REQUIRED:
            assert field in part, f"Test {test['testNumber']} Part 1: missing '{field}'"
        assert isinstance(part["questions"], list), \
            f"Test {test['testNumber']} Part 1: questions must be a list"
        assert len(part["questions"]) >= 4, \
            f"Test {test['testNumber']} Part 1: expected >=4 questions, got {len(part['questions'])}"
        assert part["partType"] == "interview"
        assert part["partNumber"] == 1


def test_long_turn_parts_have_required_fields():
    """Each long-turn part must have cue card with required fields."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        part = test["parts"][1]
        for field in LONG_TURN_REQUIRED:
            assert field in part, f"Test {test['testNumber']} Part 2: missing '{field}'"
        cc = part["cueCard"]
        for field in CUE_CARD_REQUIRED:
            assert field in cc, f"Test {test['testNumber']} Part 2 cueCard: missing '{field}'"
        assert isinstance(cc["bullets"], list), \
            f"Test {test['testNumber']} Part 2: bullets must be a list"
        assert len(cc["bullets"]) >= 3, \
            f"Test {test['testNumber']} Part 2: expected >=3 bullets, got {len(cc['bullets'])}"
        assert part["preparationTime"] == 60, \
            f"Test {test['testNumber']} Part 2: expected prepTime=60, got {part['preparationTime']}"
        assert part["speakingTime"] == 120, \
            f"Test {test['testNumber']} Part 2: expected speakingTime=120, got {part['speakingTime']}"
        assert part["partType"] == "long-turn"
        assert part["partNumber"] == 2


def test_discussion_parts_have_required_fields():
    """Each discussion part must have required fields with valid content."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        part = test["parts"][2]
        for field in DISCUSSION_REQUIRED:
            assert field in part, f"Test {test['testNumber']} Part 3: missing '{field}'"
        assert isinstance(part["questions"], list), \
            f"Test {test['testNumber']} Part 3: questions must be a list"
        assert len(part["questions"]) >= 4, \
            f"Test {test['testNumber']} Part 3: expected >=4 questions, got {len(part['questions'])}"
        assert part["partType"] == "discussion"
        assert part["partNumber"] == 3


# ── Legacy tasks ──

def test_each_test_has_legacy_task():
    """Each test must preserve the original textbook task in _legacyTask."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        assert "_legacyTask" in test, f"Test {test['testNumber']}: missing _legacyTask"


def test_legacy_tasks_have_required_fields():
    """Each legacy task must have required fields."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        lt = test["_legacyTask"]
        for field in LEGACY_REQUIRED:
            assert field in lt, f"Test {test['testNumber']} _legacyTask: missing '{field}'"
        assert isinstance(lt["topicsToAsk"], list), \
            f"Test {test['testNumber']} _legacyTask: topicsToAsk must be a list"
        assert len(lt["topicsToAsk"]) >= 3, \
            f"Test {test['testNumber']} _legacyTask: expected >=3 topics"
        assert "format" in lt, f"Test {test['testNumber']} _legacyTask: missing format description"


def test_legacy_titles_match_textbook():
    """Spot-check: legacy task titles must match Cambridge IELTS 1 textbook."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        expected = EXPECTED_LEGACY_TITLES[test["testNumber"]]
        actual = test["_legacyTask"]["title"]
        assert actual == expected, \
            f"Test {test['testNumber']}: expected title '{expected}', got '{actual}'"


def test_legacy_interviewer_notes_have_prompts():
    """Each legacy task's interviewerNotes must have description + prompts."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        notes = test["_legacyTask"]["interviewerNotes"]
        assert "description" in notes, \
            f"Test {test['testNumber']}: interviewerNotes missing description"
        assert "prompts" in notes, \
            f"Test {test['testNumber']}: interviewerNotes missing prompts"


# ── Validation metadata ──

def test_validation_metadata():
    """_validation must show all 4 tests populated, none pending."""
    data = load_json(SPEAKING_JSON_PATH)
    v = data["_validation"]
    assert v["testsPopulated"] == [1, 2, 3, 4], \
        f"Expected testsPopulated=[1,2,3,4], got {v['testsPopulated']}"
    assert v["testsPending"] == [], \
        f"Expected testsPending=[], got {v['testsPending']}"
    assert v["modernPartsPerTest"] == 3
    assert v["legacyTasksExtracted"] == 4


# ── Content quality ──

def test_all_questions_are_non_empty():
    """No question text should be empty."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        for part in test["parts"]:
            if "questions" in part:
                for q in part["questions"]:
                    assert q.strip(), \
                        f"Test {test['testNumber']} Part {part['partNumber']}: empty question"


def test_all_cue_card_topics_are_non_empty():
    """No cue card topic or bullet should be empty."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        part = test["parts"][1]
        cc = part["cueCard"]
        assert cc["topic"].strip(), f"Test {test['testNumber']}: empty cue card topic"
        for b in cc["bullets"]:
            assert b.strip(), f"Test {test['testNumber']}: empty bullet in cue card"


def test_interview_has_instructions():
    """Each interview part must have instructions text."""
    data = load_json(SPEAKING_JSON_PATH)
    for test in data["tests"]:
        part = test["parts"][0]
        assert "instructions" in part, \
            f"Test {test['testNumber']} Part 1: missing instructions"
        assert len(part["instructions"]) > 20, \
            f"Test {test['testNumber']} Part 1: instructions too short"


# ── KC cross-references ──

def test_kc_graph_has_speaking_kcs():
    """KC graph must have exactly 5 speaking KCs."""
    kc_data = load_json(KC_GRAPH_PATH)
    speak = kc_data["skills"]["speaking"]
    kcs = speak["kcs"]
    assert len(kcs) == 5, f"Expected 5 speaking KCs, got {len(kcs)}"


def test_speaking_kc_scoring_model():
    """All speaking KCs must have scoringModel: 'subjective'."""
    kc_data = load_json(KC_GRAPH_PATH)
    for kc in kc_data["skills"]["speaking"]["kcs"]:
        assert kc.get("scoringModel") == "subjective", \
            f"{kc['id']}: expected scoringModel='subjective', got '{kc.get('scoringModel')}'"


def test_speaking_kc_depends_on_valid():
    """All dependsOn references in speaking KCs must point to existing KCs."""
    kc_data = load_json(KC_GRAPH_PATH)
    all_ids = {kc["id"] for kc in kc_data["skills"]["speaking"]["kcs"]}
    for kc in kc_data["skills"]["speaking"]["kcs"]:
        for dep in kc.get("dependsOn", []):
            assert dep in all_ids, \
                f"{kc['id']} depends on non-existent KC: {dep}"


if __name__ == "__main__":
    import traceback

    # Discover and run all test_ functions
    tests = [(name, obj) for name, obj in list(globals().items())
             if name.startswith("test_") and callable(obj)]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
    sys.exit(1 if failed > 0 else 0)
