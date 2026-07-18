---
name: ielts-json-init
description: |
  Initialize JSON test files from textbook Markdown. Claude reads Cambridge IELTS
  textbook Markdown, parses questions/answers/images/tables, and generates structured
  JSON files that the HTML studio and Claude conversation mode can consume.
  Unified commands: /init-textbook-{reading|listening|speaking|writing} --source {dir}
metadata:
  version: 2.0.0
---

# Initialize JSON Textbook

Convert Cambridge IELTS textbook Markdown into structured JSON test files.
Supports **Reading**, **Listening**, **Speaking**, and **Writing**.

## Command Reference

| Skill | Command | Output | Type |
|-------|---------|--------|------|
| Reading | `/init-textbook-reading --source X --test N` | `shared/reading/{X}/test-{N}.json` | per-test |
| Listening | `/init-textbook-listening --source X` | `shared/listening/listening_{X}.json` | per-source (all 4 tests) |
| Speaking | `/init-textbook-speaking --source X` | `shared/speaking/speaking_{X}.json` | per-source (Claude-generated modern tasks + legacy extract) |
| Writing | `/init-textbook-writing --source X` | `shared/writing/writing_{X}.json` | per-source (academic + general training) |

**Multi-source:** `--source` maps to `textbook/{source}/` directory. Add any Cambridge IELTS book by creating a folder under `textbook/` (e.g., `cambridge-2`, `ielts-4-5`) with the textbook Markdown and audio files.

Examples:
```
/init-textbook-reading --source cambridge-2 --test 1
/init-textbook-listening --source cambridge-2
/init-textbook-speaking --source cambridge-2
/init-textbook-writing --source cambridge-2
```

The user may also say things like:
- "tạo JSON cho Test 1 Reading từ cambridge 2"
- "initialize listening for cambridge 2"  
- "generate speaking tasks from cambridge 1"
- "tạo JSON writing từ cambridge 1"
- "initialize writing tasks for cambridge 2"

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

### Step 5b: Extract Pedagogy Metadata (Reading only)

After extracting answer keys, find the corresponding answer key section at the end of the textbook. For each passage, extract the "Skills tested" table and "Suggested approach" to build `_pedagogy` metadata. This bridges the textbook's pedagogical content with the KC Graph (`.ielts/kc-graph-ielts.json`).

**5b.1 — Find "Skills tested" table:**

In the answer keys section, each passage has a table with headers `| Questions | Task | Skills tested |`. Match by passage title/name.

**5b.2 — Map skills → KC IDs:**

For each question group in the table:
- Read the skills listed (e.g., "skimming for information, ability to paraphrase")
- Map each skill to a KC ID using the reference table below
- Set `kcsTested` array with the mapped KC IDs

**KC Mapping Reference:**

| Textbook skill description | KC ID |
|---|---|
| skimming/scanning for information | `kc-read-detail` |
| detailed understanding of text | `kc-read-detail` |
| paraphrase / re-word / understanding paraphrase | `kc-read-vocab-context` |
| identifying attitude and opinion | `kc-read-inference` |
| understanding gist | `kc-read-main-idea` |
| identifying main ideas / noting main ideas | `kc-read-main-idea` |
| identifying supporting points | `kc-read-detail` |
| Yes/No/Not Given logic | `kc-read-ynng` |
| True/False/Not Given logic | `kc-read-tfng` |
| understanding cause and effect | `kc-read-inference` |
| understanding inference | `kc-read-inference` |
| following a chronological account | `kc-read-detail` |
| matching (items/headings/features/causes) | `kc-read-matching` |
| multiple choice | `kc-read-mc` |
| completing gaps/tables/notes/summaries | `kc-read-gapfill` |
| selecting factors | `kc-read-matching` |
| understanding description/characteristics | `kc-read-detail` |

