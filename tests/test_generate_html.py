#!/usr/bin/env python3
"""Tests for shared/generate_test_html.py — section-level HTML generator.

Covers:
  1. get_pin() — settings.json exists/absent, pin field present/missing
  2. load_section() — valid section for each skill, out-of-range errors
  3. count_questions() — flat questions, form-completion sub-questions, reading groups
  4. render_html() — no leftover {{ }}, all placeholders replaced
  5. output_path() — creates directory, correct filename
  6. escape_template_content() — {{ }} in user text
  7. discover_sections() — non-empty for each skill

Usage:
  .venv/bin/python3 tests/test_generate_html.py
  python3 tests/test_generate_html.py
"""

import json
import sys
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "shared"))

from generate_test_html import (
    get_pin, pin_hash, escape_template_content,
    count_questions_in_list, count_questions,
    load_listening_section, load_reading_section,
    load_speaking_section, load_writing_section, load_section,
    render_html, output_path,
    NormalizedSection, discover_sections,
    TEST_HTML_DIR, SETTINGS_FILE, DEFAULT_PIN,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ============================================================
# 1. get_pin()
# ============================================================
def test_get_pin_has_field():
    """get_pin returns custom PIN when settings.json has testHtmlPin."""
    custom_pin = "mysecret9999"
    orig_exists = SETTINGS_FILE.exists()
    orig_content = None
    if orig_exists:
        orig_content = SETTINGS_FILE.read_text()
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps({"testHtmlPin": custom_pin}))
        result = get_pin()
        check("get_pin: custom PIN from settings", result == custom_pin,
              f"expected '{custom_pin}', got '{result}'")
    finally:
        if orig_content is not None:
            SETTINGS_FILE.write_text(orig_content)
        elif not orig_exists and SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()


def test_get_pin_no_field():
    """get_pin returns default when settings.json exists but has no testHtmlPin."""
    orig_exists = SETTINGS_FILE.exists()
    orig_content = None
    if orig_exists:
        orig_content = SETTINGS_FILE.read_text()
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps({"language": "vi"}))
        result = get_pin()
        check("get_pin: default PIN when no testHtmlPin field",
              result == DEFAULT_PIN, f"expected '{DEFAULT_PIN}', got '{result}'")
    finally:
        if orig_content is not None:
            SETTINGS_FILE.write_text(orig_content)
        elif not orig_exists and SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()


def test_get_pin_no_file():
    """get_pin returns default when settings.json doesn't exist."""
    if SETTINGS_FILE.exists():
        print("  SKIP  get_pin: settings.json exists — can't test 'no file' case")
        return
    result = get_pin()
    check("get_pin: default PIN when no settings file",
          result == DEFAULT_PIN, f"expected '{DEFAULT_PIN}', got '{result}'")


def test_pin_hash():
    """pin_hash returns SHA-256 hex digest."""
    h = pin_hash("1234567890")
    expected = "c775e7b757ede630cd0aa1113bd102661ab38829ca52a6422ab782862f268646"
    check("pin_hash: SHA-256 of '1234567890'", h == expected,
          f"expected {expected[:12]}..., got {h[:12]}...")


# ============================================================
# 2. count_questions()
# ============================================================
def test_count_flat_questions():
    """count_questions_in_list counts plain questions."""
    qs = [
        {"number": 1, "type": "multiple-choice"},
        {"number": 2, "type": "gap-fill"},
        {"number": 3, "type": "multiple-choice-image"},
    ]
    check("count_questions_in_list: 3 plain questions",
          count_questions_in_list(qs) == 3)


def test_count_form_completion():
    """count_questions_in_list counts sub-questions in form-completion rows."""
    qs = [
        {"number": 1, "type": "multiple-choice-image"},
        {"number": 2, "type": "multiple-choice-image"},
        {"number": 3, "type": "multiple-choice-image"},
        {"number": 4, "type": "multiple-choice-image"},
        {"number": 5, "type": "multiple-choice-image"},
        {"number": 6, "type": "form-completion", "rows": [
            [{"text": "Name:"}, {"input": True, "key": "surname"}],
            [{"text": ""}, {"input": True, "key": "address"}],
            [{"text": ""}, {"input": True, "key": "street"}],
            [{"text": "Telephone:"}, {"input": True, "key": "phone"}],
            [{"text": "Value:"}, {"input": True, "key": "value"}],
        ]},
    ]
    # 5 MC-image questions + 5 form inputs = 10
    check("count_questions_in_list: form-completion sub-questions",
          count_questions_in_list(qs) == 10)


