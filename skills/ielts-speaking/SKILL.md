---
name: ielts-speaking
description: IELTS Speaking coach — Azure Speech pronunciation assessment + transcript content evaluation, fluency/lexical/grammar/pronunciation scoring, roadmap integration.
metadata:
  version: 2.1.0
  roadmap: true
---

# IELTS Speaking Coach

Evaluate speaking performance using TWO data sources:
1. **Azure Speech API** (via pronounce_cli.py) — transcript + objective pronunciation scores
2. **Your analysis** — content quality (vocabulary, grammar, structure)

Combine both to give a complete IELTS Speaking band.

## Scoring Output (always include at end of evaluation)

```json
{
  "skill": "speaking",
  "part": "Part 1|Part 2|Part 3",
  "topic": "<topic>",
  "durationSeconds": <n>,
  "transcriptLength": <words>,
  "azureScores": {
    "accuracy": <0-1>,
    "fluency": <0-1>,
    "prosody": <0-1>,
    "completeness": <0-1>,
    "pronScore": <0-1>,
    "intonation": <0-1>
  },
  "scores": {
    "fluencyAndCoherence": <x.x>,
    "lexicalResource": <x.x>,
    "grammaticalRangeAndAccuracy": <x.x>,
    "pronunciation": <x.x>
  },
  "overallBand": <x.x>,
  "fillerWords": ["<word>", "<word>"],
  "fillerCount": <n>,
  "perWordIssues": [{"word": "<word>", "accuracy": <0-1>, "errorType": "<type>"}],
  "vocabularyHighlights": ["<good usage>"],
  "grammarErrors": ["<error pattern>"],
  "recommendation": "<one specific thing to improve>"
}
```

## Workflow

1. Read audio from `~/.ielts/speaking/latest.webm` (or latest.json for transcript-only fallback)
2. Call Azure Speech pronunciation assessment:
```bash
.venv/bin/python3 ~/.claude/skills/ielts-teacher/pronounce_cli.py --audio ~/.ielts/speaking/latest.webm --json
```
3. Parse the JSON output — get transcript, pronunciation scores, per-word feedback
4. Read rubrics from shared/rubrics.md
5. Map Azure scores to IELTS bands:
   - pronunciation accuracy → Pronunciation score
   - fluency + prosody → Fluency & Coherence (partial)
6. Evaluate content from transcript:
   - Lexical Resource: vocabulary range, collocations, paraphrasing
   - Grammatical Range & Accuracy: sentence variety, error patterns
   - Coherence: structure, linking, logical flow
7. Combine pronunciation (Azure) + content (you) → overall speaking band
8. Output the JSON block above
9. Tell student: "Evaluation saved. Say 'update my roadmap' to sync with your teacher."

## Azure Score → IELTS Band Mapping

| Azure PronScore | IELTS Pronunciation Band |
|-----------------|--------------------------|
| 0.90+ | 8.0 — 9.0 |
| 0.80 — 0.89 | 7.0 — 7.5 |
| 0.65 — 0.79 | 6.0 — 6.5 |
| 0.50 — 0.64 | 5.0 — 5.5 |
| 0.35 — 0.49 | 4.0 — 4.5 |
| < 0.35 | < 4.0 |

Note: This mapping is approximate. Azure scores are mechanical (accuracy, fluency, prosody). IELTS also considers communicative effectiveness — use your judgment to adjust ±0.5.

## Fallback

If `pronounce_cli.py` fails (no API key, network error, SDK not installed):
- Check if `latest.json` has a transcript from browser SpeechRecognition
- Evaluate content only (vocabulary, grammar, structure)
- Note in scores: "pronunciation not assessed — Azure Speech unavailable"
- Tell the student: "I can evaluate your content but not pronunciation. Set up AZURE_SPEECH_KEY in .env for full assessment."
