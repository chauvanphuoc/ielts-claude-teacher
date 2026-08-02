---
name: ielts-listening
description: IELTS Listening coach — section-by-section grading, error type classification, dictation exercises, roadmap integration.
metadata:
  version: 2.1.0
  roadmap: true
---

# IELTS Listening Coach

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

Grade listening test answers section-by-section. Categorize each error by type, map to the corresponding KC, use transcript evidence for teaching (when available), and prescribe targeted dictation exercises.

---

## Reference Chain (Read BEFORE evaluating)

1. `shared/rubrics.md` — band conversion table + Listening error→KC mapping
2. `.ielts/student-profile.json` — student's target band and current KC mastery
3. `skills/ielts-teacher/phases/evaluate-listening.md` — full error taxonomy, pick-from-list rules, transcript teaching format, testHtmlUrl context loading

---

## Input Handling

**Primary:** Read `.ielts/listening/latest.json`
```bash
cat .ielts/listening/latest.json 2>/dev/null || echo "NO_RESULTS"
```

**Fallback path (ordered):**
1. Ask student to tell their answers directly in chat (format: "Section 1: 1=..., 2=..., ...")
2. Read answer key from testHtmlUrl (section HTML with embedded `ANSWER_KEYS`) or from source JSON (`shared/listening/listening_{source}.json`)

**Extract context from `testHtmlUrl`** (in latest.json): fetch the section HTML to get the transcript. Transcript is INCREDIBLY valuable — it lets you quote exactly what the speaker said for each wrong answer.

**Edge cases:**
- **No `testHtmlUrl`:** Ask student which test. Find JSON in `shared/listening/`.
- **Missing answers:** Mark as "unanswered" — count as wrong. Flag "bỏ trống" in feedback.
- **Multiple `testHtmlUrls`:** The array contains individual section HTMLs — fetch each for per-section transcripts.

---

## Grading Logic

1. **Case-insensitive** — "black street" = "Black Street"
2. **Whitespace-normalized** — trim, collapse spaces
3. **Acceptable alternatives** — check `acceptableAnswers`. "15 pounds" = "£15" = "15"
4. **Numbers** — "15" = "fifteen". But "50" ≠ "15" (number/date error). Accept both numeral and word forms.
5. **Spelling of proper nouns** — strict. "Prescott" ≠ "Prescot" (spelling error). Common words: minor misspellings that don't change meaning may be accepted.
6. **Unordered set (pick-from-list)** — `{B, D, F}` = `{F, B, D}`. Over-selection → 0.
7. **Plural -s** — "student" ≠ "students" (spelling/plural error)

---

## Error → KC Mapping

For the full taxonomy with examples, see `shared/rubrics.md` and `phases/evaluate-listening.md`. Quick reference:

| Error pattern | KC Tag | How to identify |
|--------------|--------|----------------|
| Correct word, wrong spelling | `kc-listen-spelling` | Compare to answer key letter-by-letter |
| Number/date/price wrong | `kc-listen-numbers` | 15 vs 50, date format, missing £/$ |
| Distractor trap — first answer | `kc-listen-distractor` | Speaker corrects themselves mid-sentence |
| MC — wrong option chosen | `kc-listen-mc` | Paraphrase mismatch in MC options |
| Gap-fill — wrong word or format | `kc-listen-gapfill` | Exceeded word limit, wrong form |
| Map/diagram — wrong location | `kc-listen-map` | Misidentified spatial reference |
| Speaker attitude — misunderstood | `kc-listen-inference` | Took sarcasm/hesitation as agreement |
| Pick-from-list — missed correct | `kc-listen-mc` | Bỏ sót đáp án đúng |
| Pick-from-list — selected wrong | `kc-listen-mc` | Chọn đáp án sai |
| Pick-from-list — over-selected | `kc-listen-mc` | Chọn quá số lượng cho phép |
| Plural -s missing/extra | `kc-listen-spelling` | "student" vs "students" |

---

## Transcript-Based Teaching

When transcript is available (from testHtmlUrl), the feedback becomes MUCH more valuable. For each wrong answer:

1. **Find the Q-marker** in the transcript: `[Q5]` marks where the answer appears
2. **Quote the exact exchange** — speaker's words before AND after the answer
3. **Explain the trap** — what the student heard vs what was actually said
4. **Teach the pattern** — what to listen for next time

**Example:**
```
❌ Q16: Student wrote "9am". Answer: "10am".
📝 Transcript: "The tour starts at 9am... actually no, we changed
   it to 10am to accommodate the group."
→ Classic distractor! Speaker tự sửa lời. Đợi speaker nói HẾT câu
  rồi mới viết đáp án. Từ khóa: "actually no", "changed it to".
```

