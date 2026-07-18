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
        "meta": {"source": "cambridge-1", "testNumber": 1},
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
    assert (1, 1) in sections
    assert (1, 2) in sections
    assert (1, 3) in sections

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
    sec = load_reading_section("cambridge-1", 1, 1)
    assert sec.skill == "reading"
    assert sec.test_number == 1
    assert sec.section_number == 1
    assert sec.question_count == 1
    assert "Test Passage 1" in sec.title or "Passage 1" in sec.title or "Reading Test 1" in sec.title

def test_load_reading_not_found():
    """load_reading_section raises FileNotFoundError for missing file."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import load_reading_section
    try:
        load_reading_section("nonexistent", 1, 1)
        assert False, "should have raised"
    except FileNotFoundError:
        pass

def test_load_reading_section_range():
    """load_reading_section raises ValueError for out-of-range section."""
    setup_dummy_data()
    sys.path.insert(0, str(PROJECT_ROOT))
    from shared.generate_test_html import load_reading_section
    try:
        load_reading_section("cambridge-1", 1, 99)
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
    assert data["tests"][0]["testNumber"] == 1
    assert "/api/reading/cambridge-1/test/1" in data["tests"][0]["url"]

def test_api_reading_serve_json():
    """GET /api/reading/<source>/test/<N> returns valid JSON."""
    if not _server_running():
        print("  SKIP: server not running")
        return
    r = urllib.request.urlopen(f"{SERVER_URL}/api/reading/cambridge-1/test/1")
    data = json.loads(r.read())
    assert data["meta"]["testNumber"] == 1
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
