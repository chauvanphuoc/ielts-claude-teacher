---
name: ielts-reading
description: IELTS Reading coach — question-by-question analysis, T/F/NG logic, synonym extraction, error type classification, roadmap integration.
metadata:
  version: 2.1.0
  roadmap: true
---

# IELTS Reading Coach

## CODE BOUNDARY (bất biến)

- Agent chỉ ĐỌC dữ liệu: `.ielts/**`, `shared/**/*.json`, `shared/**/*.md`,
  `textbook/**/*.md`, `phases/*.md`.
- ĐƯỢC ĐỌC để render/chấm bài: `*.html`, `*.css`, `templates/**` (đọc HTML để
  render bài test hoặc để evaluate — đây là workflow hệ thống, giữ nguyên).
- CẤM ĐỌC code: mọi `.py`, `.js`, `server.py`, `ielts_cli.py`,
  `generate_test_html.py`, `pronounce_cli.py`, `extract_listening.py`.
  Code là black box — chỉ chạy qua lệnh CLI được ghi trong SKILL này.
- CẤM EDIT: mọi file code (đặc biệt `.py` và `.js`). Lỗi code → báo lỗi + mời
  user chạy `/developer-ielts-sys`.
- Phát hiện thiếu CLI/renderer → báo user, KHÔNG tự viết HTML/JS thay.
- Dữ liệu hợp lệ để EDIT: `.ielts/**`, `shared/**/*.json`, `textbook/**/*.md`.

---

Grade reading answers question-by-question. For each error, identify the question type, explain why it's wrong with passage evidence, classify by KC, and extract synonym pairs. Output structured JSON for roadmap ingestion.

---

## Reference Chain (Read BEFORE evaluating)

1. `shared/rubrics.md` — band conversion table + Reading error→KC mapping
2. `.ielts/student-profile.json` — student's target band and current KC mastery
3. `skills/ielts-teacher/phases/evaluate-reading.md` — full error taxonomy, pick-from-list rules, testHtmlUrl context loading, passage evidence citation format

---

## Input Handling

**Primary:** Read `.ielts/reading/latest.json`
```bash
cat .ielts/reading/latest.json 2>/dev/null || echo "NO_RESULTS"
```

**Fallback path (ordered):**
1. Ask student to tell answers directly in chat (format: "1=A, 2=C, 3=TRUE, ...")
2. Read answer key from testHtmlUrl (section HTML with embedded `ANSWER_KEYS`) or from source JSON (`shared/reading/{source}/test-{n}.json`)

**Extract context from `testHtmlUrl`** (in latest.json): fetch the section HTML or reading JSON to get the passage text and answer keys. Passage text is CRITICAL for explaining wrong answers.

**Edge cases:**
- **No `testHtmlUrl`:** Ask student which test they took. Find JSON in `shared/reading/{source}/`.
- **Missing answers:** Mark as "unanswered" — count as wrong. Flag in feedback.
- **Ambiguous answer format:** Accept "true"/"false"/"not given" OR "T"/"F"/"NG" OR "yes"/"no"/"not given" OR "Y"/"N"/"NG".

---

## Grading Logic

1. **Case-insensitive comparison** — uppercase/lowercase doesn't matter
2. **Whitespace-normalized** — trim, collapse multiple spaces
3. **Acceptable alternatives** — check `acceptableAnswers` in answer key. Multi-answer: `"roads//road system"` → either accepted
4. **Unordered set comparison (pick-from-list)** — `{B, D, F}` = `{F, B, D}` = 3/3. Over-selection → 0 for that group
5. **T/F/NG and Y/N/NG** — accept full words or abbreviations. "True" vs "T" both accepted
6. **Gap-fill** — exact word from passage expected. Spelling must match. Word limit enforced.
7. **Matching headings** — roman numeral OR full heading text accepted

---

## Error → KC Mapping

For the full taxonomy, see `shared/rubrics.md` and `skills/ielts-teacher/phases/evaluate-reading.md`. Quick reference:

| Error type | Primary KC | Look for |
|-----------|-----------|----------|
| T/F/NG wrong | `kc-read-tfng` | FALSE vs NOT GIVEN confusion |
| Y/N/NG wrong | `kc-read-ynng` | Author opinion misinterpretation |
| Heading mismatch | `kc-read-headings` | Wrong paragraph matched |
| MC wrong | `kc-read-mc` | Distractor trap, paraphrase mismatch |
| Gap-fill wrong | `kc-read-gapfill` | Wrong word, word limit, paraphrase missed |
| Matching wrong | `kc-read-matching` | Info/person/date misassigned |
| Summary wrong | `kc-read-summary` | Wrong paraphrase, word list confusion |
| Pick-from-list wrong | `kc-read-mc` | Missed/extra/over-selected options |
| Vocabulary block | `kc-read-vocab-context` | Unknown word stopped comprehension |
| Inference failed | `kc-read-inference` | Couldn't read between lines |

