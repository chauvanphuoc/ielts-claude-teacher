---
name: ielts-test-html
description: |
  Generate self-contained section-level HTML test files from JSON textbook data.
  Command: /create-test-html --skill {listening|reading|speaking|writing} --section-key {key}
  Each HTML file is one section (Listening Section, Reading Passage, Speaking Part, Writing Task).
  Answers are PIN-protected (soft gate). Supports dual mode: student test + cross-check with PDF.
metadata:
  version: 1.0.0
---

# Create Test HTML

Generate self-contained HTML test files from JSON textbook data. One HTML file = one section.
Dual purpose: (1) student takes the test, (2) user cross-checks JSON accuracy against PDF source.

## Command Reference

```
/create-test-html --skill {skill} --section-key {composite-key}
/create-test-html --skill {skill} --source {textbook} --all
/create-test-html --skill {skill} --source {textbook} --all --force
/create-test-html --skill writing --section-key {key} --module {academic|generalTraining}
```

| Flag | Required | Description |
|------|----------|-------------|
| `--skill` | Yes | `listening`, `reading`, `speaking`, or `writing` |
| `--section-key` | Yes (or `--all`) | Composite key: `{textbook}_test-{N}_section-{S}` |
| `--all` | Alternative to `--section-key` | Generate all sections for the given skill + source |
| `--source` | With `--all` | Textbook name only (e.g., `cambridge-1`) |
| `--module` | Writing only | `academic` (default) or `generalTraining` |
| `--force` | No | Overwrite existing files |

**--section-key format:** `{textbook-name}_test-{N}_section-{S}`
- Example: `cambridge-1_test-1_section-1` → Listening Section 1, Test 1
- Example: `cambridge-1_test-1_section-1` → Reading Passage 1, Test 1
- Example: `cambridge-1_test-1_section-1` → Speaking Part 1, Test 1
- Example: `cambridge-1_test-1_section-1` → Writing Task 1, Test 1

The user may also say things like:
- "tạo HTML test cho listening cambridge 1 test 1 section 1"
- "generate test HTML for reading cambridge-1 passage 1"
- "tạo tất cả HTML test cho cambridge 1 listening"
- "create all test HTML files for cambridge-1"

## Workflow

### Step 1: Parse Parameters

Extract from the user's request:
- `skill`: one of `listening`, `reading`, `speaking`, `writing`
- If `--section-key` is provided: parse the composite key into `textbook_name`, `test_num`, `section_num`
  - Format: `{textbook-name}_test-{N}_section-{S}`
  - Use regex: `^(.+)_test-(\d+)_section-(\d+)$`
  - Example: `cambridge-1_test-1_section-1` → textbook=`cambridge-1`, test=`1`, section=`1`
- If `--all` + `--source` is provided: batch mode — generate all sections
- `module` (writing only): default `academic`

### Step 2: Validate Inputs

Before calling the Python script, verify:
1. **JSON source exists** — check the JSON file path on disk:
   - Listening: `shared/listening/listening_{textbook}.json`
   - Reading: `shared/reading/{textbook}/test-{test}.json`
   - Speaking: `shared/speaking/speaking_{textbook}.json`
   - Writing: `shared/writing/writing_{textbook}.json`
2. **HTML template exists** — check `skills/ielts-teacher/templates/section-templates/{skill}-section.html`
3. **Section number in range** — for single-section mode, read the JSON quickly and verify section_num is within valid range

If any check fails, report the specific error and suggest the fix. Do NOT proceed to Step 3.

### Step 3: Execute Python Generator

Call the Python script with decomposed arguments:

```bash
# Single section
.venv/bin/python3 shared/generate_test_html.py \
  --skill {skill} \
  --source {textbook_name} \
  --test {test_num} \
  --section {section_num} \
  [--module {module}] \
  [--force]

# Batch: all sections for a skill
.venv/bin/python3 shared/generate_test_html.py \
  --skill {skill} \
  --source {textbook_name} \
  --all \
  [--force]
```

### Step 4: Validate Output