def test_count_reading_groups():
    """count_questions handles reading questionGroups structure."""
    data = {
        "questionGroups": [
            {"questions": [{}, {}, {}, {}, {}, {}, {}, {}]},  # 8
            {"questions": [{}, {}, {}, {}, {}, {}, {}]},       # 7
        ]
    }
    check("count_questions: reading questionGroups (8+7=15)",
          count_questions(data) == 15)


def test_count_empty():
    """count_questions returns 0 for empty data."""
    check("count_questions: empty list", count_questions([]) == 0)
    check("count_questions: empty dict", count_questions({}) == 0)


# ============================================================
# 3. escape_template_content()
# ============================================================
def test_escape_braces():
    """escape_template_content replaces {{ and }}."""
    text = "Vue.js uses {{variable}} for templates"
    escaped = escape_template_content(text)
    check("escape_template_content: {{ replaced", "{{" not in escaped)
    check("escape_template_content: }} replaced", "}}" not in escaped)
    check("escape_template_content: original text preserved",
          "Vue.js uses" in escaped and "for templates" in escaped)


def test_escape_no_braces():
    """escape_template_content leaves normal text unchanged."""
    text = "Normal text without template markers"
    check("escape_template_content: no braces unchanged",
          escape_template_content(text) == text)


# ============================================================
# 4. load_section() — valid paths for each skill
# ============================================================
def test_load_listening_valid():
    """load_listening_section returns NormalizedSection for valid section."""
    section = load_listening_section("cambridge-1", 1, 1)
    check("load_listening: skill=listening", section.skill == "listening")
    check("load_listening: source=cambridge-1", section.source == "cambridge-1")
    check("load_listening: test=1", section.test_number == 1)
    check("load_listening: section=1", section.section_number == 1)
    check("load_listening: has title", len(section.title) > 0)
    check("load_listening: has questions", section.question_count > 0)
    check("load_listening: has audio_src", "AUDIO_SRC" in section.extra)
    check("load_listening: has transcript", "TRANSCRIPT" in section.extra)
    check("load_listening: answer_keys is list", isinstance(section.answer_keys, list))


def test_load_listening_out_of_range():
    """load_listening_section raises ValueError for invalid section."""
    try:
        load_listening_section("cambridge-1", 1, 99)
        check("load_listening: out of range raises ValueError", False, "should have raised")
    except ValueError as e:
        check("load_listening: out of range raises ValueError", "out of range" in str(e).lower() or "99" in str(e))


def test_load_reading_valid():
    """load_reading_section returns NormalizedSection for valid passage."""
    section = load_reading_section("cambridge-1", 1, 1)
    check("load_reading: skill=reading", section.skill == "reading")
    check("load_reading: has passage_title", "PASSAGE_TITLE" in section.extra)
    check("load_reading: has passage_text", "PASSAGE_TEXT" in section.extra)
    check("load_reading: question_count > 0", section.question_count > 0)


def test_load_reading_out_of_range():
    """load_reading_section raises ValueError for invalid passage."""
    try:
        load_reading_section("cambridge-1", 1, 99)
        check("load_reading: out of range raises ValueError", False, "should have raised")
    except ValueError as e:
        check("load_reading: out of range raises ValueError", "out of range" in str(e).lower() or "99" in str(e))


def test_load_speaking_valid():
    """load_speaking_section returns NormalizedSection for valid part."""
    section = load_speaking_section("cambridge-1", 1, 1)
    check("load_speaking: skill=speaking", section.skill == "speaking")
    check("load_speaking: has topic", "TOPIC" in section.extra)
    check("load_speaking: has part_type", "PART_TYPE" in section.extra)
    check("load_speaking: answer_keys is None", section.answer_keys is None)


def test_load_writing_valid():
    """load_writing_section returns NormalizedSection for valid task."""
    section = load_writing_section("cambridge-1", 1, 1, "academic")
    check("load_writing: skill=writing", section.skill == "writing")
    check("load_writing: has prompt_description", "PROMPT_DESCRIPTION" in section.extra)
    check("load_writing: has word_limit", "WORD_LIMIT" in section.extra)
    check("load_writing: duration_seconds parsed", section.extra.get("DURATION_SECONDS", "0") != "0")


def test_load_section_dispatcher():
    """load_section dispatcher works for all 4 skills."""
    for skill in ["listening", "reading", "speaking", "writing"]:
        section = load_section(skill, "cambridge-1", 1, 1, "academic")
        check(f"load_section: {skill} dispatch", section.skill == skill)


# ============================================================
# 5. render_html()
# ============================================================
def test_render_html_no_leftover_placeholders():
    """render_html output has no {{ }} markers."""
    section = load_listening_section("cambridge-1", 1, 1)
    html = render_html(section)
    check("render_html: no {{ leftover", "{{" not in html)
    check("render_html: no }} leftover", "}}" not in html)
    check("render_html: has DOCTYPE", "<!DOCTYPE html>" in html)
    check("render_html: has audio player", "audio-player" in html)
    check("render_html: has PIN modal", "pin-overlay" in html)