If a skill description doesn't clearly match any KC, look up the KC descriptions in `.ielts/kc-graph-ielts.json` and pick the closest match. When in doubt, prefer `kc-read-detail` (most general reading KC).

**5b.3 — Extract "Suggested approach":**

Located after the Skills tested table, under `#### Suggested approach` or `#### *Suggested approach*` or `#### **Suggested approach**`:
- Read the strategy steps (bullet points)
- Summarize into 1-2 sentences (≤150 characters total)
- Focus on the UNIQUE strategy for this question type — skip generic advice like "read the rubric carefully" or "check your answers"
- Write in English (target: IELTS student)

**strategySummary examples:**
- Good: "Skim for match names (italicized = easier to spot). Match meaning, not exact words. Rubric allows reuse."
- Good: "Scan for paraphrase of missing words; use the word list as clues — eliminate used words first. NB: more words than spaces."
- Bad: "Read the task rubric carefully. Decide what information is best to skim for. Skim through the text." (too generic, >150 chars)

**5b.4 — Write `_pedagogy` into `answerKeys` block:**

```json
"answerKeys": {
  "reading": {
    "passage-1": { "1": "preserve", ... },
    "_pedagogy": {
      "qg-r1-1": {
        "kcsTested": ["kc-read-detail", "kc-read-gapfill", "kc-read-vocab-context"],
        "strategySummary": "Skim for paraphrase of missing words; the word list is your clue — eliminate used words first."
      },
      "qg-r1-2": {
        "kcsTested": ["kc-read-matching", "kc-read-detail"],
        "strategySummary": "Skim for match names (italicized = easier to spot). Match meaning, not exact words."
      }
    }
  }
}
```

- Key = questionGroup ID from `passage.questionGroups[].id` (e.g., `qg-r1-1`, `qg-r1-2`)
- `kcsTested`: array of KC IDs from `.ielts/kc-graph-ielts.json` reading KCs
- `strategySummary`: 1-2 sentences, ≤150 characters
- Every questionGroup in the passage must have an entry

### Step 6: Verification (mandatory)

Before writing the JSON file, run these checks:

1. Count questions in Markdown section (pattern `**N**` not in Example blocks) → compare with number of questions in generated JSON
2. Count `![](` image references → compare with total images in JSON
3. Count answer key entries → compare with question count in JSON (may differ for multi-answer rows)
4. Spot-check 3 random questions: re-read the original Markdown at the corresponding line, compare text verbatim with JSON
5. Report: "Generated [N] questions across [P] passages, [M] images, [K] answer key entries. Spot-checks: 3/3 passed."

If any count mismatches or spot-check fails: report the specific error and regenerate the affected section.

6. **_pedagogy validation (Reading only):**
   - Every questionGroup ID has a corresponding `_pedagogy` entry (count check: N questionGroups → N _pedagogy entries)
   - Every KC ID in `kcsTested` exists in `.ielts/kc-graph-ielts.json` — read the KC graph and verify
   - Every `strategySummary` is ≤150 characters
   - Spot-check 2 passages: compare `strategySummary` with the textbook's Suggested approach — verify it captures the key strategy, not generic advice

7. Report: "Generated [N] questions across [P] passages, [M] images, [K] answer key entries, [_P] pedagogy entries. Spot-checks: 3/3 passed."

### Step 7: Write JSON

Write to `shared/reading/{source}/test-{n}.json` following the schema at `shared/reading/schema.json`. Use 2-space indentation. Create the `shared/reading/{source}/` directory if it doesn't exist.

## Example: Test 1 Reading already exists

`shared/reading/cambridge-1/test-1.json` has been generated and can serve as a reference for the expected output format. It contains 3 passages, 40 questions, and all answer keys with Cyrillic normalization applied.

## Edge Cases

