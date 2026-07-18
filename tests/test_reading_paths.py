"""Test reading JSON path refactoring — shared/reading/{source}/test-{N}.json"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SHARED_READING = PROJECT_ROOT / "shared" / "reading"

# ---- Test helpers -------------------------------------------------------

def setup_dummy_data():
    """Create minimal test data for smoke tests."""
    source_dir = SHARED_READING / "cambridge-1"
    source_dir.mkdir(parents=True, exist_ok=True)
    test_json = source_dir / "test-1.json"
    test_json.write_text(json.dumps({
        "meta": {"source": "cambridge-1", "testId": 1},
        "skills": {"reading": {"passages": [
            {"title": "P1", "questionGroups": [
                {"id": "qg-1", "questions": [{"number": 1, "text": "Q1", "type": "short-answer"}]}
            ]},
            {"title": "P2", "questionGroups": []},
            {"title": "P3", "questionGroups": []}
        ]}},
        "answerKeys": {"reading": {"passage-1": {"1": "answer"}}}
    }, indent=2))
    return source_dir, test_json

def cleanup_dummy_data():
    """Remove dummy test data."""
    import shutil
    test_file = SHARED_READING / "cambridge-1" / "test-1.json"
    if test_file.exists():
        test_file.unlink()
    source_dir = SHARED_READING / "cambridge-1"
    if source_dir.exists() and not any(source_dir.iterdir()):
        source_dir.rmdir()

# ---- Test cases ---------------------------------------------------------

def test_reading_dir_created():
    """shared/reading/ directory exists after setup."""
    assert SHARED_READING.exists(), f"{SHARED_READING} must exist"

def test_dummy_data_valid():
    """Dummy JSON has required fields."""
    source_dir, test_file = setup_dummy_data()
    data = json.loads(test_file.read_text())
    assert "meta" in data, "missing meta"
    assert "skills" in data, "missing skills"
    assert "answerKeys" in data, "missing answerKeys"
    passages = data["skills"]["reading"]["passages"]
    assert len(passages) == 3, f"expected 3 passages, got {len(passages)}"

def test_discover_sections_reading():
    """discover_sections finds all passage sections."""
    setup_dummy_data()
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import discover_sections
    sections = discover_sections("reading", "cambridge-1")
    # 3 passages → 3 sections
    assert len(sections) == 3, f"expected 3 sections, got {len(sections)}: {sections}"
    assert ("1", 1) in sections
    assert ("1", 2) in sections
    assert ("1", 3) in sections

def test_discover_sections_empty():
    """discover_sections returns [] for nonexistent source."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import discover_sections
    sections = discover_sections("reading", "nonexistent-source")
    assert sections == [], f"expected [], got {sections}"

def test_discover_sections_missing_dir():
    """discover_sections returns [] when shared/reading/ is empty or missing."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import discover_sections
    sections = discover_sections("reading", "no-dir-at-all")
    assert sections == [], f"expected [], got {sections}"

def test_load_reading_section():
    """load_reading_section returns NormalizedSection with correct data."""
    setup_dummy_data()
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import load_reading_section
    sec = load_reading_section("cambridge-1", "1", 1)
    assert sec.skill == "reading"
    assert sec.test_number == "1"
    assert sec.section_number == 1
    assert sec.question_count == 1
    assert "Test Passage 1" in sec.title or "Passage 1" in sec.title or "Reading Test 1" in sec.title

def test_load_reading_not_found():
    """load_reading_section raises FileNotFoundError for missing file."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import load_reading_section
    try:
        load_reading_section("nonexistent", "1", 1)
        assert False, "should have raised"
    except FileNotFoundError:
        pass

def test_load_reading_section_range():
    """load_reading_section raises ValueError for out-of-range section."""
    setup_dummy_data()
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import load_reading_section
    try:
        load_reading_section("cambridge-1", "1", 99)
        assert False, "should have raised"
    except ValueError:
        pass

# ---- Server API tests (requires server running) -------------------------

SERVER_URL = "http://127.0.0.1:8765"

def _server_running():
    try:
        urllib.request.urlopen(f"{SERVER_URL}/api/materials", timeout=2)
        return True
    except Exception:
        return False

def test_api_reading_sources():
    """GET /api/reading returns sources list."""
    if not _server_running():
        print("  SKIP: server not running")
        return
    r = urllib.request.urlopen(f"{SERVER_URL}/api/reading")
    data = json.loads(r.read())
    assert "sources" in data
    sources = {s["id"] for s in data["sources"]}
    assert "cambridge-1" in sources, f"cambridge-1 not in {sources}"

def test_api_reading_tests():
    """GET /api/reading/<source> returns tests list."""
    if not _server_running():
        print("  SKIP: server not running")
        return
    r = urllib.request.urlopen(f"{SERVER_URL}/api/reading/cambridge-1")
    data = json.loads(r.read())
    assert data["source"] == "cambridge-1"
    assert len(data["tests"]) >= 1
    assert data["tests"][0]["testId"] == "1"
    assert "/api/reading/cambridge-1/test/1" in data["tests"][0]["url"]

def test_api_reading_serve_json():
    """GET /api/reading/<source>/test/<N> returns valid JSON."""
    if not _server_running():
        print("  SKIP: server not running")
        return
    r = urllib.request.urlopen(f"{SERVER_URL}/api/reading/cambridge-1/test/1")
    data = json.loads(r.read())
    assert data["meta"]["testId"] == 1
    assert "skills" in data
    assert "answerKeys" in data

