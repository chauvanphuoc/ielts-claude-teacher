#!/usr/bin/env python3
"""Extract listening test data from Cambridge IELTS textbook markdown.

Reads Cambridge_IELTS_1.md, finds all LISTENING sections (questions + answer keys
+ transcripts), maps audio files, and generates structured JSON.

Usage:
  .venv/bin/python3 shared/listening/extract_listening.py \
    --source textbook/cambridge-1/textbook/Cambridge_IELTS_1.md \
    --audio-dir textbook/cambridge-1 \
    --output shared/listening/listening_cambridge-1.json
"""

import argparse, json, os, re, sys
from pathlib import Path
from datetime import datetime, timezone


def find_listening_tests(lines):
    """Find all LISTENING question sections. Returns list of (test_num, start_line, end_line)."""
    tests = []
    test_num = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Match "#### **LISTENING**" — start of a new test's listening questions
        if re.match(r'^####\s+\*\*LISTENING\*\*$', line):
            test_num += 1
            # Find the end: next "#### **LISTENING**" or "#### **PRACTICE TEST" or "#### **LISTENING KEYS**"
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if re.match(r'^####\s+\*\*LISTENING\*\*$', nxt):
                    break
                if re.match(r'^####\s+\*\*LISTENING KEYS?\*\*$', nxt):
                    break
                if re.match(r'^####\s+\*\*PRACTICE TEST', nxt):
                    break
                j += 1
            tests.append((test_num, i, j))
            i = j
            continue
        i += 1
    return tests


def find_listening_keys(lines):
    """Find all LISTENING KEYS sections. Returns list of (test_num, start_line, end_line)."""
    keys = []
    test_num = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^####\s+\*\*LISTENING KEYS?\*\*$', line):
            test_num += 1
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if re.match(r'^####\s+\*\*LISTENING KEYS?\*\*$', nxt):
                    break
                if re.match(r'^####\s+\*\*PRACTICE TEST', nxt):
                    break
                if re.match(r'^####\s+\*\*READING\*\*$', nxt):
                    break
                if re.match(r'^#+\s+\*\*READING\*\*', nxt):
                    break
                j += 1
            keys.append((test_num, i, j))
            i = j
            continue
        i += 1
    return keys


def find_transcripts(lines):
    """Find transcript sections. Returns list of (test_num, start_line, end_line)."""
    transcripts = []
    # Transcripts start after the answer keys section, under headings like:
    # "#### **SECTION 1**" followed by dialogue text
    # They're preceded by "## Transcripts" or similar
    in_transcripts = False
    test_num = 0
    current_test_start = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^##\s+Transcripts?', line, re.IGNORECASE):
            in_transcripts = True
        elif in_transcripts:
            if re.match(r'^####\s+\*\*SECTION [1234]\*\*$', line):
                if current_test_start is None:
                    # Determine test number from context
                    test_num += 1
                    current_test_start = i
            elif re.match(r'^##\s+\*\*PRACTICE TEST', line):
                if current_test_start is not None:
                    transcripts.append((test_num, current_test_start, i))
                    current_test_start = None
            elif re.match(r'^##\s+', line) and 'TRANSCRIPT' not in line.upper():
                if current_test_start is not None:
                    transcripts.append((test_num, current_test_start, i))
                    current_test_start = None
        i += 1
    # Don't miss the last one
    if current_test_start is not None:
        transcripts.append((test_num, current_test_start, i))
    return transcripts


def parse_answer_keys(lines_section):
    """Parse answer keys from a LISTENING KEYS section. Returns dict of section -> answers."""
    sections = {}
    current_section = None
    current_answers = []

    for line in lines_section:
        stripped = line.strip()
        if not stripped:
            continue

        # Section headers
        sec_match = re.match(r'^####\s+\*?\*?Section\s+([1-4])\*?\*?', stripped, re.IGNORECASE)
        if sec_match:
            if current_section and current_answers:
                sections[current_section] = current_answers
            current_section = int(sec_match.group(1))
            current_answers = []
            continue

        # Answer lines: either bullet points or plain text
        # Format: "- A" or "- Prescott" or "- $250 million" etc.
        answer_match = re.match(r'^[-•]\s+(.+)$', stripped)
        if answer_match:
            answer = answer_match.group(1).strip()
            # Clean up notes in parentheses
            answer = re.sub(r'\s*\(must be.*?\)', '', answer)
            answer = re.sub(r'\s*\(has .*?\)', '', answer)
            answer = re.sub(r'\s*\*in any\*\s*$', '', answer)
            answer = re.sub(r'\s*\*order\*\s*$', '', answer)
            current_answers.append(answer.strip())

    if current_section and current_answers:
        sections[current_section] = current_answers

    return sections


