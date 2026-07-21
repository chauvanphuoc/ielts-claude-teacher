#!/usr/bin/env python3
"""Extract listening test data from Cambridge IELTS textbook markdown.

Reads Cambridge_IELTS_N.md, finds all LISTENING sections (questions + answer keys
+ transcripts), maps audio files, and generates structured JSON.

Supports multiple markdown formats:
  - ### LISTENING           (Cambridge 1, 2 – level 3, no bold)
  - #### **LISTENING**      (alternative – level 4, bold)
  - #### LISTENING          (alternative – level 4, no bold)

Test boundary formats:
  - ## Practice Test N      (Cambridge 1)
  - ## TEST N               (Cambridge 2)

Usage:
  .venv/bin/python3 shared/listening/extract_listening.py \
    --source textbook/cambridge-1/textbook/Cambridge_IELTS_1.md \
    --audio-dir textbook/cambridge-1 \
    --output shared/listening/listening_cambridge-1.json

  .venv/bin/python3 shared/listening/extract_listening.py \
    --source textbook/cambridge-2/textbook/Cambridge_IELTS_2.md \
    --audio-dir textbook/cambridge-2 \
    --output shared/listening/listening_cambridge-2.json
"""

import argparse, json, os, re, sys
from pathlib import Path
from datetime import datetime, timezone


# ── Flexible regex patterns ──

# Test boundaries: ## Practice Test N, ## TEST N, ### TEST N, etc.
# Matches heading levels 2-4 (main content uses level 2, answer key area uses level 3)
RE_TEST_BOUNDARY = re.compile(
    r'^#{2,4}\s+\*?\*?(?:PRACTICE\s+)?TEST\s+(\d+)\*?\*?\s*(?::.*)?$',
    re.IGNORECASE
)

# Listening section heading — matches any heading level (2-4) with optional bold:
#   ### LISTENING, #### **LISTENING**, #### LISTENING, etc.
RE_LISTENING = re.compile(
    r'^#{2,4}\s+\*?\*?LISTENING\*?\*?\s*$'
)

# Other skill headings used as section-end markers
RE_SKILL = re.compile(
    r'^#{2,4}\s+\*?\*?(?:READING|WRITING|SPEAKING)\*?\*?\s*$',
    re.IGNORECASE
)

# Answer key area: ## ANSWER KEY or #### LISTENING KEYS
RE_ANSWER_KEY = re.compile(
    r'^#{2,4}\s+\*?\*?ANSWER\s+KEY\*?\*?\s*$',
    re.IGNORECASE
)
RE_LISTENING_KEYS = re.compile(
    r'^#{2,4}\s+\*?\*?LISTENING\s+KEYS?\*?\*?\s*$',
    re.IGNORECASE
)

# Section header within questions: #### SECTION N Questions X-Y
RE_SECTION = re.compile(
    r'^#{3,5}\s+\*?\*?SECTION\s+([1-4])\*?\*?\s*(?:Questions?\s+\d+[–-]\d+)?',
    re.IGNORECASE
)

# Section header within answer keys (both Cambridge 1 and 2):
#   ###### Section N          (C1)
#   ##### *Section N, Questions X-Y*  (C2)
RE_KEYS_SECTION = re.compile(
    r'^#{3,6}\s+\*?\*?Section\s+([1-4])\*?\*?\s*(?:,?\s*Questions?\s+\d+[–-]\d+)?',
    re.IGNORECASE
)

# Transcripts / tapescripts heading
RE_TRANSCRIPT = re.compile(
    r'^##\s+\*?\*?(?:TAPE)?SCRIPTS?\*?\*?\s*(?:\(LISTENING\))?\s*$',
    re.IGNORECASE
)

# Cambridge 2 answer line: * **N** answer text (with optional separator like : or —)
RE_C2_ANSWER = re.compile(r'^\*\s+\*\*(\d+)\*\*\s*[:–-—]?\s*(.+)$')

# Cambridge 2 LaTeX multi-answer: \textbf{6} && \mathbf{B} or \text{walking boots}
RE_LATEX_PAIR = re.compile(
    r'\\textbf\{(\d+)\}\s*&&\s*(?:\\mathbf\{([^}]+)\}|\\text\{([^}]+)\})'
)

