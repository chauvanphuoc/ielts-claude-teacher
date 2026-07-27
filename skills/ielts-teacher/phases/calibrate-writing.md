# Writing Calibration Exercise

Runs every 5 writing sessions to detect scoring drift. Non-blocking — does not delay student evaluation.

---

## Trigger Check

Before evaluating a student essay, check:

```bash
cat .ielts/student-profile.json | python3 -c "import sys,json; p=json.load(sys.stdin); w=p['skills']['writing']; print(w['practiceCount'])"
```

If `practiceCount > 0 AND practiceCount % 5 == 0` → run calibration. Otherwise skip.

---

## Step 1 — Load anchor bank

Read `.ielts/calibration/writing-anchors.json`. Pick 2-3 anchors:
- One from a band **lower** than the student's typical band (use `currentBand` or `targetBand`)
- One from a band **higher**
- Avoid re-using the same anchor as the last calibration (check `.ielts/calibration/calibration-log.json` → `history[0].anchorsTested`)

---

## Step 2 — Score blind

Score each selected anchor essay as if it were a real student submission:
- **Do NOT look at the reference scores** stored in the anchor
- Follow the standard 4-dimension scoring: TR, CC, LR, GRA
- Provide evidence for each score

---

## Step 3 — Compare to reference

For each anchor, compare your blind scores to `referenceScores`:

```
drift = |scoredBand - referenceBand|
```

- `drift <= 0.5` → **PASS** (well-calibrated)
- `0.5 < drift <= 1.0` → **MINOR DRIFT** — note but don't alarm
- `drift > 1.0` → **SIGNIFICANT DRIFT** — flag in coach notes

---

## Step 4 — Log results

Update `.ielts/calibration/calibration-log.json`:

```json
{
  "date": "<ISO datetime>",
  "practiceCountAt": <n>,
  "anchorsTested": ["<id>", "<id>"],
  "results": [
    {"anchorId": "<id>", "referenceBand": <x.x>, "scoredBand": <y.y>, "drift": <d>, "passed": <bool>}
  ],
  "overallPassed": <bool>,
  "maxDrift": <max_d>
}
```

Update `lastCalibrationAt` and `lastCalibrationSession` at top level.

---

## Step 5 — Report (brief)

**If all pass:** No output needed. Just log silently.

**If drift detected:**
```
⚙️ Calibration check: minor drift detected.
   Anchor {id} (Band {ref}) scored as Band {scored} — off by {drift}.
   This won't affect your scores. I've logged it for monitoring.
```

Add coach note:
```bash
.venv/bin/python3 shared/ielts_cli.py memory add \
  --content "CALIBRATION: Drift on {dimension}. Anchor {id} scored {scored} vs reference {ref}." \
  --category observation \
  --skill writing \
  --priority medium
```

---

## Step 6 — Proceed with student evaluation

Calibration is informational only. Continue with normal Phase 5 student essay evaluation regardless of drift result.