def parse_questions_section(lines_section):
    """Parse questions from a listening test section. Returns structured question data."""
    sections = []
    current_section = None
    current_questions = []
    current_section_title = ""
    current_instructions = ""
    current_question_range = ""
    i = 0

    while i < len(lines_section):
        line = lines_section[i].strip()

        # Section header
        sec_match = re.match(r'^####\s+\*?\*?SECTION\s+([1-4])\*?\*?\s*(.*)$', line.strip('​'), re.IGNORECASE)
        if sec_match:
            if current_section is not None and current_questions:
                sections.append({
                    "sectionNumber": current_section,
                    "title": current_section_title.strip(),
                    "questionRange": current_question_range.strip(),
                    "instructions": current_instructions.strip(),
                    "questions": current_questions
                })
            current_section = int(sec_match.group(1))
            current_section_title = f"Section {current_section}"
            current_questions = []
            current_instructions = ""
            current_question_range = ""
            # Check if next line has question range
            if i + 1 < len(lines_section):
                next_line = lines_section[i + 1].strip()
                qr_match = re.match(r'^####\s+Questions?\s+(\d+[-–]\d+)', next_line, re.IGNORECASE)
                if qr_match:
                    current_question_range = f"Questions {qr_match.group(1)}"
            i += 1
            continue

        # Question range sub-heading
        qr_match = re.match(r'^####\s+Questions?\s+(\d+[-–]\d+)', line, re.IGNORECASE)
        if qr_match:
            current_question_range = f"Questions {qr_match.group(1)}"
            i += 1
            continue

        # Instructions
        instr_match = re.match(r'^\*(.+)\*$', line)
        if instr_match and current_instructions == "":
            current_instructions = instr_match.group(1)
            i += 1
            continue

        i += 1

    # Don't miss the last section
    if current_section is not None and current_questions:
        sections.append({
            "sectionNumber": current_section,
            "title": current_section_title.strip(),
            "questionRange": current_question_range.strip(),
            "instructions": current_instructions.strip(),
            "questions": current_questions
        })

    return sections


def map_audio_files(audio_dir, num_tests=4, sections_per_test=4):
    """Map expected audio files to tests and sections."""
    audio_map = {}
    audio_path = Path(audio_dir)

    if not audio_path.exists():
        return audio_map

    for test_n in range(1, num_tests + 1):
        audio_map[test_n] = {}
        for sec_n in range(1, sections_per_test + 1):
            # Try multiple naming patterns
            patterns = [
                f"Test {test_n} - Section {sec_n}.mp3",
                f"Test{test_n} - Section{sec_n}.mp3",
                f"Test {test_n} Section {sec_n}.mp3",
            ]
            for pattern in patterns:
                candidate = audio_path / pattern
                if candidate.exists():
                    audio_map[test_n][sec_n] = pattern
                    break
            if sec_n not in audio_map[test_n]:
                audio_map[test_n][sec_n] = None  # Missing

    return audio_map


def build_listening_json(source_name, audio_dir, tests_questions, answer_keys_by_test, audio_map):
    """Build the full listening JSON structure."""
    output = {
        "source": source_name,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generatedBy": "/init-textbook-listening",
        "audioBasePath": str(Path(audio_dir)),
        "tests": []
    }

    for test_n in range(1, 5):
        test_entry = {
            "testNumber": test_n,
            "sections": []
        }

        sections = tests_questions.get(test_n, [])
        answers = answer_keys_by_test.get(test_n, {})
        audio = audio_map.get(test_n, {})

        for sec in sections:
            sec_num = sec["sectionNumber"]
            sec_answers = answers.get(sec_num, [])

            # Build questions with answers
            questions_with_answers = []
            for idx, q in enumerate(sec.get("questions", [])):
                q_entry = dict(q)
                if idx < len(sec_answers):
                    answer = sec_answers[idx]
                    # Handle multi-answer (// separator)
                    if "//" in answer:
                        parts = [a.strip() for a in answer.split("//")]
                        q_entry["correctAnswer"] = parts[0]
                        q_entry["acceptableAnswers"] = parts
                    else:
                        q_entry["correctAnswer"] = answer
                questions_with_answers.append(q_entry)

            section_entry = {
                "sectionNumber": sec_num,
                "title": sec.get("title", f"Section {sec_num}"),
                "questionRange": sec.get("questionRange", ""),
                "audioFile": audio.get(sec_num),
                "instructions": sec.get("instructions", ""),
                "questions": questions_with_answers,
                "transcript": "",
                "answerKey": [{"questionNumber": idx + 1, "answer": a} for idx, a in enumerate(sec_answers)]
            }
            test_entry["sections"].append(section_entry)

        output["tests"].append(test_entry)

    return output