# Cambridge 2 "in any order" / "in either order" note (from LaTeX \text{\textit{...}})
RE_ANY_ORDER = re.compile(r'\\text\{\\textit\{([^}]*)\}\}')


# ── Helper functions ──

def find_landmarks(lines):
    """Find major structural landmarks: answer key and transcript start lines."""
    answer_key = -1
    transcripts = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if answer_key < 0 and (RE_ANSWER_KEY.match(s) or RE_LISTENING_KEYS.match(s)):
            answer_key = i
        if transcripts < 0 and RE_TRANSCRIPT.match(s):
            transcripts = i
    return answer_key, transcripts


def find_listening_tests(lines, stop_at=-1):
    """Find all LISTENING question sections.

    Scans sequentially from the start, stops at stop_at if >= 0.
    Returns list of (test_num, start_line, end_line).
    """
    tests = []
    test_num = 0
    i = 0
    limit = stop_at if stop_at >= 0 else len(lines)

    while i < limit:
        line = lines[i].strip()
        if RE_LISTENING.match(line):
            test_num += 1
            j = i + 1
            while j < limit:
                nxt = lines[j].strip()
                if RE_LISTENING.match(nxt):
                    break
                if RE_SKILL.match(nxt):
                    break
                if RE_TEST_BOUNDARY.match(nxt):
                    break
                j += 1
            tests.append((test_num, i, j))
            i = j
            continue
        i += 1
    return tests


def find_listening_keys(lines, answer_key_start=-1, transcript_start=-1):
    """Find listening answer key sections.

    Handles both Cambridge 1 (#### LISTENING KEYS) and
    Cambridge 2 (#### LISTENING under ### TEST N) formats.

    Returns list of (test_num, start_line, end_line).
    """
    keys = []
    if answer_key_start < 0:
        return keys

    ak_end = transcript_start if transcript_start > answer_key_start else len(lines)
    test_num = 0

    i = answer_key_start
    while i < ak_end:
        line = lines[i].strip()

        # Test boundary then listening heading:
        #   Cambridge 1: ### PRACTICE TEST N > #### LISTENING (or #### LISTENING KEYS)
        #   Cambridge 2: ### TEST N > #### LISTENING
        test_m = RE_TEST_BOUNDARY.match(line)
        if test_m:
            test_num = int(test_m.group(1))
            # Look for listening answer key heading within this test's block
            # (both #### LISTENING and #### LISTENING KEYS are used)
            j = i + 1
            while j < ak_end:
                nxt = lines[j].strip()
                if RE_TEST_BOUNDARY.match(nxt):
                    break  # next test → stop looking
                if RE_LISTENING.match(nxt) or RE_LISTENING_KEYS.match(nxt):
                    # Found listening answer key for this test
                    k = j + 1
                    while k < ak_end:
                        nxt2 = lines[k].strip()
                        if RE_TEST_BOUNDARY.match(nxt2):
                            break
                        if RE_LISTENING.match(nxt2) or RE_LISTENING_KEYS.match(nxt2):
                            break
                        if RE_SKILL.match(nxt2):
                            break
                        k += 1
                    keys.append((test_num, j, k))
                    j = k
                    continue
                j += 1
            i = j
            continue

        i += 1
    return keys


def find_transcripts(lines, transcript_start=-1):
    """Find transcript sections.

    Handles both Cambridge 1 and 2 format (#### SECTION N within transcript area).

    Returns list of (test_num, start_line, end_line).
    """
    if transcript_start < 0:
        return []

    t_end = len(lines)
    transcripts = []
    test_num = 0
    current_test_start = None

    i = transcript_start
    while i < t_end:
        line = lines[i].strip()

        # Test boundary within transcripts
        test_m = RE_TEST_BOUNDARY.match(line)
        if test_m:
            test_num = int(test_m.group(1))
            current_test_start = i
            i += 1
            continue

        # Section header within transcripts
        sec_m = RE_SECTION.match(line)
        if sec_m:
            if current_test_start is None:
                current_test_start = i
            if test_num == 0:
                test_num += 1

            j = i + 1
            while j < t_end:
                nxt = lines[j].strip()
                if RE_SECTION.match(nxt):
                    break
                if RE_TEST_BOUNDARY.match(nxt):
                    break
                # Stop at any level-2 heading (major section break)
                if nxt.startswith('## ') or nxt.startswith('##\t'):
                    break
                j += 1
            transcripts.append((test_num, i, j))
            i = j
            continue

        i += 1
    return transcripts


