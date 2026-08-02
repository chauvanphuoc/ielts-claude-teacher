---
name: ielts-speaking
description: IELTS Speaking coach — Azure Speech pronunciation assessment + transcript content evaluation, fluency/lexical/grammar/pronunciation scoring, roadmap integration.
metadata:
  version: 2.1.0
  roadmap: true
---

# IELTS Speaking Coach

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

Evaluate speaking performance using TWO data sources:
1. **Azure Speech API** (via `pronounce_cli.py`) — transcript + objective pronunciation scores
2. **Claude content analysis** — vocabulary range, grammatical accuracy, coherence, fluency patterns from transcript

Combine both to produce a complete IELTS Speaking band score with per-dimension feedback and KC mapping.

---

## Reference Chain (Read BEFORE evaluating)

1. `shared/rubrics.md` — 0.5-increment band descriptors for FC/LR/GR/Pron + Speaking error→KC mapping
2. `.ielts/student-profile.json` — student's target band and current KC mastery
3. `skills/ielts-teacher/phases/evaluate-speaking.md` — full 9-step workflow, Azure mapping, testHtmlUrl context loading

---

## Input Handling

**Primary — 2 data sources:**

1. **Audio (pronunciation):** `.ielts/speaking/latest.webm`
   ```bash
   .venv/bin/python3 skills/ielts-teacher/pronounce_cli.py --audio .ielts/speaking/latest.webm --json
   ```
   Parse output: `transcript`, `accuracy`, `fluency`, `prosody`, `completeness`, `pronScore`, `intonation`, `perWord[]`

2. **Test metadata:** `.ielts/speaking/latest.json`
   ```bash
   cat .ielts/speaking/latest.json 2>/dev/null || echo "NO_RESULTS"
   ```
   Extract: `testHtmlUrl` (for cue card + topic context), `transcript` (browser SpeechRecognition fallback), `duration`

**Extract context from `testHtmlUrl`**: fetch the section HTML to get the PART_TYPE, TOPIC, cue card, questions. Knowing what the student was ASKED to talk about is essential for evaluating Task Achievement.

**Fallback paths (ordered):**
1. Azure Speech succeeds → full evaluation (pronunciation + content)
2. Azure Speech fails, but transcript in latest.json → content-only evaluation. Note: "Pronunciation not assessed — Azure Speech unavailable."
3. Neither available → ask student: "Bạn vừa nói về chủ đề gì? Bạn có thể kể lại những gì bạn đã nói không?"

**Edge cases:**
- **No audio file:** Content-only evaluation from transcript. Flag pronunciation as "not assessed."
- **Transcript < 30 seconds:** Too short for reliable band scoring. Flag as "insufficient sample."
- **Only Part 1, 2, or 3 completed:** Score what's available. Note which parts are missing.
- **No target band set:** Still evaluate, but skip KC errorRate update.

---

## Azure Score → IELTS Pronunciation Band

| Azure PronScore | IELTS Pron Band | Interpretation |
|-----------------|-----------------|----------------|
| ≥ 0.90 | 8.0 – 9.0 | Near-native pronunciation |
| 0.80 – 0.89 | 7.0 – 7.5 | Clear, minor L1 influence |
| 0.65 – 0.79 | 6.0 – 6.5 | Generally intelligible, some errors |
| 0.50 – 0.64 | 5.0 – 5.5 | Errors cause occasional strain |
| 0.35 – 0.49 | 4.0 – 4.5 | Frequent mispronunciation |
| < 0.35 | < 4.0 | Heavy accent, hard to understand |

**Adjustment guide:** Azure scores are mechanical. Adjust ±0.5 based on communicative effectiveness — if the student is easy to understand despite accent features, bump up. If Azure gives 0.85 but you notice word-level errors that impede clarity, bump down.

**Per-word analysis:** Use `perWord[]` array for targeted feedback. Flag words with `accuracy < 0.70` or `errorType != "None"`.

---

## Content Evaluation Guide

For detailed band descriptors, see `shared/rubrics.md`. Below are specific patterns to look for in each dimension.

### Fluency & Coherence — What to check in the transcript

| Signal | Indicates |
|--------|----------|
| Filler words: "um", "uh", "like", "you know", "I mean", "sort of" | Hesitation, low fluency |
| Repeated words/phrases | Searching for vocabulary |
| Long pauses (noted in transcript as "...") | Planning in real-time, low automaticity |
| Self-correction: "I went... I go... I went to" | Monitoring, can be positive (Band 7+) or negative (Band 5) |
| Clear introduction → development → conclusion | Coherence — Band 7+ |
| Jumping between unrelated ideas | Incoherence — Band 5 |
| Linking words: "however", "on the other hand", "therefore", "in addition" | Coherence — count and variety |

**Filler word thresholds:** Band 7+: <2 fillers/minute. Band 6: 2-4/min. Band 5: >4/min.

### Lexical Resource — What to check in the transcript

