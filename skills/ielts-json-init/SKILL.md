---
name: ielts-json-init
description: |
  Initialize JSON test files from textbook Markdown. Claude reads Cambridge IELTS
  textbook Markdown, parses questions/answers/images/tables, and generates structured
  JSON files that the HTML studio and Claude conversation mode can consume.
  Usage: /initialize-json-textbook --source cambridge-1 --test 1 --skill reading
metadata:
  version: 1.0.0
---

# Initialize JSON Textbook

You convert Cambridge IELTS textbook Markdown into structured JSON test files.

## Purpose

The textbook Markdown (e.g., `Cambridge_IELTS_1.md`, 4255 lines) contains all test content — passages, questions, images, tables, and answer keys — but in an unstructured format that neither the HTML studio nor Claude can programmatically consume.

Your job: read the Markdown, understand the structure, and generate a JSON file per test per skill that accurately represents every question, answer, image, and table.

## Output Location

```
textbook/{source}/json/test-{n}-{skill}.json
```

Examples:
- `textbook/cambridge-1/json/test-1-reading.json`
- `textbook/cambridge-1/json/test-1-writing.json`
- `textbook/cambridge-1/json/test-1-listening.json`

Schema reference: `textbook/cambridge-1/schema.json`

## Usage

```
/initialize-json-textbook --source cambridge-1 --test 1 --skill reading
```

The user may also say things like:
- "tạo JSON cho Test 1 Reading"
- "initialize test 1 reading from cambridge 1"
- "generate json for practice test 1"

## Workflow

### Step 1: Read the textbook Markdown

Read the file at `textbook/{source}/textbook/Cambridge_IELTS_{N}.md`. For large files (>3000 lines), read in chunks focused on the target test and skill.

### Step 2: Locate the target test

Find the test using the marker `### Practice Test {N}`. Only parse content for the requested test number.

### Step 3: Locate the target skill

Find the skill section using one of these markers (order of preference):
1. `#### READING PASSAGE {N}` — for Reading (most Cambridge tests use this, NOT `#### **READING**`)
2. `#### **LISTENING**` — for Listening
3. `#### **WRITING**` — for Writing
4. `#### WRITING TASK 1` — alternative Writing marker

**Important:** `#### READING PASSAGE N` is the primary navigation marker for Reading sections. The heading `#### **READING**` may not exist in all tests.

### Step 4: Parse questions

Use the Markdown Parsing Guidelines table below to identify structure:

| Marker Pattern | Meaning | Action |
|---|---|---|
| `### Practice Test N` | Test boundary | Start new test |
| `#### READING PASSAGE N` | Reading passage start | Extract passage text until next marker |
| `#### **LISTENING**` | Listening section start | Switch to listening context |
| `#### SECTION X Questions Y-Z` | Question group for Listening | Create new questionGroup |
| `#### Questions X-Y` | Question group | Create new questionGroup |
| `**N**` at line start | Numbered question | Create new question with this number |
| `- **N** question text` | Numbered question (list format) | Create new question |
| `![] (filename.jpeg)` | Image attachment | Add to nearest question's images array |
| `- **A** / - **B** text` | Multiple choice option | Add to current question's options |
| `| cell | cell |` (2+ lines) | Table | Extract as table object |
| `*text in italics*` | Instructions | Set as questionGroup.instructions |
| `#### *Example*` | Example question | **Skip entirely** — do not include in JSON |
| `- **A** the Ethereal Match` etc. | Match type list (matching questions) | Store as options on matching questions |

### Step 5: Extract answer keys

Answer keys are in a separate section at the end of the textbook, under `### Answer keys` or `## Answer key`.

**CRITICAL: Cyrillic normalization.** The answer key tables may contain Cyrillic characters that look identical to Latin letters. Before storing any answer, normalize:
- `В` (U+0412) → `B`
- `С` (U+0421) → `C`
- `А` (U+0410) → `A`
- `Е` (U+0415) → `E`
- `М` (U+041C) → `M`

**Answer key formats (all must be handled):**

1. **Simple 2-column table:** `| Question | Answer |` — extract each row
2. **3-column table:** `| Question | Answer | Location |` — extract only question and answer columns
3. **Multi-answer row:** `| 11-13 | E F H (in any order) |` — split range into individual question numbers
4. **Inline annotations:** `roads//road system`, `Prescott (*must be correct spelling*)` — strip annotations, keep only answers

**Multi-answer handling with `//`:**
- Split by `//` to get alternatives
- Normalize whitespace and punctuation for each alternative
- Store the full alternative string as-is in answerKeys
- When scoring, Claude will check if the user's answer matches ANY alternative (case-insensitive, whitespace-normalized)

**Skip tutorial text:** Between answer tables there are "Suggested approach" tutorial blocks. Only parse lines that start with `|` and contain a question number.

### Step 6: Verification (mandatory)

Before writing the JSON file, run these checks:

1. Count questions in Markdown section (pattern `**N**` not in Example blocks) → compare with number of questions in generated JSON
2. Count `![](` image references → compare with total images in JSON
3. Count answer key entries → compare with question count in JSON (may differ for multi-answer rows)
4. Spot-check 3 random questions: re-read the original Markdown at the corresponding line, compare text verbatim with JSON
5. Report: "Generated [N] questions across [P] passages, [M] images, [K] answer key entries. Spot-checks: 3/3 passed."

If any count mismatches or spot-check fails: report the specific error and regenerate the affected section.

### Step 7: Write JSON

Write to `textbook/{source}/json/test-{n}-{skill}.json` following the schema at `textbook/cambridge-1/schema.json`. Use 2-space indentation.

## Example: Test 1 Reading already exists

`textbook/cambridge-1/json/test-1-reading.json` has been generated and can serve as a reference for the expected output format. It contains 3 passages, 40 questions, and all answer keys with Cyrillic normalization applied.

## Edge Cases

- **No answer key section found:** Report "Answer key not found in textbook. Please verify the textbook file includes answer keys." Do not write JSON without answer keys.
- **Question count mismatch:** If Markdown has 40 questions but answer keys have 38, report the mismatch and list which question numbers are missing from the answer key.
- **Image file not found:** If `![] (filename.jpeg)` references an image that doesn't exist in the textbook directory, still include the src in JSON but add a `"missing": true` flag.
- **Multiple acceptable answers (//):** Store the full `"answer1//answer2"` string in answerKeys. Scoring logic handles splitting.
