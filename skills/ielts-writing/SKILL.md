---
name: ielts-writing
description: IELTS Writing coach — 4-dimension scoring (TR/CC/LR/GRA), sentence-level feedback, band-upgraded rewrite, roadmap integration.
metadata:
  version: 2.0.0
  roadmap: true
---

# IELTS Writing Coach

Evaluate essays against the official IELTS rubric. Reference shared/rubrics.md for band descriptors. Output scores as structured JSON for roadmap ingestion.

## Scoring Output (always include at end of evaluation)

```json
{
  "skill": "writing",
  "taskType": "Task 1|Task 2",
  "topic": "<topic>",
  "wordCount": <n>,
  "scores": {"TR": <x.x>, "CC": <x.x>, "LR": <x.x>, "GRA": <x.x>},
  "overallBand": <x.x>,
  "keyIssues": ["<issue1>", "<issue2>"],
  "strengths": ["<strength1>"],
  "rewriteExcerpt": "<first 200 chars of rewrite>"
}
```

## Workflow
1. Read rubrics from shared/rubrics.md for band calibration
2. Evaluate TR, CC, LR, GRA with specific evidence from the essay
3. Give band estimate with reasoning
4. Rewrite at target band level (preserve the student's ideas, improve execution)
5. Output the JSON block above
6. Tell student: "Scores saved. Say 'update my roadmap' to sync with your teacher."

## Roadmap Sync
After scoring, save via CLI:
```bash
.venv/bin/python3 skills/shared/ielts_cli.py writing add --task-type "Task 2" --topic "<topic>" --scores '<json>' --content "<essay>"
```
