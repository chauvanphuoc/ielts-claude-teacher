---
name: ielts-listening
description: IELTS Listening coach — section-by-section grading, error type classification, dictation exercises, roadmap integration.
metadata:
  version: 2.0.0
  roadmap: true
---

# IELTS Listening Coach

Grade listening test answers, categorize errors, prescribe targeted exercises.

## Scoring Output (always include at end of grading)

```json
{
  "skill": "listening",
  "testName": "<Cambridge X Test Y>",
  "totalQuestions": 40,
  "correct": <n>,
  "band": <x.x>,
  "sectionScores": {"Section1": {"total": 10, "correct": <n>}, "Section2": {"total": 10, "correct": <n>}, "Section3": {"total": 10, "correct": <n>}, "Section4": {"total": 10, "correct": <n>}},
  "errorTypes": {"spelling": <n>, "number-date": <n>, "missed": <n>, "distractor": <n>, "format": <n>, "plural": <n>},
  "keyErrors": ["<type>: Q<n> — <detail>"],
  "weakestSection": "<S1|S2|S3|S4>",
  "prescribedExercise": "<specific dictation or practice task>"
}
```

## Workflow
1. Read answers from ~/.ielts/listening/latest.json
2. Read answer key from docs/Cambridge-IELTS-1/textbook/Cambridge_IELTS_1.md (or relevant test)
3. Grade each question, categorize each error using the taxonomy from shared/rubrics.md
4. Give section-by-section breakdown
5. Recommend a specific dictation/practice exercise based on weakest section
6. Output the JSON block above
7. Tell student: "Grades saved. Say 'update my roadmap' to sync with your teacher."

## Roadmap Sync
After grading, save via CLI:
```bash
.venv/bin/python3 skills/shared/ielts_cli.py listening add --test-name "<name>" --total-questions 40 --correct <n> --score <band> --section-scores '<json>' --question-type-errors '<json>' --key-errors '<json>'
```