After Python completes:
1. **Check exit code** — non-zero means error. Read stderr for details.
2. **File exists** — verify the HTML file was created at `.ielts/test-html/{source}_{skill}_test-{n}_section-{s}.html`
3. **File has content** — file size > 0
4. **Question count matches** — grep the generated HTML for `class="question"` and compare with expected count from JSON
5. **No leftover template markers** — grep for `{{` in the output (should find none)

If Python exits non-zero:
- Read the full error message from stderr
- Report to user: what went wrong and how to fix
- Common fixes: check JSON file exists, verify section number is in range, use `--force` to overwrite
- Do NOT attempt to render HTML directly — always go through Python for deterministic output

### Step 5: Report Results

Format the success report:

```
✅ Generated: .ielts/test-html/{filename}
   📋 {N} questions rendered (matches JSON: {N})
   🎯 Skill: {skill} | {section_label} {section_num} | Test {test_num}
   🔒 Answers locked behind PIN (default: 1234567890 — change in .ielts/settings.json → testHtmlPin)
   🔑 Teacher bypass: Ctrl+Shift+U to view answers without answering
   📂 Open: open .ielts/test-html/{filename}
   🌐 Serve: http://localhost:8765/test-html/{filename} (required for listening audio)
```

For batch mode:
```
✅ {generated}/{total} files generated for {skill}/{source}
   📂 Output: .ielts/test-html/
   📋 Index:  .ielts/test-html/_generated.json
```

### Step 6: Offer to Open

Ask the user: "Open the file in your browser?"
- If yes: run `open .ielts/test-html/{filename}` (macOS) or equivalent
- For listening: suggest opening via server for audio: `http://localhost:8765/test-html/{filename}`
- If batch mode: ask which file to open, or offer to open the output directory

## Cross-Check Workflow (User Guide)

After generating, the user can verify JSON accuracy against the PDF source:

1. Open the generated HTML file + original PDF side by side
2. Press `Ctrl+Shift+U` (teacher bypass — no need to answer questions first)
3. Enter PIN (default: `1234567890`)
4. Correct answers are revealed with green/red highlighting
5. Compare each question + answer with the PDF
6. If you find an error → edit the JSON source file → re-run `/create-test-html` with `--force`

## Output Structure

```
.ielts/test-html/
├── cambridge-1_listening_test-1_section-1.html
├── cambridge-1_listening_test-1_section-2.html
├── ...
├── cambridge-1_reading_test-1_section-1.html
├── ...
├── cambridge-1_speaking_test-1_section-1.html
├── ...
├── cambridge-1_writing_test-1_section-1.html
├── ...
└── _generated.json          # Index of all generated files
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `FileNotFoundError: JSON not found` | JSON source hasn't been initialized | Run `/init-textbook-{skill} --source {textbook}` first |
| `ValueError: Section N out of range` | Requested section doesn't exist | Check available sections in the JSON |
| `FileExistsError: File already exists` | HTML file already generated | Use `--force` to overwrite |
| `FileNotFoundError: Template not found` | Template file missing | Check `skills/ielts-teacher/templates/section-templates/` |
| Python crash (other) | JSON format issue or bug | Read stderr, report to user |

## PIN Configuration

- Default PIN: `1234567890`
- Change via: `.ielts/settings.json` → add field `"testHtmlPin": "your-new-pin"`
- PIN is SHA-256 hashed before embedding in HTML (hash is in source, plaintext is not)
- PIN is a **soft gate** — prevents accidental exposure. Determined users can View Source to see answers.
- Teacher bypass: `Ctrl+Shift+U` opens PIN modal without requiring answers first

## Integration with Teaching Workflow

After generating HTML files:

1. **Student test:** Claude opens `http://localhost:8765/test-html/{filename}` → student answers → submits → results saved to `.ielts/{skill}/latest.json` → Claude reads and grades
2. **Cross-check:** User opens HTML + PDF side by side → `Ctrl+Shift+U` → PIN → verify answers
3. **Lesson library:** `_generated.json` tracks all generated files. Claude can later import into `lesson-library.json` with KC tags