def parse_answer_keys_v1(lines_section):
    """Parse Cambridge 1 style answer keys.

    Format:
      ###### Section 1
      1 answer
      2 answer2 // alt

    Returns dict of section_number -> [answer_string, ...]
    """
    sections = {}
    current_section = None
    current_answers = []

    for line in lines_section:
        stripped = line.strip()
        if not stripped:
            continue

        # Section headers: ###### Section N
        sec_m = RE_KEYS_SECTION.match(stripped)
        if sec_m:
            if current_section is not None and current_answers:
                sections[current_section] = current_answers
            current_section = int(sec_m.group(1))
            current_answers = []
            continue

        # Answer line: N answer
        ans_m = re.match(r'^(\d+)\s+(.+)$', stripped)
        if ans_m:
            answer = ans_m.group(2).strip()
            # Strip annotations like (do not accept "lonely")
            answer = re.sub(r'\s*\(do not accept.*?\)', '', answer)
            answer = re.sub(r'\s*\(must be.*?\)', '', answer)
            current_answers.append(answer.strip())

    if current_section is not None and current_answers:
        sections[current_section] = current_answers

    return sections


def parse_answer_keys_v2(lines_section):
    r"""Parse Cambridge 2 style answer keys.

    Format:
      ##### *Section 1, Questions 1-10*
      * **1**   Black
      * **2**   2085
      * $\begin{aligned} &\textbf{6} && \mathbf{B} \\ ... \end{aligned} \Big\} \text{\textit{in any order}}$

    Returns dict of section_number -> [answer_string, ...]
    (sorted by question number).
    """
    sections = {}
    current_section = None
    # Use dict of qnum -> answer to collect pairs, then sort
    qa_pairs = {}  # section -> [(qnum, answer), ...]

    for line in lines_section:
        stripped = line.strip()
        if not stripped:
            continue

        # Section headers: ##### *Section N, Questions X-Y*
        sec_m = RE_KEYS_SECTION.match(stripped)
        if sec_m:
            if current_section is not None and qa_pairs.get(current_section):
                # Sort existing section answers by question number
                qa_pairs[current_section].sort(key=lambda x: x[0])
            current_section = int(sec_m.group(1))
            if current_section not in qa_pairs:
                qa_pairs[current_section] = []
            continue

        # Simple answer: * **N** answer
        ans_m = RE_C2_ANSWER.match(stripped)
        if ans_m:
            qn = int(ans_m.group(1))
            answer = ans_m.group(2).strip()
            # Clean up bold markers on answer (for MC like * **1** **B**)
            answer = re.sub(r'^\*\*(.+)\*\*$', r'\1', answer)
            # Clean up annotations like *NOT* per month/monthly
            answer = re.sub(r'\s+\*NOT\*.*$', '', answer)
            # Clean up //ACCEPT annotations
            answer = re.sub(r'\s+/+ACCEPT.*$', '', answer)
            if current_section is not None:
                qa_pairs.setdefault(current_section, []).append((qn, answer))
            continue

        # LaTeX multi-answer: $\begin{aligned}... \end{aligned}$
        if '\\begin{aligned}' in stripped:
            # Extract question-answer pairs from LaTeX
            pairs = RE_LATEX_PAIR.findall(stripped)
            # Extract "in any order" / "in either order" note
            order_m = RE_ANY_ORDER.search(stripped)
            order_note = order_m.group(1) if order_m else ''

            for qn_str, ans_math, ans_text in pairs:
                qn = int(qn_str)
                answer = (ans_math or ans_text or '').strip()
                # Add order note if present
                if order_note:
                    answer = f"{answer} ({order_note})"
                if current_section is not None:
                    qa_pairs.setdefault(current_section, []).append((qn, answer))
            continue

    # Final sort for the last section
    if current_section is not None and qa_pairs.get(current_section):
        qa_pairs[current_section].sort(key=lambda x: x[0])

    # Convert to flat answer list per section
    for sec, pairs in qa_pairs.items():
        sections[sec] = [a for _, a in pairs]

    return sections


