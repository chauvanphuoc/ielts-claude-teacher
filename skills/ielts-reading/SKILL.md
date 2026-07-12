---
name: ielts-reading
description: IELTS Reading coach — question-by-question analysis, T/F/NG logic, synonym extraction, error type classification, roadmap integration.
metadata:
  version: 2.0.0
  roadmap: true
---

# IELTS Reading Coach

Analyze reading answers question by question. Extract synonym pairs. Classify errors by type.

## Scoring Output (always include at end of analysis)

```json
{
  "skill": "reading",
  "passageTitle": "<title>",
  "totalQuestions": 40,
  "correct": <n>,
  "band": <x.x>,
  "questionTypeErrors": {"T/F/NG": <n>, "headings": <n>, "MC": <n>, "sentence-completion": <n>, "matching": <n>},
  "keyErrors": ["<type>: <description>"],
  "synonymsExtracted": <n>
}
```

## Workflow
1. Grade each question against the answer key
2. For each wrong answer: identify question type, explain why it's wrong, quote the passage evidence
3. Extract synonym pairs from the passage → save to CLI
4. Classify errors by type using the taxonomy from shared/rubrics.md
5. Output the JSON block above
6. Tell student: "Analysis saved. Say 'update my roadmap' to sync with your teacher."

## Roadmap Sync
After analysis, save via CLI and update synonym library:
```bash
python3 ~/.claude/skills/shared/ielts_cli.py reading add --passage-title "<title>" --total-questions 40 --correct <n> --score <band> --question-types '<json>' --key-errors '<json>'
python3 ~/.claude/skills/shared/ielts_cli.py synonym add --word "<original>" --synonym "<paraphrase>" --context "<context>"
```