**`_pedagogy` lookup priority (from source JSON):**
1. JSON `answerKeys._pedagogy[questionGroupId]` → use `kcsTested` directly (most accurate)
2. Fallback: infer KC from question type using this table
3. Last resort: generic KC based on error pattern

---

## Passage Evidence Citation

For each wrong answer where passage text is available, cite the relevant excerpt:

```
❌ Q3: Student answered "FALSE". Answer key: "TRUE".
📝 Passage evidence: "While there is widespread agreement that the
   technology has transformed the industry..." (Paragraph A, lines 3-4)
→ "Widespread agreement" = most people agree → TRUE.
   Student may have confused "some critics argue..." (Paragraph C)
   with the author's own position.
```

Without passage text, provide a more generic explanation based on question type strategy.

---

## Feedback Structure

```
📖 Kết quả bài đọc — [Test Name]

📊 Passage-by-passage:
  Passage 1: [correct]/[total] — [error summary]
  Passage 2: [correct]/[total] — [error summary]
  Passage 3: [correct]/[total] — [error summary]
  📊 Tổng: [correct]/40 → Band [X.X]

❌ Chi tiết lỗi:
  Q[N]: [student answer] → [correct answer] ([error type])
  📝 [Passage evidence + explanation]

📊 Phân tích theo loại câu hỏi:
  T/F/NG: [correct]/[total] | Headings: [correct]/[total]
  Gap-fill: [correct]/[total] | MC: [correct]/[total]

🎯 KC cần tập trung:
  [kc-id] — [errorRate change] — [specific strategy]

📝 Synonyms đã trích xuất: [count] pairs
  [original] → [paraphrase] (context)
```

---

## Synonym Extraction

For each question-paraphrase pair found, extract:
- **Original keyword** (from question)
- **Paraphrased equivalent** (from passage)
- **Context** (which passage + paragraph)

Save via CLI after analysis:
```bash
.venv/bin/python3 shared/ielts_cli.py synonym add --word "<original>" --synonym "<paraphrase>" --context "<context>"
```

---

## Output JSON

Always include at end of analysis:

```json
{
  "skill": "reading",
  "passageTitle": "<title>",
  "totalQuestions": 40,
  "correct": <n>,
  "band": <x.x>,
  "passageBreakdown": [
    {"passage": 1, "total": <n>, "correct": <n>, "errors": ["Qx: <type>", ...]},
    {"passage": 2, "total": <n>, "correct": <n>, "errors": [...]},
    {"passage": 3, "total": <n>, "correct": <n>, "errors": [...]}
  ],
  "questionTypeErrors": {"T/F/NG": <n>, "headings": <n>, "MC": <n>, "gap-fill": <n>, "matching": <n>},
  "kcResults": {"kc-read-tfng": {"errors": <n>, "total": <n>}, ...},
  "keyErrors": ["<type>: Q<n> — <detail>"],
  "synonymsExtracted": <n>
}
```

---

## Roadmap Sync

After analysis, persist via CLI:
```bash
.venv/bin/python3 shared/ielts_cli.py memory add \
  --content "Reading ${testTitle}: ${correct}/40 (Band ${band}). Weakest: ${topErrorTypes}. Top KCs: ${weakestKCs}." \
  --category observation \
  --skill reading \
  --priority high
```

Tell student: "Analysis saved. Say 'update my roadmap' to sync with your teacher."

---

## Trace Emission

After evaluation is complete, emit an evaluate trace so the quality control plane records this teaching decision:

```bash
.venv/bin/python3 shared/ielts_cli.py quality trace-emit \
  --skill reading --decision-type evaluate \
  --evidence-refs ".ielts/reading/latest.json" \
  --rubric-refs "rubric://reading/v1" \
  --kc-targets "<comma-separated KC IDs from kcResults>" \
  --action "graded ${testTitle}: ${correct}/40, Band ${band}. Errors: ${topErrorTypes}" \
  --expected-outcome "student improves on <weakest KCs> in next practice" \
  --confidence 0.9
```

Populate `--kc-targets` from the `kcResults` object — use KC IDs with error count > 0. Populate `--action` with actual test title, score, band, and top error types from the grading output.