def detect_answer_format(lines_section):
    """Detect whether answer keys use Cambridge 1 or Cambridge 2 format."""
    for line in lines_section[:20]:  # Check first 20 lines
        stripped = line.strip()
        if RE_C2_ANSWER.match(stripped):
            return 'v2'
        if '\\begin{aligned}' in stripped:
            return 'v2'
        if re.match(r'^\d+\s+', stripped):
            return 'v1'
    return 'v1'  # Default


def parse_answer_keys(lines_section):
    """Parse answer keys — auto-detects format."""
    fmt = detect_answer_format(lines_section)
    if fmt == 'v2':
        return parse_answer_keys_v2(lines_section)
    else:
        return parse_answer_keys_v1(lines_section)


def parse_questions_section(lines_section):
    """Parse questions from a listening test section. Returns structured section data."""
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
        sec_match = RE_SECTION.match(line.strip())
        if sec_match:
            if current_section is not None:
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
                qr_match = re.match(r'^#{2,5}\s+Questions?\s+(\d+[-–]\d+)', next_line, re.IGNORECASE)
                if qr_match:
                    current_question_range = f"Questions {qr_match.group(1)}"
            i += 1
            continue

        # Question range sub-heading
        qr_match = re.match(r'^#{2,5}\s+Questions?\s+(\d+[-–]\d+)', line, re.IGNORECASE)
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
    if current_section is not None:
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
            patterns = [
                f"Test {test_n} - Section {sec_n}.mp3",
                f"Test{test_n} - Section{sec_n}.mp3",
                f"Test {test_n} Section {sec_n}.mp3",
            ]
            found = None
            for pattern in patterns:
                candidate = audio_path / pattern
                if candidate.exists():
                    found = pattern
                    break
            audio_map[test_n][sec_n] = found

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
                    adj_q += sum(1 for row in q.get("rows", []) for cell in row if cell.get("input"))
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
                    q_img = q.get("image", "")
                    if q_img:
                        img_path = audio_base / "textbook" / q_img
                        if not img_path.exists():
                            warnings.append(
                                f"Q{q['number']}: Question image not found: {q_img}"
                            )
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

    # Step 1: Find landmarks
    answer_key_start, transcript_start = find_landmarks(lines)
    print(f"[extract] Landmarks: answer_key={answer_key_start}, transcripts={transcript_start}")

    # Step 2: Find listening question sections (before answer key)
    stop_at = answer_key_start if answer_key_start >= 0 else transcript_start if transcript_start >= 0 else -1
    listening_tests = find_listening_tests(lines, stop_at=stop_at)
    print(f"[extract] Found {len(listening_tests)} listening test question sections")

    # Step 3: Find listening answer keys
    listening_keys = find_listening_keys(lines, answer_key_start, transcript_start)
    print(f"[extract] Found {len(listening_keys)} listening keys sections")

    # Step 4: Find transcripts
    transcripts = find_transcripts(lines, transcript_start)
    print(f"[extract] Found {len(transcripts)} transcript sections")

    # Step 5: Parse each test's questions (structural metadata)
    tests_questions = {}
    for test_n, start, end in listening_tests:
        section_lines = lines[start:end]
        sections = parse_questions_section(section_lines)
        tests_questions[test_n] = sections
        total_q = sum(len(s.get("questions", [])) for s in sections)
        print(f"[extract] Test {test_n}: {len(sections)} sections, {total_q} questions extracted")

    # Step 6: Parse answer keys
    answer_keys_by_test = {}
    for test_n, start, end in listening_keys:
        section_lines = lines[start:end]
        answers = parse_answer_keys(section_lines)
        answer_keys_by_test[test_n] = answers
        total_a = sum(len(v) for v in answers.values())
        print(f"[extract] Test {test_n} keys: {len(answers)} sections, {total_a} answers")

    # Step 7: Map audio files
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

    # Step 8: Build JSON
    output = build_listening_json(source_name, args.audio_dir, tests_questions, answer_keys_by_test, audio_map)

    # Step 9: Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_questions = sum(
        sum(len(s.get("questions", [])) for s in tests_questions.get(t, []))
        for t in range(1, 5)
    )
    print(f"[extract] Wrote {output_path} ({output_path.stat().st_size} bytes, {total_questions} total questions)")

    # Step 10: Validate the generated JSON
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

    # Summary
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