def validate_listening_json(json_path, audio_dir):
    """Validate an existing listening JSON file.

    Checks:
      1. JSON structure integrity
      2. Answer key count = question count per section
      3. Audio file existence
      4. Image references
      5. Ambiguous answer key format
      6. Cyrillic characters in answers

    Returns: (warnings, errors) — two lists of strings.
    """
    warnings = []
    errors = []

    if not json_path.exists():
        errors.append(f"JSON file not found: {json_path}")
        return warnings, errors

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return warnings, errors

    audio_base = Path(audio_dir)
    cyrillic_map = {'В': 'B', 'С': 'C', 'А': 'A', 'Е': 'E', 'М': 'M'}

    for test in data.get("tests", []):
        tn = test["testNumber"]
        for sec in test.get("sections", []):
            sn = sec["sectionNumber"]
            questions = sec.get("questions", [])
            answer_keys = sec.get("answerKey", [])

            # Check answer key count
            adj_q = 0
            for q in questions:
                if q["type"] == "matching-checkboxes":
                    adj_q += q.get("selectCount", len(q.get("correctAnswers", [])))
                elif q["type"] == "form-completion":
                    # Count each input cell as a separate question
                    for row in q.get("rows", []):
                        for cell in row:
                            if cell.get("input"):
                                adj_q += 1
                else:
                    adj_q += 1

            if adj_q != len(answer_keys) and len(answer_keys) > 0:
                warnings.append(
                    f"Test {tn} Section {sn}: {adj_q} questions (adj) vs {len(answer_keys)} answer keys"
                )

            # Check audio file
            audio_file = sec.get("audioFile")
            if audio_file:
                audio_path = audio_base / audio_file
                if not audio_path.exists():
                    errors.append(
                        f"Test {tn} Section {sn}: Audio file missing: {audio_file}"
                    )
            else:
                warnings.append(
                    f"Test {tn} Section {sn}: No audioFile specified"
                )

            # Check questions
            for q in questions:
                qn = q["number"]

                # Check for ambiguous answer format
                answer = q.get("correctAnswer", "")
                if "//" in answer:
                    warnings.append(
                        f"Q{qn}: Answer contains '//' — should use acceptableAnswers array: {answer}"
                    )

                # Check for Cyrillic characters
                for cyr, lat in cyrillic_map.items():
                    if cyr in answer:
                        warnings.append(
                            f"Q{qn}: Cyrillic character '{cyr}' found in answer — should be '{lat}'"
                        )

                # Check answer key has entry
                if q["type"] == "matching-checkboxes":
                    correct_count = len(q.get("correctAnswers", []))
                    key_count = sum(1 for a in answer_keys if a["questionNumber"] >= qn and a["questionNumber"] < qn + correct_count)
                    if key_count != correct_count:
                        warnings.append(
                            f"Q{qn}: matching-checkboxes expects {correct_count} correct answers, "
                            f"found {key_count} answer key entries"
                        )
                else:
                    key_match = [a for a in answer_keys if a["questionNumber"] == qn]
                    if not key_match:
                        warnings.append(f"Q{qn}: No answer key entry found")

            # Check image references in questions
            for q in questions:
                if q["type"] == "multiple-choice-image":
                    # Check question-level image (single-image mode)
                    q_img = q.get("image", "")
                    if q_img:
                        img_path = audio_base / "textbook" / q_img
                        if not img_path.exists():
                            warnings.append(
                                f"Q{q['number']}: Question image not found: {q_img}"
                            )
                    # Check option-level images (individual image mode)
                    for opt in q.get("options", []):
                        img = opt.get("image", "")
                        if img:
                            img_path = audio_base / "textbook" / img
                            if not img_path.exists():
                                warnings.append(
                                    f"Q{q['number']}: Option image not found: {img}"
                                )

    return warnings, errors


