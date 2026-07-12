# IELTS Claude Teacher — Manual Test Checklist

28 test paths from the Eng review test coverage diagram. Run before each ship.
Check off each item after verification.

## E2E Flows (3 paths)

- [ ] **E2E-1: Speaking Record → Transcribe → Save → Claude Scores**
  1. Open studio in browser (http://localhost:8765/ielts-studio.html)
  2. Click Speaking tab, click record button
  3. Speak for 15+ seconds, verify transcript appears
  4. Click stop, click "Save & Ask Claude to Evaluate"
  5. Verify success message appears
  6. In Claude: say "evaluate my speaking"
  7. Verify Claude reads transcript, gives band score with reasoning
  8. Verify roadmap.json updates with new speaking band

- [ ] **E2E-2: Listening Test → Play MP3 → Answer → Save → Claude Grades**
  1. Select Cambridge IELTS 1 Test 1 from dropdown
  2. Verify MP3 loads and plays (audio player visible)
  3. Type answers in question inputs (at least 5)
  4. Click "Save Answers & Ask Claude to Grade"
  5. Verify success message
  6. In Claude: say "grade my listening test"
  7. Verify Claude reads answers, compares to answer key, gives section breakdown
  8. Verify roadmap.json updates with new listening band

- [ ] **E2E-3: Writing Submit → Save → Claude Evaluates → Diff Renders**
  1. Click Writing Diff tab
  2. Paste a 150+ word essay
  3. Click "Submit Essay & Ask Claude to Evaluate"
  4. In Claude: say "evaluate my essay"
  5. Verify Claude gives TR/CC/LR/GRA scores with specific evidence
  6. Verify Claude generates band-upgraded rewrite
  7. After Claude saves rewrite, refresh studio
  8. Verify diff view shows side-by-side comparison

## User Flows (10 paths)

### Learning Path Init
- [ ] **UF-1: /init-path-learn — all skills**
  - Verify Claude asks target band, exam date, active skills
  - Choose all 4 skills, verify roadmap.json created
  - Verify roadmap panel shows all 4 skill bars

- [ ] **UF-2: /init-path-learn — skip speaking**
  - Verify speaking bar shows "(skipped)" in roadmap panel
  - Verify roadmap.json shows speaking not in activeSkills

- [ ] **UF-3: /init-path-learn — invalid target band**
  - Enter band 10.0, verify Claude asks again
  - Enter band 3.0, verify Claude asks again

- [ ] **UF-4: /init-path-learn — all skills skipped**
  - Try to skip all 4 skills, verify Claude requires at least 1

### Speaking Practice
- [ ] **UF-5: Mic permission denied**
  - Deny mic permission in browser
  - Click record, verify error message with instructions
  - Grant permission, verify record works after reload

- [ ] **UF-6: Recording too short**
  - Record for < 10 seconds
  - Verify warning message appears
  - Verify submit button stays disabled

### Listening Test
- [ ] **UF-7: MP3 file missing**
  - Select a test, verify audio loads
  - (Manual: rename an MP3 to simulate missing, verify error state)

- [ ] **UF-8: Duplicate test submission**
  - Submit answers, verify success
  - Submit again, verify warning about duplicate (or Claude catches it)

### Writing Diff
- [ ] **UF-9: Empty essay submission**
  - Click submit with empty textarea
  - Verify submit button is disabled (min 50 chars)

- [ ] **UF-10: Roadmap panel empty state**
  - Delete roadmap.json, reload studio
  - Verify roadmap panel shows "No roadmap yet" message
  - Run /init-path-learn, verify roadmap panel populates

## Code Paths (12 paths)

### Teacher Skill
- [ ] **CP-1: /ielts-check all pass**
  - Run /ielts-check in Claude
  - Verify all checks show PASS (Python, CLI, data dir, roadmap, studio, bridge, MP3s)

- [ ] **CP-2: /ielts-check with missing component**
  - Remove one file, run /ielts-check
  - Verify that component shows FAIL/MISSING

- [ ] **CP-3: Roadmap schema validation**
  - Create roadmap.json with the Band 5.0 calibration example
  - Verify Claude parses it correctly and displays progress

### LLM Scoring
- [ ] **CP-4: Writing Band 5.0 calibration**
  - Run: `python3 tests/eval_writing.py --check`
  - Enter Band 5.0 essay, verify Claude scores 5.0 ± 0.5
  - If FAIL: scoring prompts need calibration

- [ ] **CP-5: Writing Band 6.5 calibration**
  - Enter Band 6.5 essay, verify Claude scores 6.5 ± 0.5

- [ ] **CP-6: Writing Band 8.0 calibration**
  - Enter Band 8.0 essay, verify Claude scores 8.0 ± 0.5

- [ ] **CP-7: Speaking Band 5.0 calibration**
  - Run: `python3 tests/eval_speaking.py --check`
  - Enter Band 5.0 transcript, verify 5.0 ± 0.5

- [ ] **CP-8: Speaking Band 6.5 calibration**
  - Enter Band 6.5 transcript, verify 6.5 ± 0.5

- [ ] **CP-9: Speaking Band 8.0 calibration**
  - Enter Band 8.0 transcript, verify 8.0 ± 0.5

### File Bridge
- [ ] **CP-10: POST invalid JSON**
  - Send invalid JSON to http://localhost:8765/save
  - Verify 400 error response

- [ ] **CP-11: POST valid JSON**
  - Send valid JSON, verify 200 and file written to ~/.ielts/

- [ ] **CP-12: GET missing MP3**
  - Request /audio/cambridge-1/nonexistent.mp3
  - Verify 404 response

## Cross-Skill Analysis (3 paths)

- [ ] **CS-1: Root cause identification**
  - Create roadmap with T/F/NG reading errors + MC listening errors
  - Ask Claude to diagnose, verify it identifies "implied vs stated" pattern
  - Verify crossSkillPatterns entry added to roadmap.json

- [ ] **CS-2: Proactive weakness pre-emption**
  - Have weak areas in roadmap.json
  - Say "I'm about to take Cambridge 1 Test 1"
  - Verify Claude warns about predicted traps based on weak areas

- [ ] **CS-3: Learning path custom skill set**
  - /init-path-learn with writing + reading only
  - Verify roadmap shows only 2 active skills
  - Verify listening/speaking show as inactive

---

## Quick Smoke Test (5 min)

- [ ] Studio loads at http://localhost:8765/ielts-studio.html
- [ ] All 3 tabs switch correctly (Speaking, Listening, Writing Diff)
- [ ] Roadmap panel renders (empty or with data)
- [ ] Bridge server starts without errors
- [ ] /ielts-check returns all PASS

---

Run before each ship. Check all boxes or document failures.
Last run: __________  |  Passed: __/28  |  By: __________