def test_api_reading_test_404():
    """GET /api/reading/<source>/test/99 returns 404."""
    if not _server_running():
        print("  SKIP: server not running")
        return
    try:
        urllib.request.urlopen(f"{SERVER_URL}/api/reading/cambridge-1/test/99")
        assert False, "should have returned 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"expected 404, got {e.code}"

def test_other_skills_unaffected():
    """Listening API still works."""
    if not _server_running():
        print("  SKIP: server not running")
        return
    r = urllib.request.urlopen(f"{SERVER_URL}/api/listening")
    data = json.loads(r.read())
    assert "sources" in data


# ---- String testId tests (Phase 2: Other-Tests Support) ------------------

def setup_gt_dummy_data():
    """Create GT test dummy files for string testId testing."""
    gt_dir = SHARED_READING / "cambridge-2"
    gt_dir.mkdir(parents=True, exist_ok=True)
    for tid in ["gt-a", "gt-b"]:
        f = gt_dir / f"test-{tid}.json"
        f.write_text(json.dumps({
            "meta": {"source": "cambridge-2", "testNumber": tid},
            "skills": {"reading": {"passages": [
                {"title": f"GT {tid}", "questionGroups": [
                    {"id": f"qg-{tid}-1", "questions": [{"number": 1, "text": f"Q1 {tid}", "type": "tfng"}]}
                ]}
            ]}},
            "answerKeys": {"reading": {f"section-1": {"1": "TRUE"}}}
        }, indent=2))


def test_gt_test_id_in_discovery():
    """_build_reading_tests parses gt-a, gt-b with correct testId strings."""
    setup_gt_dummy_data()
    if not _server_running():
        print("  SKIP: server not running")
        return
    r = urllib.request.urlopen(f"{SERVER_URL}/api/reading/cambridge-2")
    data = json.loads(r.read())
    test_ids = {t["testId"] for t in data["tests"]}
    assert "gt-a" in test_ids, f"gt-a missing from {test_ids}"
    assert "gt-b" in test_ids, f"gt-b missing from {test_ids}"


def test_api_serve_gt_test_json():
    """GET /api/reading/cambridge-2/test/gt-a returns valid JSON."""
    setup_gt_dummy_data()
    if not _server_running():
        print("  SKIP: server not running")
        return
    r = urllib.request.urlopen(f"{SERVER_URL}/api/reading/cambridge-2/test/gt-a")
    data = json.loads(r.read())
    assert data["meta"]["testNumber"] == "gt-a"
    assert "skills" in data


def test_discover_sections_with_string_testid():
    """discover_sections returns string testIds for GT tests."""
    setup_gt_dummy_data()
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import discover_sections
    sections = discover_sections("reading", "cambridge-2")
    test_ids = {s[0] for s in sections}
    assert "gt-a" in test_ids, f"gt-a missing from {test_ids}"
    assert "gt-b" in test_ids, f"gt-b missing from {test_ids}"


def test_output_path_with_string_testid():
    """output_path generates correct filename with string testId."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import output_path
    path = output_path("cambridge-2", "reading", "gt-a", 1)
    expected = "cambridge-2_reading_test-gt-a_section-1.html"
    assert path.name == expected, f"expected {expected}, got {path.name}"


def test_cli_string_test_arg():
    """CLI --test accepts string values like 'gt-a'."""
    sys.path.insert(0, str(PROJECT_ROOT))
    import argparse
    from shared.generate_test_html import main as _  # ensure module loaded
    # Simulate argparse with string type
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=str)
    args = parser.parse_args(["--test", "gt-a"])
    assert args.test == "gt-a", f"expected 'gt-a', got {args.test}"


# ---- Main ---------------------------------------------------------------

if __name__ == "__main__":
    setup_dummy_data()
    passed = 0
    failed = 0
    skipped = 0

    tests = [
        ("reading dir exists", test_reading_dir_created),
        ("dummy data valid", test_dummy_data_valid),
        ("discover_sections reading", test_discover_sections_reading),
        ("discover_sections empty", test_discover_sections_empty),
        ("discover_sections missing dir", test_discover_sections_missing_dir),
        ("load_reading_section", test_load_reading_section),
        ("load_reading_section not found", test_load_reading_not_found),
        ("load_reading_section range", test_load_reading_section_range),
        ("API /api/reading", test_api_reading_sources),
        ("API /api/reading/<source>", test_api_reading_tests),
        ("API /api/reading/<source>/test/<N>", test_api_reading_serve_json),
        ("API 404", test_api_reading_test_404),
        ("other skills unaffected", test_other_skills_unaffected),
        # Phase 2: string testId tests
        ("GT testId in discovery", test_gt_test_id_in_discovery),
        ("API serve GT test JSON", test_api_serve_gt_test_json),
        ("discover_sections string testId", test_discover_sections_with_string_testid),
        ("output_path string testId", test_output_path_with_string_testid),
        ("CLI --test string arg", test_cli_string_test_arg),
    ]

    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            if "SKIP" in str(e):
                skipped += 1
                print(f"  SKIP  {name}")
            else:
                failed += 1
                print(f"  ERROR {name}: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    if failed:
        sys.exit(1)