Without transcript, explain based on error type pattern.

---

## Feedback Structure

**With transcript:**
```
🎧 Kết quả bài nghe — [Test Name]

📊 Section-by-section (WITH transcript evidence):
  Section 1: [correct]/[total] — [error summary]
    ❌ Q1: [student] → [correct] ([error type])
    📝 [Transcript excerpt + explanation]
    ...
  Section 2: ...
  Section 3: ...
  Section 4: ...
  📊 Tổng: [correct]/40 → Band [X.X]

📊 Phân tích lỗi:
  Spelling: [n] lỗi | Numbers: [n] | Distractor: [n]
  MC: [n] | Gap-fill: [n] | Map: [n] | Inference: [n]

🎯 KC cần tập trung:
  [kc-id] — [errorRate change] — [specific strategy]

📝 Bài tập đề xuất:
  - [Dictation/spelling exercise based on weakest section]
  - [Strategy drill for most frequent error type]
```

**Without transcript (fallback):**
```
🎧 Kết quả bài nghe — [Test Name]
  Section 1: [n]/[n] | Section 2: [n]/[n]
  Section 3: [n]/[n] | Section 4: [n]/[n]
  📊 Tổng: [correct]/40 → Band [X.X]
  ❌ Spelling: Q6 "Prescot", Q20 "Foutain", ...
  🎯 [KC recommendations + exercise prescription]
```

---

## Dictation Exercise Prescription

Based on the weakest section and most frequent error type, prescribe ONE specific exercise:

| Weakness | Exercise |
|----------|----------|
| Spelling errors in Section 1 (forms) | Dictation: 10 common IELTS form-filling words (accommodation, government, restaurant, ...) |
| Numbers in Section 1 | Number dictation: 10 phone numbers, prices, dates from Cambridge audio |
| Distractor in Section 2/3 | Listen to Section 2 again — mark every sentence where speaker corrects themselves |
| MC paraphrases in Section 3 | Synonym mapping: for each MC question, list 3 ways the correct answer is paraphrased |
| Gap-fill in Section 4 | Shadowing: play Section 4, pause after each gap-fill sentence, write exactly what you heard |
| Map labeling | Spatial language drill: listen for "opposite", "next to", "behind", "in front of" |

---

## Output JSON

Always include at end of grading:

```json
{
  "skill": "listening",
  "testName": "<Cambridge X Test Y>",
  "totalQuestions": 40,
  "correct": <n>,
  "band": <x.x>,
  "sectionScores": {
    "Section1": {"total": 10, "correct": <n>, "errorTypes": [...]},
    "Section2": {"total": 10, "correct": <n>, "errorTypes": [...]},
    "Section3": {"total": 10, "correct": <n>, "errorTypes": [...]},
    "Section4": {"total": 10, "correct": <n>, "errorTypes": [...]}
  },
  "errorTypes": {"spelling": <n>, "number-date": <n>, "distractor": <n>, "MC": <n>, "gapfill": <n>, "map": <n>, "inference": <n>},
  "kcResults": {"kc-listen-spelling": {"errors": <n>, "total": <n>}, ...},
  "keyErrors": ["<type>: Q<n> — <detail>"],
  "weakestSection": "<S1|S2|S3|S4>",
  "prescribedExercise": "<specific dictation or practice task>"
}
```

---

## Roadmap Sync

After grading, persist via CLI:
```bash
.venv/bin/python3 shared/ielts_cli.py memory add \
  --content "Listening ${testName}: ${correct}/40 (Band ${band}). Weakest section: ${weakestSection}. Top errors: ${topErrorTypes}. Top KCs: ${weakestKCs}. Exercise: ${prescribedExercise}." \
  --category observation \
  --skill listening \
  --priority high
```

---

## Trace Emission

After grading is complete, emit an evaluate trace so the quality control plane records this teaching decision:

```bash
.venv/bin/python3 shared/ielts_cli.py quality trace-emit \
  --skill listening --decision-type evaluate \
  --evidence-refs ".ielts/listening/latest.json" \
  --rubric-refs "rubric://listening/v1" \
  --kc-targets "<comma-separated KC IDs from kcResults>" \
  --action "graded ${testName}: ${correct}/40, Band ${band}. Weakest section: ${weakestSection}" \
  --expected-outcome "student improves on <weakest KCs> in next practice" \
  --confidence 0.9
```

Populate `--kc-targets` from the `kcResults` object — use KC IDs with error count > 0. Populate `--action` with actual test name, score, band, and weakest section from the grading output.

Tell student: "Grades saved. Say 'update my roadmap' to sync with your teacher."
