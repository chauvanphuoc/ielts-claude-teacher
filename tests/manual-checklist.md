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

- [ ] **SP-1: Task auto-load on tab switch**
  - Open HTML Studio, click Speaking tab
  - Verify source dropdown auto-populates with "cambridge-1"
  - Verify test dropdown auto-populates and auto-selects "Test 1"
  - Verify Part 1 cue card renders with interview questions
  - Verify Part 2 and Part 3 pills are clickable and load correct content

- [ ] **SP-2: Task selector manual selection**
  - Change source dropdown (if multiple available)
  - Verify test dropdown updates
  - Change test dropdown manually
  - Verify cue card updates to new test's Part 1

- [ ] **SP-3: Part navigation keyboard**
  - Click Part 1 pill, press ArrowRight → Part 2 should focus
  - Press ArrowRight again → Part 3 should focus
  - Press ArrowLeft → Part 2 should focus
  - Press Enter/Space on focused pill → cue card updates

- [ ] **SP-4: Empty state — no speaking sources**
  - Delete shared/speaking/speaking_cambridge-1.json
  - Reload Speaking tab
  - Verify empty state shows "No speaking tasks available yet" with CLI command
  - Restore JSON file

- [ ] **SP-5: Error state — API unavailable**
  - Stop server.py
  - Reload Speaking tab
  - Verify error card shows "Failed to load speaking sources" with retry button
  - Start server, click retry → verify tasks load

- [ ] **SP-6: Save with task context**
  - Record speaking for >10 seconds with a task loaded
  - Click "Save & Ask Claude to Evaluate"
  - Check .ielts/speaking/latest.json
  - Verify it contains: source, testNumber, partNumber, taskTitle, transcript, duration

- [ ] **SP-7: Success message shows task context**
  - After save, verify success state shows task title, duration, word count
  - Verify CTA text: "Switch to Claude and say: evaluate my speaking"

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
  - Send valid JSON, verify 200 and file written to .ielts/

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

## Listening Test Paths (10 paths)

### Template Loading
- [ ] **L-M1: Listening template loads with valid source+test params**
  1. Start server: `.venv/bin/python3 skills/ielts-teacher/server.py`
  2. Open `http://localhost:8765/lessons/listening-test.html?source=cambridge-1&test=1`
  3. Verify: test title shows "Cambridge IELTS 1 — Test 1"
  4. Verify: 4 section steps visible in nav
  5. Verify: Section 1 questions render (10 questions)

- [ ] **L-M2: Listening template shows error state for invalid source**
  1. Open `http://localhost:8765/lessons/listening-test.html?source=nonexistent&test=1`
  2. Verify: error state visible with message about missing source
  3. Verify: loading spinner disappears

- [ ] **L-M3: Listening template shows error state for missing test**
  1. Open `http://localhost:8765/lessons/listening-test.html?source=cambridge-1&test=99`
  2. Verify: error state visible with "Test not found" message
  3. Verify: available test numbers shown

### Audio Player
- [ ] **L-M4: Audio player loads MP3 for section**
  1. Open test 1 section 1
  2. Verify: audio player shows loading spinner initially
  3. Verify: play button appears after audio loads
  4. Verify: time display shows current/total

- [ ] **L-M5: Audio player keyboard controls**
  1. Click play button
  2. Press Space → verify audio pauses
  3. Press Space again → verify audio resumes
  4. Press ArrowRight → verify seek forward 5s
  5. Press ArrowLeft → verify seek backward 5s
  6. Press M → verify mute toggles

- [ ] **L-M6: Audio player error state**
  1. (Simulate by renaming an MP3 file temporarily)
  2. Verify: audio error message visible
  3. Verify: play button becomes warning icon

### Section Navigation
- [ ] **L-M7: Section nav updates progress**
  1. Answer all questions in section 1
  2. Click "Next Section"
  3. Verify: section 1 step shows "done" (green check)
  4. Verify: section 2 step shows "active" (blue)
  5. Verify: audio switches to section 2 MP3
  6. Verify: new questions render for section 2

- [ ] **L-M8: Section nav validation blocks navigation**
  1. Leave some questions unanswered in section 1
  2. Click "Next Section"
  3. Verify: warning appears about unanswered questions
  4. Verify: unanswered questions highlighted with warning border
  5. Verify: stays on section 1

### Submit & Results
- [ ] **L-M9: Submit shows results with section scores**
  1. Navigate to section 4, answer all questions
  2. Click "Submit Answers"
  3. Verify: results display with per-question correct/incorrect
  4. Verify: transcript panel appears below results
  5. Verify: warning banner appears (server not running fallback)
  6. Start server.py, click Retry → verify results saved

- [ ] **L-M10: Transcript toggle works**
  1. After submitting, click "Show Transcript"
  2. Verify: transcript content expands
  3. Verify: Q-markers (Q1, Q2) are highlighted in amber
  4. Click again → verify: transcript collapses

### JSON Integrity
- [ ] **L-A1: Listening JSON valid**
  1. Run: `.venv/bin/python3 tests/test_listening_json.py`
  2. Verify: all 15 tests pass

### KC Graph
- [ ] **L-A2: Listening KCs in graph**
  1. Run: `.venv/bin/python3 tests/test_student_profile.py`
  2. Verify: 7 listening KC tests pass
  3. Verify: total 44 tests pass

---

Run before each ship. Check all boxes or document failures.
Last run: __________  |  Passed: __/40  |  By: __________