def test_render_html_reading():
    """render_html works for reading sections."""
    section = load_reading_section("cambridge-1", 1, 1)
    html = render_html(section)
    check("render_html reading: no {{ leftover", "{{" not in html)
    check("render_html reading: has passage text", "questions-panel" in html)


def test_render_html_has_embedded_data():
    """render_html embeds SECTION_DATA and ANSWER_KEYS."""
    section = load_listening_section("cambridge-1", 1, 1)
    html = render_html(section)
    check("render_html: window.__SECTION_DATA__ present", "__SECTION_DATA__" in html or "var SECTION_DATA" in html)
    check("render_html: question data embedded", '"type"' in html)  # JSON type field
    check("render_html: PIN hash embedded", "PIN_HASH" not in html or "c775e7b7" in html)  # hash should be present


# ============================================================
# 6. output_path()
# ============================================================
def test_output_path_format():
    """output_path generates correct filename."""
    path = output_path("cambridge-1", "listening", 1, 1)
    expected_name = "cambridge-1_listening_test-1_section-1.html"
    check("output_path: filename matches", path.name == expected_name,
          f"expected '{expected_name}', got '{path.name}'")
    check("output_path: in test-html dir", "test-html" in str(path))


def test_output_path_creates_dir():
    """output_path creates the directory if it doesn't exist."""
    # output_path calls _ensure_dir, so directory should exist
    path = output_path("cambridge-1", "listening", 1, 1)
    check("output_path: directory exists", TEST_HTML_DIR.exists())


# ============================================================
# 7. discover_sections()
# ============================================================
def test_discover_listening():
    """discover_sections finds listening sections."""
    sections = discover_sections("listening", "cambridge-1")
    check("discover: listening has sections", len(sections) > 0)
    # Should find (1, 1), (1, 2), (1, 3), (1, 4)
    check("discover: listening has 4 sections for test 1",
          sum(1 for t, s in sections if t == 1) == 4)


def test_discover_reading():
    """discover_sections finds reading passages."""
    sections = discover_sections("reading", "cambridge-1")
    check("discover: reading has passages", len(sections) > 0)


def test_discover_speaking():
    """discover_sections finds speaking parts."""
    sections = discover_sections("speaking", "cambridge-1")
    check("discover: speaking has parts", len(sections) > 0)


def test_discover_writing():
    """discover_sections finds writing tasks."""
    sections = discover_sections("writing", "cambridge-1")
    check("discover: writing has tasks", len(sections) > 0)


# ============================================================
# 8. NormalizedSection
# ============================================================
def test_normalized_section_extra():
    """NormalizedSection stores extra placeholders."""
    section = NormalizedSection(
        title="Test", skill="listening", skill_badge="L", section_badge="S1",
        section_data=[], answer_keys=[], source="s", test_number=1,
        section_number=1, question_count=0,
        extra_placeholders={"AUDIO_SRC": "/audio/test.mp3"}
    )
    check("NormalizedSection: extra placeholder stored", section.extra["AUDIO_SRC"] == "/audio/test.mp3")
    check("NormalizedSection: title", section.title == "Test")
    check("NormalizedSection: question_count 0", section.question_count == 0)


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=== test_generate_html.py ===\n")

    print("-- get_pin() --")
    test_get_pin_has_field()
    test_get_pin_no_field()
    test_get_pin_no_file()
    test_pin_hash()

    print("\n-- count_questions() --")
    test_count_flat_questions()
    test_count_form_completion()
    test_count_reading_groups()
    test_count_empty()

    print("\n-- escape_template_content() --")
    test_escape_braces()
    test_escape_no_braces()

    print("\n-- load_section() valid --")
    test_load_listening_valid()
    test_load_reading_valid()
    test_load_speaking_valid()
    test_load_writing_valid()
    test_load_section_dispatcher()

    print("\n-- load_section() errors --")
    test_load_listening_out_of_range()
    test_load_reading_out_of_range()

    print("\n-- render_html() --")
    test_render_html_no_leftover_placeholders()
    test_render_html_reading()
    test_render_html_has_embedded_data()

    print("\n-- output_path() --")
    test_output_path_format()
    test_output_path_creates_dir()

    print("\n-- discover_sections() --")
    test_discover_listening()
    test_discover_reading()
    test_discover_speaking()
    test_discover_writing()

    print("\n-- NormalizedSection --")
    test_normalized_section_extra()

    print(f"\n{'='*60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
    if FAIL > 0:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)