def main():
    parser = argparse.ArgumentParser(description="Extract listening test data from textbook markdown")
    parser.add_argument("--source", help="Path to textbook markdown file")
    parser.add_argument("--audio-dir", required=True, help="Path to audio directory")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate an existing JSON file, don't extract")
    args = parser.parse_args()

    # ── Validate-only mode ──
    if args.validate_only:
        if not args.output:
            print("[validate] ERROR: --output is required for --validate-only")
            sys.exit(1)
        output_path = Path(args.output)
        warnings, errors = validate_listening_json(output_path, args.audio_dir)

        if warnings:
            print(f"[validate] ⚠️  {len(warnings)} warning(s):")
            for w in warnings:
                print(f"  ⚠️  {w}")

        if errors:
            print(f"[validate] ❌ {len(errors)} error(s):")
            for e in errors:
                print(f"  ❌ {e}")

        if errors:
            print(f"\n[validate] VALIDATION FAILED — {len(errors)} errors, {len(warnings)} warnings")
            sys.exit(1)
        elif warnings:
            print(f"\n[validate] ✅ Validation passed with {len(warnings)} warning(s)")
        else:
            print(f"[validate] ✅ All checks passed — no issues found")
        return

    if not args.source or not args.output:
        print("[extract] ERROR: --source and --output are required for extraction")
        sys.exit(1)

    with open(args.source, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")

    print(f"[extract] Read {len(lines)} lines from {args.source}")

    # Find sections
    listening_tests = find_listening_tests(lines)
    print(f"[extract] Found {len(listening_tests)} listening test question sections")

    listening_keys = find_listening_keys(lines)
    print(f"[extract] Found {len(listening_keys)} listening keys sections")

    # transcripts = find_transcripts(lines)
    # print(f"[extract] Found {len(transcripts)} transcript sections")

    # Parse each test's questions
    tests_questions = {}
    for test_n, start, end in listening_tests:
        section_lines = lines[start:end]
        sections = parse_questions_section(section_lines)
        tests_questions[test_n] = sections
        total_q = sum(len(s.get("questions", [])) for s in sections)
        print(f"[extract] Test {test_n}: {len(sections)} sections, {total_q} questions extracted")

    # Parse answer keys
    answer_keys_by_test = {}
    for test_n, start, end in listening_keys:
        section_lines = lines[start:end]
        answers = parse_answer_keys(section_lines)
        answer_keys_by_test[test_n] = answers
        total_a = sum(len(v) for v in answers.values())
        print(f"[extract] Test {test_n} keys: {len(answers)} sections, {total_a} answers")

    # Map audio files
    source_name = Path(args.audio_dir).name
    audio_map = map_audio_files(args.audio_dir)

    # Verify counts
    for test_n in range(1, 5):
        q_count = sum(len(s.get("questions", [])) for s in tests_questions.get(test_n, []))
        a_count = sum(len(v) for v in answer_keys_by_test.get(test_n, {}).values())
        if q_count == 0 and a_count == 0:
            continue
        status = "✅" if q_count == a_count else "⚠️ MISMATCH"
        print(f"[extract] Test {test_n}: {q_count} questions vs {a_count} answers {status}")

    # Build JSON
    output = build_listening_json(source_name, args.audio_dir, tests_questions, answer_keys_by_test, audio_map)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_questions = sum(
        sum(len(s.get("questions", [])) for s in tests_questions.get(t, []))
        for t in range(1, 5)
    )
    print(f"[extract] Wrote {output_path} ({output_path.stat().st_size} bytes, {total_questions} total questions)")

    # ── Validate the generated JSON ──
    print(f"\n[validate] Running validation checks...")
    warnings, errors = validate_listening_json(output_path, args.audio_dir)

    if warnings:
        print(f"[validate] ⚠️  {len(warnings)} warning(s):")
        for w in warnings:
            print(f"  ⚠️  {w}")

    if errors:
        print(f"[validate] ❌ {len(errors)} error(s):")
        for e in errors:
            print(f"  ❌ {e}")
        print(f"\n[validate] VALIDATION FAILED — {len(errors)} errors found")
        sys.exit(1)

    if not warnings and not errors:
        print(f"[validate] ✅ All checks passed — no issues found")
    else:
        print(f"[validate] ✅ Validation passed with {len(warnings)} warning(s)")

    # ── Summary ──
    print(f"\n[summary] Source: {source_name}")
    print(f"[summary] Tests: {len(output['tests'])}")
    for t in output['tests']:
        tn = t['testNumber']
        sec_count = len(t['sections'])
        q_count = sum(len(s.get('questions', [])) for s in t['sections'])
        a_count = sum(len(s.get('answerKey', [])) for s in t['sections'])
        audio_ok = sum(1 for s in t['sections'] if s.get('audioFile'))
        print(f"[summary]   Test {tn}: {sec_count} sections, {q_count} questions, "
              f"{a_count} answer keys, {audio_ok}/{sec_count} audio files")


if __name__ == "__main__":
    main()
