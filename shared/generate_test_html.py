#!/usr/bin/env python3
"""
Section-level HTML test generator.
Reads JSON textbook data -> renders self-contained HTML files (one per section).

Usage:
  .venv/bin/python3 shared/generate_test_html.py --skill listening --source cambridge-1 --test 1 --section 1
  .venv/bin/python3 shared/generate_test_html.py --skill reading --source cambridge-1 --test 1 --section 1
  .venv/bin/python3 shared/generate_test_html.py --skill listening --source cambridge-1 --all
  .venv/bin/python3 shared/generate_test_html.py --source cambridge-1 --all-skills
  .venv/bin/python3 shared/generate_test_html.py --skill writing --source cambridge-1 --test 1 --section 1 --module generalTraining

Output: .ielts/test-html/{source}_{skill}_test-{n}_section-{s}.html
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---- Paths -----------------------------------------------------------
SCRIPT_FILE = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_FILE.parent.parent
IELTS_DIR = PROJECT_ROOT / ".ielts"
TEST_HTML_DIR = IELTS_DIR / "test-html"
SETTINGS_FILE = IELTS_DIR / "settings.json"
INDEX_FILE = TEST_HTML_DIR / "_generated.json"
TEMPLATE_DIR = PROJECT_ROOT / "skills" / "ielts-teacher" / "templates" / "section-templates"

DEFAULT_PIN = "1234567890"

# ---- JSON source paths per skill ------------------------------------
READING_JSON_PATH = "shared/reading/{source}/test-{test}.json"

SKILL_JSON_PATHS = {
    "listening": "shared/listening/listening_{source}.json",
    "reading": READING_JSON_PATH,
    "speaking": "shared/speaking/speaking_{source}.json",
    "writing": "shared/writing/writing_{source}.json",
}

# ---- HTML template paths per skill ----------------------------------
SKILL_TEMPLATES = {
    "listening": "listening-section.html",
    "reading": "reading-section.html",
    "speaking": "speaking-section.html",
    "writing": "writing-section.html",
}

# ---- Section key mappings per skill ---------------------------------
SECTION_KEYS = {
    "listening": {"key": "sections", "num_field": "sectionNumber"},
    "reading": {"key": "passages", "num_field": None},  # 0-indexed
    "speaking": {"key": "parts", "num_field": "partNumber"},
    "writing": {"key": "tasks", "num_field": "taskNumber"},
}

SECTION_LABELS = {
    "listening": "Section",
    "reading": "Passage",
    "speaking": "Part",
    "writing": "Task",
}


# ---- NormalizedSection IR -------------------------------------------
class NormalizedSection:
    """Unified intermediate representation across all 4 skills.
    Each skill loader fills this struct; the template renderer only sees this.
    """
    def __init__(self, title, skill, skill_badge, section_badge, section_data,
                 answer_keys, source, test_number, section_number,
                 question_count, extra_placeholders=None):
        self.title = title
        self.skill = skill
        self.skill_badge = skill_badge
        self.section_badge = section_badge
        self.section_data = section_data
        self.answer_keys = answer_keys
        self.source = source
        self.test_number = test_number
        self.section_number = section_number
        self.question_count = question_count
        self.extra = extra_placeholders or {}


# ---- Utilities -------------------------------------------------------
def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def get_pin():
    """Read PIN from settings.json or use default."""
    if SETTINGS_FILE.exists():
        try:
            settings = json.loads(SETTINGS_FILE.read_text())
            return settings.get("testHtmlPin", DEFAULT_PIN)
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_PIN


def pin_hash(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def escape_template_content(text: str) -> str:
    """Escape literal {{ and }} in user content to prevent placeholder collision."""
    if not isinstance(text, str):
        return text
    return text.replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;")


def count_questions_in_list(questions: list) -> int:
    """Count questions including sub-questions in form-completion rows and pick-from-list groups."""
    count = 0
    for q in questions:
        if isinstance(q, dict):
            if q.get("type") == "pick-from-list":
                count += len(q.get("questionNumbers", []))
            elif q.get("type") == "form-completion" and "rows" in q:
                # Each input row = one question
                rows = q.get("rows", [])
                for row in rows:
                    for cell in row:
                        if isinstance(cell, dict) and cell.get("input"):
                            count += 1
            else:
                count += 1
        else:
            count += 1
    return count


def count_questions(section_data) -> int:
    """Count questions in the normalized section data."""
    if isinstance(section_data, list):
        return count_questions_in_list(section_data)
    if isinstance(section_data, dict):
        # For reading: questionGroups
        groups = section_data.get("questionGroups", [])
        if groups:
            total = 0
            for g in groups:
                qs = g.get("questions", [])
                total += count_questions_in_list(qs)
            return total
        # For speaking/writing: questions array
        qs = section_data.get("questions", [])
        if isinstance(qs, list):
            return len(qs)
    return 0


# ---- Question type alias normalization --------------------------------
# Canonical names = what the JS template switch/case expects.
# Add new aliases here as needed — no need to modify JSON or JS.

QUESTION_TYPE_CANONICAL = {
    # True/False/Not Given
    "tfng": "true-false-not-given",
    "t-f-ng": "true-false-not-given",
    "true-false-not-given": "true-false-not-given",
    # Yes/No/Not Given
    "ynng": "yes-no-not-given",
    "y-n-ng": "yes-no-not-given",
    "yes-no-not-given": "yes-no-not-given",
    # Gap fill
    "gapfill": "gap-fill",
    "gap-fill": "gap-fill",
    # Summary completion
    "summary": "summary-completion",
    "summary-completion": "summary-completion",
    # Matching
    "matching": "matching",
    "matching-headings": "matching-headings",
    # Table / form / note / sentence / diagram
    "table-completion": "table-completion",
    "form-completion": "form-completion",
    "note-completion": "note-completion",
    "sentence-completion": "sentence-completion",
    "diagram-labeling": "diagram-labeling",
    # Multiple choice
    "multiple-choice": "multiple-choice",
    # Pick from list (group multiple choice)
    "pick-from-list": "pick-from-list",
    # Short answer
    "short-answer": "short-answer",
}


def normalize_type(raw_type: str) -> str:
    """Map any type alias to its canonical JS template name.
    If unrecognized, return as-is (the JS switch default renders a text input).
    """
    if not raw_type:
        return raw_type
    key = raw_type.strip().lower().replace("_", "-")
    return QUESTION_TYPE_CANONICAL.get(key, raw_type)


def normalize_question_types_in_passages(passages: list) -> list:
    """Normalize questionType and type fields in all question groups/questions."""
    for passage in passages:
        for group in passage.get("questionGroups", []):
            if group.get("questionType"):
                group["questionType"] = normalize_type(group["questionType"])
            for q in group.get("questions", []):
                if q.get("type"):
                    q["type"] = normalize_type(q["type"])
    return passages


def normalize_question_types_in_list(questions: list) -> list:
    """Normalize type fields in a flat list of questions (listening, speaking)."""
    for q in questions:
        if isinstance(q, dict):
            if q.get("type"):
                q["type"] = normalize_type(q["type"])
    return questions


def normalize_question_images_in_list(questions: list) -> list:
    """Convert singular 'image' (string) to 'images' (array) for consistency with reading."""
    for q in questions:
        if isinstance(q, dict):
            if "image" in q and "images" not in q:
                q["images"] = [{"src": q.pop("image"), "alt": ""}]
    return questions


# ---- Data loaders (one per skill) -----------------------------------

def load_listening_section(source: str, test_num: int, section_num: int) -> NormalizedSection:
    """Extract one listening section from per-source JSON."""
    json_path = PROJECT_ROOT / SKILL_JSON_PATHS["listening"].format(source=source)
    if not json_path.exists():
        raise FileNotFoundError(f"Listening JSON not found: {json_path}")

    data = json.loads(json_path.read_text())
    tests = data.get("tests", [])

    # Find test by testNumber
    test = None
    for t in tests:
        if str(t.get("testNumber")) == str(test_num):
            test = t
            break
    if not test:
        available = [t.get("testNumber") for t in tests]
        raise ValueError(f"Test {test_num} not found in {source}. Available: {available}")

    sections = test.get("sections", [])
    if section_num < 1 or section_num > len(sections):
        raise ValueError(f"Section {section_num} out of range. Valid: 1-{len(sections)}")

    sec = sections[section_num - 1]
    questions = sec.get("questions", [])
    questions = normalize_question_types_in_list(questions)
    questions = normalize_question_images_in_list(questions)
    answer_key = sec.get("answerKey", [])

    title = f"Cambridge IELTS {source.replace('cambridge-', '')} — Listening Test {test_num}, Section {section_num}"
    audio_file = sec.get("audioFile", "")
    audio_src = f"/textbook/{source}/{audio_file}" if audio_file else ""

    return NormalizedSection(
        title=title,
        skill="listening",
        skill_badge="Listening",
        section_badge=f"Section {section_num}",
        section_data=questions,
        answer_keys=answer_key,
        source=source,
        test_number=test_num,
        section_number=section_num,
        question_count=count_questions_in_list(questions),
        extra_placeholders={
            "AUDIO_SRC": audio_src,
            "INSTRUCTIONS": sec.get("instructions", ""),
            "TRANSCRIPT": sec.get("transcript", ""),
            "IMAGES": sec.get("images", []),
        }
    )


def load_reading_section(source: str, test_id: str, section_num: int) -> NormalizedSection:
    """Extract one reading passage from per-test JSON."""
    json_path = PROJECT_ROOT / SKILL_JSON_PATHS["reading"].format(source=source, test=test_id)
    if not json_path.exists():
        raise FileNotFoundError(f"Reading JSON not found: {json_path}")

    data = json.loads(json_path.read_text())
    passages = data.get("skills", {}).get("reading", {}).get("passages", [])
    passages = normalize_question_types_in_passages(passages)
    if section_num < 1 or section_num > len(passages):
        raise ValueError(f"Passage {section_num} out of range. Valid: 1-{len(passages)}")

    passage = passages[section_num - 1]
    question_groups = passage.get("questionGroups", [])
    total_questions = sum(len(g.get("questions", [])) for g in question_groups)

    title = f"Cambridge IELTS {source.replace('cambridge-', '')} — Reading Test {test_id}, Passage {section_num}"
    # Support both root-level (Academic) and nested-under-skills (GT) answerKeys
    ak = data.get("answerKeys") or data.get("skills", {}).get("reading", {}).get("answerKeys", {})
    answer_keys = ak.get("reading", {})

    return NormalizedSection(
        title=title,
        skill="reading",
        skill_badge="Reading",
        section_badge=f"Passage {section_num}",
        section_data=question_groups,
        answer_keys=answer_keys,
        source=source,
        test_number=test_id,
        section_number=section_num,
        question_count=total_questions,
        extra_placeholders={
            "PASSAGE_TITLE": passage.get("title", ""),
            "PASSAGE_TEXT": passage.get("text", ""),
            "PASSAGE_IMAGES": passage.get("images", []),
        }
    )


def load_speaking_section(source: str, test_num: int, section_num: int) -> NormalizedSection:
    """Extract one speaking part from per-source JSON."""
    json_path = PROJECT_ROOT / SKILL_JSON_PATHS["speaking"].format(source=source)
    if not json_path.exists():
        raise FileNotFoundError(f"Speaking JSON not found: {json_path}")

    data = json.loads(json_path.read_text())
    tests = data.get("tests", [])

    test = None
    for t in tests:
        if t.get("testNumber") == test_num:
            test = t
            break
    if not test:
        available = [t.get("testNumber") for t in tests]
        raise ValueError(f"Test {test_num} not found in {source}. Available: {available}")

    parts = test.get("parts", [])
    if section_num < 1 or section_num > len(parts):
        raise ValueError(f"Part {section_num} out of range. Valid: 1-{len(parts)}")

    part = parts[section_num - 1]
    questions = part.get("questions", [])
    part_type = part.get("partType", "")

    part_type_labels = {"interview": "Part 1 — Interview", "long-turn": "Part 2 — Long Turn", "discussion": "Part 3 — Discussion"}
    title = f"Cambridge IELTS {source.replace('cambridge-', '')} — Speaking Test {test_num}, Part {section_num}"

    return NormalizedSection(
        title=title,
        skill="speaking",
        skill_badge="Speaking",
        section_badge=f"Part {section_num}",
        section_data=part,
        answer_keys=None,
        source=source,
        test_number=test_num,
        section_number=section_num,
        question_count=len(questions) if isinstance(questions, list) else 0,
        extra_placeholders={
            "PART_TYPE": part_type_labels.get(part_type, part_type),
            "TOPIC": part.get("topic", ""),
            "DURATION": part.get("duration", ""),
            "INSTRUCTIONS": part.get("instructions", ""),
        }
    )


def load_writing_section(source: str, test_num: int, section_num: int, module: str = "academic") -> NormalizedSection:
    """Extract one writing task from per-source JSON."""
    json_path = PROJECT_ROOT / SKILL_JSON_PATHS["writing"].format(source=source)
    if not json_path.exists():
        raise FileNotFoundError(f"Writing JSON not found: {json_path}")

    data = json.loads(json_path.read_text())
    module_data = data.get(module, data.get("academic", {}))
    tests = module_data.get("tests", [])

    test = None
    for t in tests:
        if t.get("testNumber") == test_num:
            test = t
            break
    if not test:
        available = [t.get("testNumber") for t in tests]
        raise ValueError(f"Test {test_num} not found in {source} ({module}). Available: {available}")

    tasks = test.get("tasks", [])
    if section_num < 1 or section_num > len(tasks):
        raise ValueError(f"Task {section_num} out of range. Valid: 1-{len(tasks)}")

    task = tasks[section_num - 1]
    duration_str = task.get("duration", "20 minutes")
    # Parse duration to seconds
    duration_seconds = 1200  # default 20 min
    try:
        parts = duration_str.split()
        if len(parts) >= 2:
            duration_seconds = int(parts[0]) * 60
    except (ValueError, IndexError):
        pass

    duration_minutes = duration_seconds // 60
    title = f"Cambridge IELTS {source.replace('cambridge-', '')} — Writing Test {test_num}, Task {section_num}"
    task_type_labels = {"report": "Task 1 — Report", "essay": "Task 2 — Essay"}

    return NormalizedSection(
        title=title,
        skill="writing",
        skill_badge="Writing",
        section_badge=f"Task {section_num}",
        section_data=task,
        answer_keys=None,
        source=source,
        test_number=test_num,
        section_number=section_num,
        question_count=1,  # writing has 1 task per section
        extra_placeholders={
            "TASK_TYPE": task_type_labels.get(task.get("taskType", ""), task.get("taskType", "")),
            "PROMPT_DESCRIPTION": task.get("promptDescription", ""),
            "PROMPT_INSTRUCTION": task.get("promptInstruction", ""),
            "WORD_LIMIT": str(task.get("wordLimit", 150)),
            "DURATION": task.get("duration", "20 minutes"),
            "DURATION_MINUTES": str(duration_minutes),
            "DURATION_SECONDS": str(duration_seconds),
            "IMAGES": task.get("images", []),
        }
    )


# ---- Loader dispatch -------------------------------------------------

LOADERS = {
    "listening": load_listening_section,
    "reading": load_reading_section,
    "speaking": load_speaking_section,
    "writing": load_writing_section,
}


def load_section(skill: str, source: str, test_id: str, section_num: int, module: str = "academic") -> NormalizedSection:
    """Dispatch to the correct loader based on skill."""
    loader = LOADERS.get(skill)
    if not loader:
        raise ValueError(f"Unknown skill: {skill}. Valid: {list(LOADERS.keys())}")
    if skill == "writing":
        return loader(source, test_id, section_num, module)
    return loader(source, test_id, section_num)


# ---- Template rendering ---------------------------------------------

def load_template(skill: str) -> str:
    tmpl_path = TEMPLATE_DIR / SKILL_TEMPLATES[skill]
    if not tmpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tmpl_path}")
    return tmpl_path.read_text()


def render_html(section: NormalizedSection) -> str:
    """Load template and replace all placeholders with section data."""
    template = load_template(section.skill)
    pin = get_pin()
    ph = pin_hash(pin)

    # Build placeholder map
    placeholders = {
        "TITLE": section.title,
        "SKILL": section.skill,
        "SKILL_BADGE": section.skill_badge,
        "SECTION_BADGE": section.section_badge,
        "SECTION_DATA": json.dumps(section.section_data, ensure_ascii=False),
        "ANSWER_KEYS": json.dumps(section.answer_keys, ensure_ascii=False) if section.answer_keys is not None else "null",
        "PIN_HASH": ph,
        "SOURCE": section.source,
        "TEST_NUMBER": json.dumps(section.test_number, ensure_ascii=False),
        "SECTION_NUMBER": json.dumps(section.section_number, ensure_ascii=False),

        "QUESTION_COUNT": str(section.question_count),
    }

    # Add skill-specific extra placeholders
    # JS-context placeholders: used in <script> as JS values → JSON-encode
    JS_CONTEXT_KEYS = {"TRANSCRIPT", "PASSAGE_IMAGES", "IMAGES"}
    for key, value in section.extra.items():
        if isinstance(value, (list, dict)):
            placeholders[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, str):
            if key in JS_CONTEXT_KEYS:
                # JSON-encode for JS context: "" → valid JS empty string
                placeholders[key] = json.dumps(escape_template_content(value), ensure_ascii=False)
            else:
                # HTML context: plain string, escape template delimiters only
                placeholders[key] = escape_template_content(value)
        elif value is None:
            placeholders[key] = "null"
        else:
            placeholders[key] = str(value)

    # Replace all {{PLACEHOLDER}} markers
    html = template
    for key, value in placeholders.items():
        html = html.replace("{{" + key + "}}", value)

    return html


# ---- Output ----------------------------------------------------------

def output_path(source: str, skill: str, test_id: str, section_num: int) -> Path:
    filename = f"{source}_{skill}_test-{test_id}_section-{section_num}.html"
    _ensure_dir(TEST_HTML_DIR)
    return TEST_HTML_DIR / filename


def write_html(path: Path, html: str, force: bool = False):
    if path.exists() and not force:
        raise FileExistsError(f"File already exists: {path}. Use --force to overwrite.")
    path.write_text(html, encoding="utf-8")


def update_index(section: NormalizedSection, filepath: Path):
    """Append/update entry in _generated.json index."""
    _ensure_dir(TEST_HTML_DIR)
    if INDEX_FILE.exists():
        try:
            index = json.loads(INDEX_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            index = {"generatedAt": _now(), "sections": []}
    else:
        index = {"generatedAt": _now(), "sections": []}

    # Question types from section data
    question_types = []
    if isinstance(section.section_data, list):
        for q in section.section_data:
            if isinstance(q, dict) and "type" in q:
                qt = q["type"]
                if qt not in question_types:
                    question_types.append(qt)
    elif isinstance(section.section_data, dict):
        for group in section.section_data.get("questionGroups", []):
            qt = group.get("questionType", "")
            if qt and qt not in question_types:
                question_types.append(qt)

    # Upsert: update existing entry or append new
    rel_path = str(filepath.relative_to(PROJECT_ROOT))
    for entry in index["sections"]:
        if entry.get("path") == rel_path:
            entry["questionCount"] = section.question_count
            entry["questionTypes"] = question_types
            entry["generatedAt"] = _now()
            break
    else:
        index["sections"].append({
            "path": rel_path,
            "textbook": section.source,
            "skill": section.skill,
            "testNumber": section.test_number,
            "sectionNumber": section.section_number,
            "title": section.title,
            "questionCount": section.question_count,
            "questionTypes": question_types,
            "generatedAt": _now(),
        })

    index["generatedAt"] = _now()
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


# ---- Batch discovery -------------------------------------------------

def discover_sections(skill: str, source: str, module: str = "academic") -> list:
    """Discover all available (test_num, section_num) pairs for a skill+source."""
    sections = []
    try:
        if skill == "reading":
            # Reading is per-test: scan shared/reading/{source}/test-*.json
            import re
            json_dir = PROJECT_ROOT / "shared" / "reading" / source
            if json_dir.exists():
                for f in sorted(json_dir.glob("test-*.json")):
                    m = re.search(r'test-(.+)\.json', f.name)
                    if m:
                        test_id = m.group(1)
                        data = json.loads(f.read_text())
                        passages = data.get("skills", {}).get("reading", {}).get("passages", [])
                        for i in range(len(passages)):
                            sections.append((test_id, i + 1))
        else:
            json_path_str = SKILL_JSON_PATHS[skill].format(source=source)
            json_path = PROJECT_ROOT / json_path_str
            if not json_path.exists():
                return []
            data = json.loads(json_path.read_text())

            if skill == "writing":
                module_data = data.get(module, data.get("academic", {}))
                tests = module_data.get("tests", [])
                for t in tests:
                    tn = t.get("testNumber")
                    tasks = t.get("tasks", [])
                    for i in range(len(tasks)):
                        sections.append((tn, i + 1))
            else:
                list_key = SECTION_KEYS[skill]["key"]
                num_field = SECTION_KEYS[skill]["num_field"]
                tests = data.get("tests", [])
                for t in tests:
                    tn = t.get("testNumber")
                    items = t.get(list_key, [])
                    for i, item in enumerate(items):
                        sn = item.get(num_field, i + 1) if num_field else (i + 1)
                        sections.append((tn, sn))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"Warning: Error discovering sections for {skill}/{source}: {e}", file=sys.stderr)
    return sections


# ---- CLI -------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate section-level IELTS test HTML files from JSON textbook data."
    )
    parser.add_argument("--skill",
                        choices=["listening", "reading", "speaking", "writing"],
                        help="Skill to generate test for (required unless --all-skills)")
    parser.add_argument("--source", required=True,
                        help="Textbook source (e.g., cambridge-1)")
    parser.add_argument("--test", type=str, help="Test number or ID (required unless --all)")
    parser.add_argument("--section", type=int, help="Section/Passage/Part/Task number (required unless --all)")
    parser.add_argument("--module", choices=["academic", "generalTraining"], default="academic",
                        help="Writing module (writing skill only, default: academic)")
    parser.add_argument("--all", action="store_true",
                        help="Generate all sections for the given skill + source")
    parser.add_argument("--all-skills", action="store_true",
                        help="Generate all sections for all skills for the given source")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing output files")
    args = parser.parse_args()

    # Validate
    if not args.all_skills and not args.skill:
        parser.error("--skill is required (or use --all-skills)")
    if not args.all and not args.all_skills:
        if args.test is None:
            parser.error("--test is required (or use --all)")
        if args.section is None:
            parser.error("--section is required (or use --all)")

    # ---- Batch mode: all sections per skill ----
    if args.all:
        sections = discover_sections(args.skill, args.source, args.module)
        # Khi --test được truyền cùng --all, chỉ generate test đó, không quét toàn bộ
        if args.test is not None:
            sections = [(tid, sn) for tid, sn in sections if tid == args.test]
            if not sections:
                print(f"No sections found for test '{args.test}' in {args.skill}/{args.source}")
                sys.exit(1)
        if not sections:
            print(f"No sections found for {args.skill}/{args.source}")
            sys.exit(1)

        print(f"Generating {len(sections)} HTML files for {args.skill}/{args.source}...")
        generated = 0
        for test_id, section_num in sections:
            try:
                section = load_section(args.skill, args.source, test_id, section_num, args.module)
                html = render_html(section)
                out = output_path(args.source, args.skill, test_id, section_num)
                write_html(out, html, force=args.force)
                update_index(section, out)
                print(f"  OK  {out.name}  ({section.question_count} questions)")
                generated += 1
            except Exception as e:
                print(f"  FAIL  test-{test_id}_section-{section_num}: {e}", file=sys.stderr)

        print(f"\nDone: {generated}/{len(sections)} files generated.")
        print(f"Output: {TEST_HTML_DIR}/")
        print(f"Index:  {INDEX_FILE}")
        sys.exit(0 if generated == len(sections) else 1)

    # ---- Batch mode: all skills ----
    if args.all_skills:
        total = 0
        for skill in ["listening", "reading", "speaking", "writing"]:
            sections = discover_sections(skill, args.source, args.module)
            if not sections:
                print(f"{skill}: No sections found — skipping")
                continue
            print(f"\n{skill}: {len(sections)} sections")
            for test_id, section_num in sections:
                try:
                    section = load_section(skill, args.source, test_id, section_num, args.module)
                    html = render_html(section)
                    out = output_path(args.source, skill, test_id, section_num)
                    write_html(out, html, force=args.force)
                    update_index(section, out)
                    print(f"  OK  {out.name}  ({section.question_count} questions)")
                    total += 1
                except Exception as e:
                    print(f"  FAIL  test-{test_id}_section-{section_num}: {e}", file=sys.stderr)

        print(f"\nDone: {total} files generated across all skills.")
        print(f"Output: {TEST_HTML_DIR}/")
        print(f"Index:  {INDEX_FILE}")
        sys.exit(0)

    # ---- Single section mode ----
    try:
        section = load_section(args.skill, args.source, args.test, args.section, args.module)
        html = render_html(section)
        out = output_path(args.source, args.skill, args.test, args.section)
        write_html(out, html, force=args.force)
        update_index(section, out)

        print(f"OK  {out}")
        print(f"    Skill:    {section.skill}  |  {section.section_badge}")
        print(f"    Source:   {section.source}  |  Test {section.test_number}")
        print(f"    Questions: {section.question_count}")
        print(f"    PIN:      {get_pin()[:4]}... (hash: {pin_hash(get_pin())[:12]}...)")
        label = SECTION_LABELS.get(args.skill, "Section")
        print(f"    Open:     open {out}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