- **No answer key section found:** Report "Answer key not found in textbook. Please verify the textbook file includes answer keys." Do not write JSON without answer keys.
- **Question count mismatch:** If Markdown has 40 questions but answer keys have 38, report the mismatch and list which question numbers are missing from the answer key.
- **Image file not found:** If `![] (filename.jpeg)` references an image that doesn't exist in the textbook directory, still include the src in JSON but add a `"missing": true` flag.
- **Multiple acceptable answers (//):** Store the full `"answer1//answer2"` string in answerKeys. Scoring logic handles splitting.
- **Writing — Image file not found:** If `![] (filename.jpeg)` references an image that doesn't exist, still include the src in JSON but add `"missing": true` flag.
- **Writing — No model answers:** If the textbook has no model answers section, or only some tasks have model answers, set `modelAnswer: null` and populate `_modelAnswerNote` explaining which tasks lack model answers.
- **Writing — Mixed formatting (bold vs non-bold task headers):** Cambridge IELTS 1 uses inconsistent formatting: Test 1 uses `#### **WRITING TASK 1**` (bold), Tests 2-4 use `#### WRITING TASK 1` (non-bold). Use flexible matching: `####\s*\*?\*?WRITING TASK [12]\*?\*?`.
- **Writing — General Training vs Academic detection:** The 5th `#### **WRITING**` belongs to General Training, NOT a 5th practice test. Detect by checking if the section is under `### Practice Test N` (Academic) or `### General Training Module` (GT).
- **Writing — Sub-headings within Task 1:** Some Task 1 sections have descriptive sub-headings (e.g., `#### **Expenditure on fast foods**`) between the prompt and images. Only `WRITING TASK` headers indicate task boundaries.

## Listening Extraction (/init-textbook-listening)

**Usage:** `/init-textbook-listening --source cambridge-1`

Listening is fundamentally different from Reading: all content must be extracted from the textbook because audio files are the test material. Claude cannot invent listening questions.

### Output Location

```
shared/listening/listening_{source}.json
```

This is per-source consolidated (all 4 tests in one file) — unlike Reading which is per-test. Rationale: audio files are source-level resources, transcripts cross-reference sections, and consolidated size (~60-80KB) is manageable.

### Step 1: Read textbook markdown

Read `textbook/{source}/textbook/Cambridge_IELTS_*.md`. Find all `#### **LISTENING**` sections.

### Step 2: For each test, extract 4 sections

Each section contains:
- Section header: `#### SECTION X Questions Y-Z`
- Instructions: `*Complete the form...*` (italicized text)
- Questions with types: multiple-choice, multiple-choice-image (picture options), gap-fill, form-completion, matching-checkboxes (select N of M)
- Image references: `![](_page_XX_Picture_YY.jpeg)`

### Step 3: Extract answer keys

Find `#### **LISTENING KEYS**` section. Parse bullet-point answers under `#### *Section N*` headers. Handle:
- Single answers: `- A`
- Multi-answer: `- E F in any order` → split to individual
- Alternatives: `roads//road system` → `["roads", "road system"]`
- Annotations: `Prescott (*must be correct spelling with capital "P"*)` → strip annotation, keep answer + note

### Step 4: Map audio files

Audio files follow naming convention: `Test {N} - Section {S}.mp3`
Validate each file exists in `textbook/{source}/`.

### Step 5: Extract transcripts

Find transcripts section (after answer keys, under `## Transcripts` or section headers with dialogue text). Store inline in each section's `transcript` field. Preserve Q-marker annotations (Q1, Q2) for answer position highlighting.

### Step 6: Validation (mandatory)

Run the validation script after generating JSON:

```bash
.venv/bin/python3 shared/listening/extract_listening.py \
  --source textbook/{source}/textbook/Cambridge_IELTS_*.md \
  --audio-dir textbook/{source} \
  --output shared/listening/listening_{source}.json
```

The validation checks:
1. **Answer key count:** per section, question count (adjusted for grouped types like matching-checkboxes) must match answer key entries. Report mismatches as warnings.
2. **Audio file existence:** every `audioFile` reference must resolve to an existing MP3 file. Missing audio = **ERROR** — block JSON generation.
3. **Image references:** every image in `multiple-choice-image` options must exist. Missing images = **warning** — flag with `"missing": true` in JSON, continue generation.
4. **Ambiguous answer format:** answers containing `//` should use `acceptableAnswers` array instead. Report as warning.
5. **Cyrillic characters:** detect Cyrillic look-alikes (В, С, А, Е, М) in answer keys. Report as warning — normalize to Latin.
6. **Spot-check:** re-read 3 random answers from original markdown, compare with extracted JSON. Any mismatch = **ERROR**.
7. **JSON schema integrity:** validate top-level fields, section fields, question required fields.

**Error severity:**
- **ERROR:** blocks JSON generation. Examples: audio file missing, JSON parse failure, spot-check mismatch.
- **WARNING:** does not block. Examples: image not found, ambiguous answer format, answer key count mismatch.

**Validation output format:**
```
[validate] ⚠️  3 warning(s):
  ⚠️  Test 1 Section 1: Q1 image not found: _page_17_Picture_13.jpeg
  ⚠️  Q14: Answer contains '//' — should use acceptableAnswers array
  ⚠️  Q23: Cyrillic character 'В' found — should be 'B'
[validate] ✅ Validation passed with 3 warning(s)

[summary] Source: cambridge-1
[summary]   Test 1: 4 sections, 39 questions, 41 answer keys, 4/4 audio files
```

**If validation fails with errors:** report the specific errors, do NOT write JSON. Tell the user: "Validation found N errors. Fix the extraction and re-run."

### Step 7: Write JSON

Write to `shared/listening/listening_{source}.json`. Structure:

```json
{
  "source": "cambridge-1",
  "generatedAt": "<ISO datetime>",
  "generatedBy": "/init-textbook-listening",
  "audioBasePath": "textbook/cambridge-1",
  "tests": [
    {
      "testNumber": 1,
      "sections": [
        {
          "sectionNumber": 1,
          "title": "Section 1 — ...",
          "questionRange": "Questions 1-10",
          "audioFile": "Test 1 - Section 1.mp3",
          "speakerInfo": "...",
          "instructions": "...",
          "questions": [...],
          "transcript": "...",
          "answerKey": [...]
        }
      ]
    }
  ]
}
```

### Reference

See `shared/listening/listening_cambridge-1.json` for a complete example (Test 1 fully extracted).

## Speaking Extraction (/init-textbook-speaking)

**Usage:** `/init-textbook-speaking --source cambridge-2`

Speaking is fundamentally different from Reading/Listening: there are no answer keys (speaking is subjectively scored), and Cambridge IELTS 1 uses the old 5-part format where Part 3 (Elicitation) has the candidate asking questions — not the modern 3-part format. Claude must BOTH extract legacy tasks AND generate modern-format content.

### Output Location

```
shared/speaking/speaking_{source}.json
```

Per-source consolidated (all tests in one file), same pattern as Listening.

### Step 1: Read textbook markdown

Read `textbook/{source}/textbook/Cambridge_IELTS_*.md`. Find all `#### **SPEAKING**` sections. There should be one per practice test (4 total for Cambridge books).

### Step 2: Extract legacy tasks

For each speaking section, extract:
- **Candidate's Cue Card:** title, scenario text, role description, topics to ask about
- **Interviewer's Notes:** description, prompt bullet points

Store in `_legacyTask` field:
```json
{
  "_legacyTask": {
    "partType": "elicitation",
    "title": "University Clubs and Associations",
    "format": "Cambridge IELTS 1 (1996) — Part 3 Elicitation",
    "scenario": "You have just arrived at a new university...",
    "role": "Your examiner is a Student Union representative.",
    "topicsToAsk": ["types of clubs", "meeting times", "benefits", "costs"],
    "interviewerNotes": {
      "description": "...",
      "prompts": ["...", "..."]
    }
  }
}
```

### Step 3: Generate modern 3-part tasks

Based on the theme of each legacy task, Claude generates modern IELTS Speaking format:

**Part 1 (Interview, 4-5 min):** 5 general questions on the topic theme. Questions should be personal and conversational — about the student's own experience.

**Part 2 (Long Turn, 3-4 min):** A cue card with a topic + 4 bullet points. Include preparation time (60s) and speaking time (120s). The topic should relate to the legacy task theme but be framed for the CANDIDATE to speak about (not ask questions about).

**Part 3 (Discussion, 4-5 min):** 6 follow-up discussion questions. More abstract — opinions, comparisons, predictions. Related to the Part 2 topic.

### Step 4: Write JSON

Write to `shared/speaking/speaking_{source}.json`. Structure:

```json
{
  "source": "cambridge-2",
  "generatedAt": "<ISO datetime>",
  "generatedBy": "/init-textbook-speaking",
  "tests": [
    {
      "testNumber": 1,
      "parts": [
        {
          "partNumber": 1,
          "partType": "interview",
          "duration": "4-5 minutes",
          "topic": "...",
          "instructions": "Answer these questions about...",
          "questions": ["...", "..."]
        },
        {
          "partNumber": 2,
          "partType": "long-turn",
          "duration": "3-4 minutes",
          "topic": "...",
          "cueCard": {
            "topic": "Describe...",
            "bullets": ["what...", "how...", "why...", "and explain..."]
          },
          "preparationTime": 60,
          "speakingTime": 120
        },
        {
          "partNumber": 3,
          "partType": "discussion",
          "duration": "4-5 minutes",
          "topic": "...",
          "questions": ["...", "..."]
        }
      ],
      "_legacyTask": { ... }
    }
  ],
  "_validation": {
    "testsPopulated": [1, 2, 3, 4],
    "testsPending": [],
    "modernPartsPerTest": 3,
    "legacyTasksExtracted": 4
  }
}
```

### Step 5: Validation

1. **Legacy tasks extracted:** exactly 4 tasks (one per practice test)
2. **Modern parts:** 3 parts per test (interview, long-turn, discussion)
3. **Content quality:** Part 1 has ≥4 questions, Part 2 cue card has ≥3 bullets, Part 3 has ≥4 questions
4. **Themes match:** modern tasks relate to the legacy task themes
5. **JSON schema:** all required fields present, part types correct

### Reference

See `shared/speaking/speaking_cambridge-1.json` for a complete example (all 4 tests with modern parts + legacy tasks).

## Writing Extraction (/init-textbook-writing)

**Usage:** `/init-textbook-writing --source cambridge-1`

Writing extraction differs from Reading/Listening: there are no correct/incorrect answer keys (writing is subjectively scored using band descriptors TR/CC/LR/GRA). The JSON captures task prompts, images, and model answers for reference. Cambridge IELTS 1 includes both Academic (4 tests) and General Training (standalone) writing modules.

### Output Location

```
shared/writing/writing_{source}.json
```

Per-source consolidated (all 4 tests + General Training in one file), same pattern as Listening/Speaking.

### Step 1: Read textbook markdown

Read `textbook/{source}/textbook/Cambridge_IELTS_*.md`. The entire file is needed because model answers appear in a separate section at the end.

### Step 2: Locate Academic Writing sections

Find all `#### **WRITING**` sections within `### Practice Test N` boundaries. In Cambridge 1, there are 4 academic writing sections (Tests 1-4), one per test. A 5th `#### **WRITING**` (line ~2417) belongs to the General Training module and must be handled separately (see Step 4).

**Task header patterns (all must be handled):**
- `#### **WRITING TASK 1**` — bold, with asterisks (Test 1)
- `#### **WRITING TASK 2**` — bold, with asterisks (Test 1)
- `#### WRITING TASK 1` — non-bold (Tests 2, 3, 4)
- `#### WRITING TASK 2` — non-bold (Tests 2, 3, 4)

**Task boundary detection:** A task section runs from its `WRITING TASK {N}` header until the next `WRITING TASK {N}` header, `#### **SPEAKING**`, `### Practice Test N`, or `### General Training Module`.

### Step 3: Extract task content

For each task, extract:

| Field | Source | Notes |
|-------|--------|-------|
| `taskNumber` | Heading | Parse N from `WRITING TASK {N}` |
| `taskType` | Content heuristics | `"report"` (chart/table/diagram/map description), `"letter"` (GT Task 1), `"essay"` (Task 2) |
| `duration` | `*You should spend about {N} minutes*` | May or may not be italicized |
| `wordLimit` | `*write at least {N} words*` | 150 for Task 1, 250 for Task 2 |
| `promptDescription` | Text describing the topic | Multi-paragraph — the chart/table description or essay topic |
| `promptInstruction` | Text describing the task | "Write a report for a university lecturer..." or "Present a written argument..." |
| `images` | `![](_page_XX_...)` references | Collect all images between task header and next boundary. Check file existence. |
| `rubricDimensions` | Always `["TR", "CC", "LR", "GRA"]` | Writing tasks are scored on all 4 dimensions |

**Task type detection:**
```
If promptInstruction contains "report for a university lecturer" → "report"
If promptInstruction contains "letter" OR task is in GT module Task 1 → "letter"
If promptInstruction contains "argument" OR "essay" OR "topic" → "essay"
Default Task 1 → "report" (academic), Default Task 2 → "essay"
```

**Image handling:** Some Task 1 prompts have sub-headings between the prompt and images (e.g., Test 3 has `#### **Expenditure on fast foods by income groups**` and `#### **Consumption of fast foods 1970-1990**`). Do NOT treat these as task boundaries — they are descriptive labels for chart images. Only `WRITING TASK` headers mark boundaries.

### Step 4: Extract General Training Writing

Find the 5th `#### **WRITING**` marker (line ~2417 in Cambridge 1). This appears under `### General Training Module` — NOT inside a numbered practice test.

**Detection:** Check section context — if the writing section is NOT within `### Practice Test N` boundaries, it's General Training. Confirm by checking if Task 1 mentions "Write a letter" (GT) vs "Write a report" (Academic).

Extract GT Task 1 (letter) and Task 2 (essay). Store in `generalTraining.tasks` array — separate from numbered academic tests. GT tasks do NOT have a `testNumber`.

**GT-specific fields:**
- `salutation`: parsed from `Begin your letter as follows: *Dear Sir,*` (Task 1 letter only)
- `addressNote`: `"You do NOT need to write your own address."` if present

### Step 5: Extract Model Answers

Find `#### **WRITING: MODEL ANSWERS**` at the end of the textbook (line ~4102 in Cambridge 1).

**Sub-sections:**
1. `#### **ACADEMIC WRITING MODULE**` — model answers for academic tasks
   - Each entry labeled `Practice Test N, Writing Task M`
   - Followed by `*Model answer {N} words*` then the answer text
2. `#### **GENERAL TRAINING WRITING MODULE**` — model answers for GT tasks
   - `Writing Task 1` / `Writing Task 2` headers
   - Same `*Model answer {N} words*` pattern

**Matching logic:**
1. For Academic: parse `Practice Test N, Writing Task M` → find matching `testNumber` and `taskNumber` → set `modelAnswer` inline on the matched task
2. For GT: match by `taskNumber` in `generalTraining.tasks`
3. Tasks without model answers → `modelAnswer: null`

**Model answer extraction:**
- Read from `*Model answer {N} words*` until the next section marker (`####`, `###`, or `![](`)
- Preserve paragraph breaks (`\n\n`)
- For letters (GT Task 1): extract salutation and closing as structured fields
- The textbook repeats the prompt before each model answer — do NOT re-extract the prompt

**Model answer fields:**
```json
{
  "wordCount": 165,
  "content": "The chart shows that..."
}
```

For GT Task 1 letters, add `salutation` and `closing` fields.

### Step 6: Validation (mandatory)

Before writing the JSON file, run these checks:

1. **Task count:** Academic: 4 tests × 2 tasks = 8 tasks expected. General Training: 2 tasks expected (may be 0 for textbooks without GT module).
2. **Image references:** Every `![](` image referenced in tasks must exist at `textbook/{source}/textbook/{filename}`. Missing images → flag in `_validation.missingImages` with `"missing": true` on the image object (WARNING, does not block).
3. **Model answer coverage:** Report "X of Y tasks have model answers."
4. **Required fields:** Every task must have `taskNumber`, `taskType`, `promptDescription`, `promptInstruction`, `wordLimit`, `duration`, `rubricDimensions`.
5. **Spot-check:** Re-read 2 random task prompts from original markdown, compare verbatim with extracted JSON. Any mismatch = ERROR (blocks generation).
6. **JSON schema integrity:** Validate top-level fields, test structure, task required fields.
7. **Cyrillic normalization:** Apply same normalization as other skills (В→B, С→C, А→A, Е→E, М→M).

**Validation output format:**
```
[validate] ✅ 4 academic tests, 8 tasks extracted
[validate] ✅ 2 General Training tasks extracted
[validate] ✅ 4 model answers matched (Academic Test 3 Tasks 1+2, GT Tasks 1+2)
[validate] ⚠️  1 warning(s):
  ⚠️  Test 2 Task 1: image _page_56_Picture_7.jpeg not found
[validate] ✅ 2/2 spot-checks passed
[validate] ✅ JSON schema integrity verified

[summary] Source: cambridge-1
[summary]   Academic: 4 tests, 8 tasks, 5 images, 2 model answers
[summary]   General Training: 2 tasks, 0 images, 2 model answers
[summary]   Overall: 10 tasks, 5 images, 4 model answers
```

### Step 7: Write JSON

Write to `shared/writing/writing_{source}.json`. Create `shared/writing/` directory if it doesn't exist. Use 2-space indentation.

```json
{
  "source": "cambridge-1",
  "generatedAt": "<ISO datetime>",
  "generatedBy": "/init-textbook-writing",
  "academic": {
    "tests": [
      {
        "testNumber": 1,
        "tasks": [
          {
            "taskNumber": 1,
            "taskType": "report",
            "duration": "20 minutes",
            "wordLimit": 150,
            "promptDescription": "The charts below show the results of a survey...",
            "promptInstruction": "Write a report for a university lecturer...",
            "images": [{"src": "_page_36_Figure_6.jpeg", "alt": "", "missing": false}],
            "modelAnswer": null,
            "rubricDimensions": ["TR", "CC", "LR", "GRA"]
          },
          {
            "taskNumber": 2,
            "taskType": "essay",
            "duration": "40 minutes",
            "wordLimit": 250,
            "promptDescription": "There are many different types of music...",
            "promptInstruction": "Present a written argument or case...",
            "images": [],
            "modelAnswer": null,
            "rubricDimensions": ["TR", "CC", "LR", "GRA"]
          }
        ]
      }
    ]
  },
  "generalTraining": {
    "tasks": []
  },
  "_validation": {
    "academicTestsExtracted": 4,
    "academicTasksExtracted": 8,
    "generalTrainingTasksExtracted": 2,
    "modelAnswersMatched": 0,
    "totalImages": 5,
    "missingImages": []
  }
}
```

### Reference

See `shared/listening/listening_cambridge-1.json` and `shared/speaking/speaking_cambridge-1.json` for the per-source consolidated pattern that writing follows.