| Signal | Indicates |
|--------|----------|
| Precise vocabulary: "exacerbate" not "make worse" | Band 7+ |
| Collocations: "heavy rain" not "strong rain" | Band 6+ |
| Idiomatic language: "a double-edged sword" | Band 8+ |
| Paraphrasing: restating ideas in different words | Band 7+ |
| Repetition of basic words: "good", "bad", "thing" | Band 5 |
| Vietnamese-L1 transfer errors: "eat medicine" instead of "take medicine" | Band 5-6 |

**Vocabulary highlights:** List 3 good word choices. List 3 upgrade opportunities with alternatives.

### Grammatical Range & Accuracy — What to check in the transcript

| Signal | Indicates |
|--------|----------|
| Complex structures: relative clauses, conditionals, passives | Band 6+ |
| Variety of structures: not just "I think... I think..." | Band 7+ |
| Article errors: "I went to university" vs "I went to the university" | Common Vietnamese-L1 error |
| Tense mixing: present → past → present in same narrative | Band 5-6 |
| Subject-verb agreement: "people is" instead of "people are" | Band 5 |
| Word order in questions: "where you went?" instead of "where did you go?" | Band 5 |

**Grammar error categorization:** Count errors by type. Flag the TOP 2 most frequent patterns.

### Pronunciation (from Azure) — What to report

- Overall PronScore → IELTS band
- Per-word problems: list 3-5 words with lowest accuracy
- Intonation: flat (Band 5) vs varied (Band 7+)
- Word stress: correct (Band 7+) vs inconsistent (Band 5-6)

---

## Feedback Structure

```
🎙️ Kết quả bài nói — Part [1/2/3]: [topic]
  Thời lượng: [n]s | Độ dài transcript: [n] từ

📊 Điểm từng tiêu chí:
  Fluency & Coherence:          [Band] — [1-sentence evidence]
  Lexical Resource:             [Band] — [1-sentence evidence]
  Grammatical Range & Accuracy: [Band] — [1-sentence evidence]
  Pronunciation:                [Band] — [Azure PronScore: X.XX]
  📊 Tổng: Band [X.X]

🗣️ Filler words: [list + count] ([n]/phút)
   💡 Tập pause thay vì "um" — im lặng 1 giây tốt hơn filler.

✅ Điểm mạnh:
  - Từ vựng: [specific good usage]
  - Ngữ pháp: [specific good structure]

⚠️ Cần cải thiện:
  1. [Dimension]: [specific issue + concrete fix]
  2. [Dimension]: [specific issue + concrete fix]

🔊 Phát âm (Azure):
  - Từ cần sửa: [word] → accuracy [X.XX], lỗi: [errorType]
  - Intonation: [flat / varied / good range]

🎯 KC cần tập trung: [kc-speak-xx] ([errorRate change])

💡 Bài tập:
  - [One specific speaking drill based on weakest dimension]
```

---

## Output JSON

Always include at end of evaluation:

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
  "kcMapping": {
    "kc-speak-fluency": {"bandGap": <x.x>},
    "kc-speak-coherence": {"bandGap": <x.x>},
    "kc-speak-lexical": {"bandGap": <x.x>},
    "kc-speak-grammar": {"bandGap": <x.x>},
    "kc-speak-pronunciation": {"bandGap": <x.x>}
  },
  "fillerWords": ["<word>", ...],
  "fillerCount": <n>,
  "fillerRatePerMinute": <x.x>,
  "perWordIssues": [{"word": "<word>", "accuracy": <0-1>, "errorType": "<type>"}],
  "vocabularyHighlights": ["<good usage>", ...],
  "vocabularyUpgrades": [{"original": "<word>", "upgrade": "<better word>"}],
  "grammarErrors": [{"pattern": "<pattern>", "count": <n>, "example": "<from transcript>"}],
  "recommendation": "<one specific thing to improve>"
}
```

---

## Roadmap Sync

After evaluation, persist via CLI:
```bash
.venv/bin/python3 shared/ielts_cli.py memory add \
  --content "Speaking Part ${part}: ${topic}. Band ${overallBand} (FC=${fc}, LR=${lr}, GR=${gra}, P=${pron}). Fillers: ${fillerCount} (${fillerRate}/min). Top KCs: ${weakestKCs}." \
  --category observation \
  --skill speaking \
  --priority high
```

---

## Trace Emission

After evaluation is complete, emit an evaluate trace so the quality control plane records this teaching decision:

```bash
.venv/bin/python3 shared/ielts_cli.py quality trace-emit \
  --skill speaking --decision-type evaluate \
  --evidence-refs ".ielts/speaking/latest.json" \
  --rubric-refs "rubric://speaking/v1" \
  --kc-targets "<comma-separated KC IDs from kcMapping>" \
  --action "evaluated Part ${part}: ${topic}. Band ${overallBand} (FC=${fc}, LR=${lr}, GR=${gra}, P=${pron})" \
  --expected-outcome "student improves on <weakest KC> in next practice" \
  --confidence 0.85
```

Populate `--kc-targets` from the `kcMapping` object — use KC IDs with bandGap > 0.5. Populate `--action` with actual part, topic, band, and criterion scores from the evaluation output.

Tell student: "Evaluation saved. Say 'update my roadmap' to sync with your teacher."
