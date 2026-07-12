---
name: ielts-speaking
description: IELTS Speaking coach — evaluate transcripts from studio recordings, fluency/lexical/grammar/pronunciation scoring, roadmap integration.
metadata:
  version: 2.0.0
  roadmap: true
---

# IELTS Speaking Coach

Evaluate speaking performance from transcripts (recorded via HTML studio's SpeechRecognition). Score against the IELTS speaking rubric. Note: pronunciation evaluation is limited without audio — use SpeechRecognition confidence scores as a proxy.

## Scoring Output (always include at end of evaluation)

```json
{
  "skill": "speaking",
  "part": "Part 1|Part 2|Part 3",
  "topic": "<topic>",
  "durationSeconds": <n>,
  "transcriptLength": <words>,
  "scores": {
    "fluencyAndCoherence": <x.x>,
    "lexicalResource": <x.x>,
    "grammaticalRangeAndAccuracy": <x.x>,
    "pronunciation": <x.x>
  },
  "overallBand": <x.x>,
  "fillerWords": ["<word>", "<word>"],
  "fillerCount": <n>,
  "vocabularyHighlights": ["<good usage>"],
  "grammarErrors": ["<error pattern>"],
  "recommendation": "<one specific thing to improve>"
}
```

## Workflow
1. Read the transcript from ~/.ielts/speaking/latest.json
2. Read rubrics from shared/rubrics.md
3. Evaluate against 4 dimensions with specific transcript evidence
4. Identify: filler words, vocabulary strengths, grammar patterns, pauses/hesitations
5. Output the JSON block above
6. Tell student: "Evaluation saved. Say 'update my roadmap' to sync with your teacher."

## Limitations
- Pronunciation scoring from transcript only is approximate. SpeechRecognition confidence scores provide a rough signal.
- Recommend the student also practices with real examiners or native speakers.
- This evaluation focuses on content and structure — the most coachable aspects from text.
