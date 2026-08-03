# pick-from-list — Implementation Plan

**Status:** APPROVED  
**Design:** v3 (B1-B7 + review findings F1-F6)  
**Scope:** 7 phases, 6 files changed, 1 data migration  
**Impact:** listening_cambridge-2.json (17 circle-N → 6 pick-from-list groups)

### Review Findings Applied (v3)

| # | Finding | Severity | Fix |
|---|---------|----------|-----|
| F1 | Substring selector collision (`*="1"` matches Q10) | 🔴 High | Find group by name attribute instead of substring query |
| F2 | Constraint 3 contradictory (mandatory "in any order" vs Group 6) | 🔴 High | Nới lỏng constraint 3: mandatory → optional warning |
| F3 | Silent truncation of over-selection inflates score | 🔴 High | Fail cứng: over-selection → score=0, flag `overSelected: true` |
| F4 | questionNumbers derived from pickCount can misalign | 🟡 Medium | questionNumbers always from parsed data, never computed |
| F5 | Group identity not normalized (join order) | 🟡 Medium | Sort questionNumbers before join → canonical group key |
| F6 | Missing automated regression tests | 🟡 Medium | Added test cases for selector collision, over-selection, parity |

---

## Phase 1: JSON Data Migration

**File:** `shared/listening/listening_cambridge-2.json`

### What to change

Every group of N consecutive `circle-three`/`circle-two`/`circle-four` questions that share the same stem → 1 `pick-from-list` entry.

Apply 3 constraints from B1-fix (F2-fix: constraint 3 is optional, generates warning if absent):
1. Same stem across all questions in range
2. "Choose {N} letters" in instructions
3. Answer key has "in any order" / "in either order" — **optional, WARNING if absent**

### Verified migration map (6 groups total, all in listening_cambridge-2.json)

Verified by script — all 17 `circle-N` questions form exactly 6 groups. No reading JSONs are affected. `listening_cambridge-1.json` not affected.

#### Group 1: Test 1, Section 1, Q6-8 (circle-three → pick-from-list)

Stem: "What types of films does Louise like? Choose THREE letters A-F."  
Current answers: B, D, F — answer key: "in any order with Q7, Q8" / "in any order with Q6, Q8" / "in any order with Q6, Q7"  
Options: A-F (Action, Comedies, Musicals, Romance, Westerns, Wildlife)  
✅ All 3 constraints pass. Migrate.

#### Group 2: Test 1, Section 2, Q16-18 (circle-three → pick-from-list)

Stem: "What does Charles say about his friends? Choose THREE letters A-F."  
Current answers: B, C, E — answer key: "in any order with Q17, Q18" / "in any order with Q16, Q18" / "in any order with Q16, Q17"  
Options: A-F (He met them..., They kept..., One helped..., One owned..., Some travelled..., Only one group...)  
✅ All 3 constraints pass. Migrate.

#### Group 3: Test 1, Section 2, Q19-20 (circle-two → pick-from-list)

Stem: "What does Charles say about the donkeys? Choose TWO letters A-E."  
Current answers: B, D — answer key: "in either order with Q20" / "in either order with Q19"  
Options: A-E (He rode them..., He named them..., One died..., Difficult diversions..., Long-suffering)  
✅ All 3 constraints pass. "in either order" → `anyOrder: true`. Migrate.

#### Group 4: Test 3, Section 2, Q11-14 (circle-four → pick-from-list)

Stem: "Which FOUR activities of the Union are mentioned by the speaker?"  
Current answers: A, C, E, G — answer key: "in any order" across Q11-14  
✅ All 3 constraints pass. Migrate.

#### Group 5: Test 3, Section 2, Q15-16 (circle-two → pick-from-list)

Stem: "Which TWO of the following can you get advice about from the Union?"  
Current answers: B, E — answer key: "in either order" across Q15-16  
✅ All 3 constraints pass. Migrate.

#### Group 6: Test 3, Section 4, Q38-40 (circle-three → pick-from-list) ⚠️

Stem: "Which THREE of the following uses of dam water are mentioned?"  
Current answers: B, D, E — answer key: **NO "in any order" note** (likely JSON generation error — agent didn't capture the note from textbook)  
Options: 7 options A-G about dam water uses  
⚠️ Constraint 3 not met, but F2-fix: constraint 3 is now optional. "Choose THREE letters" is inherently unordered in IELTS. Migrate, flag `_missingAnyOrderNote: true` để human review textbook.

#### NOT migrated — Q11-13, Q14, Q15 (Test 1 Section 2)

Q11-13 are `gapfill` (route book, 900 miles, North Africa) — individual, different stems.  
Q14, Q15 are individual `multiple-choice` — each has a DIFFERENT stem.  
✅ Correctly excluded by constraint 2.

### Answer key migration

For each pick-from-list group, replace N individual entries with 1 group entry:

```jsonc
// Before:
{"number": 6, "answer": "B", "note": "in any order with Q7, Q8"},
{"number": 7, "answer": "D", "note": "in any order with Q6, Q8"},
{"number": 8, "answer": "F", "note": "in any order with Q6, Q7"}

// After:
{"groupType": "pick-from-list", "questionNumbers": [6,7,8], "answers": ["B","D","F"], "pickCount": 3, "anyOrder": true, "maxMarks": 3}
```

### Validation after migration

Run:
```bash
.venv/bin/python3 shared/generate_test_html.py --skill listening --source cambridge-2 --all
```

Verify:
- [ ] Question count unchanged (total questions = original total)
- [ ] No JSON parse errors
- [ ] All answer key entries resolved correctly

---

## Phase 2: Python Generator

**File:** `shared/generate_test_html.py`

### 2.1 Add canonical type (line ~188)

```python
QUESTION_TYPE_CANONICAL = {
    # ... existing ...
    "pick-from-list": "pick-from-list",
}
```

### 2.2 Update count_questions_in_list (line ~120)

```python
def count_questions_in_list(questions: list) -> int:
    count = 0
    for q in questions:
        if isinstance(q, dict):
            if q.get("type") == "pick-from-list":
                count += len(q.get("questionNumbers", []))
            elif q.get("type") == "form-completion" and "rows" in q:
                rows = q.get("rows", [])
                for row in rows:
                    for cell in row:
                        if isinstance(cell, dict) and cell.get("input"):
                            count += 1
            else:
                count += 1
        else:
            count += 1
    return count
```

### 2.3 Update normalize_question_types (line ~205)

Pick-from-list questions already have canonical type — no normalization needed. Just pass through.

### Verification

```bash
.venv/bin/python3 shared/generate_test_html.py --skill listening --source cambridge-2 --test 1 --section 1
# Check: output says "10 questions" (unchanged)
# Check: HTML contains pick-from-list checkboxes, not 3 radio groups
```

---

## Phase 3: HTML Template — Rendering

**File:** `skills/ielts-teacher/templates/section-templates/listening-section.html`

### 3.1 Add CSS for pick-from-list (before `</style>`)

Insert:
- `.sr-only` utility
- `.pick-count-badge` badge style
- `.option-checkbox` + `.option-disabled` states
- `.option-correct`, `.option-missed`, `.option-wrong` (for reveal)
- `.pick-list-summary` + child spans (`.summary-score`, `.summary-matched`, `.summary-missed`, `.summary-extra`, `.summary-over-selected`)
- `.over-selection-warning` (F3-fix: red alert for over-selected groups)
- `.result-line.matched`, `.result-line.missed`, `.result-line.extra` (for results panel)
- `.result-group-header` (for group result header)

### 3.2 Add renderPickFromList function (after renderMC, ~line 999)

Full function as designed in v2 — includes:
- Label "Questions X-Y"
- Instruction + Pick N badge
- Question text + images
- Checkbox list with role="group", aria-label, aria-describedby
- enforcePickLimit on change
- Hidden .sr-only instruction span

### 3.3 Add enforcePickLimit function

Disables unchecked boxes when limit reached, re-enables when under limit.

### 3.4 Add switch case for pick-from-list (after line ~908)

```javascript
case 'pick-from-list':
  renderPickFromList(div, q);
  break;
```

### 3.5 Repeat for reading-section.html

Same changes — CSS + renderPickFromList + enforcePickLimit + switch case.  
Reading template already has `renderQuestion()` function — add the case there.

---

## Phase 4: HTML Template — Grading + Reveal

**File:** `skills/ielts-teacher/templates/section-templates/listening-section.html`

### 4.1 Add findGroupByQuestionNumber helper (new function)

Trước `getUserAnswer`, thêm helper để tìm group từ 1 qNumber bất kỳ — tránh substring collision (F1-fix):

```javascript
// F1-fix: Find pick-from-list group by exact question number membership.
// Returns the group object from questions[], or null if not found.
function findGroupByQuestionNumber(qNumber) {
  for (var i = 0; i < questions.length; i++) {
    var q = questions[i];
    if (q.type === 'pick-from-list') {
      if (q.questionNumbers.indexOf(qNumber) !== -1) {
        return q;
      }
    }
  }
  return null;
}

// F5-fix: Return canonical group key (sorted questionNumbers joined).
function getGroupKey(questionNumbers) {
  return questionNumbers.slice().sort(function(a, b) { return a - b; }).join('-');
}
```

### 4.2 Update getUserAnswer (line ~1237)

Add `pick-from-list` case — dùng group name attribute thay vì substring query (F1-fix):

```javascript
if (qType === 'pick-from-list') {
  // F1-fix: Find group by exact membership, construct name attribute directly.
  // Avoids substring collision: '1' matching Q10, Q11, Q12.
  var group = findGroupByQuestionNumber(qNumber);
  if (!group) return [];
  
  // F5-fix: canonical group key
  var groupKey = getGroupKey(group.questionNumbers);
  var groupName = 'pick-group-' + groupKey;
  
  var allCB = document.querySelectorAll('input[type="checkbox"][name="' + groupName + '"]');
  var checked = [];
  allCB.forEach(function(cb) {
    if (cb.checked) checked.push(cb.value);
  });
  
  return checked.sort();
}
```

### 4.3 Over-selection handling principle (F3-fix)

Over-selection được phát hiện trong `checkAnswers()`, không phải `getUserAnswer()`.  
`getUserAnswer()` trả về **toàn bộ** checked boxes (kể cả khi vượt quá pickCount).  
`checkAnswers()` sẽ phát hiện `checked.length > pickCount` và fail cứng group → score=0.

Lý do: `getUserAnswer` chỉ là data collector. Logic phạt nằm ở grader.

### 4.4 Update getAnswerKey (line ~1220)

Handle group-type answer key entries:
```javascript
function getAnswerKey(qNumber) {
  if (!ANSWER_KEYS || ANSWER_KEYS === null) return null;
  
  if (Array.isArray(ANSWER_KEYS)) {
    for (var i = 0; i < ANSWER_KEYS.length; i++) {
      // Group entry
      if (ANSWER_KEYS[i].groupType === 'pick-from-list' && 
          ANSWER_KEYS[i].questionNumbers.indexOf(qNumber) !== -1) {
        return ANSWER_KEYS[i];
      }
      // Individual entry
      if (ANSWER_KEYS[i].number === qNumber || ANSWER_KEYS[i].questionNumber === qNumber) {
        return ANSWER_KEYS[i];
      }
    }
  }
  // ... existing object format handling
}
```

### 4.5 Update checkAnswers (line ~1325)

Group grading với processedGroups dedup (F5-fix: canonical key), set comparison, và over-selection fail cứng (F3-fix):

```javascript
function checkAnswers() {
  var results = [];
  var processedGroups = {};  // canonical group key → true (F5-fix)
  var correctCount = 0;
  
  questions.forEach(function(q) {
    if (q.type === 'pick-from-list') {
      // F5-fix: canonical group key prevents duplicate or missed grading
      var groupKey = getGroupKey(q.questionNumbers);
      if (processedGroups[groupKey]) return;
      processedGroups[groupKey] = true;
      
      var userPicks = getUserAnswer(q.questionNumbers[0], 'pick-from-list');
      var correctSet = q.answers || [];
      var pickCount = q.pickCount;
      
      // F3-fix: Over-selection detection — fail cứng nếu chọn quá N
      if (userPicks.length > pickCount) {
        correctCount += 0;  // 0 marks for this group
        results.push({
          type: 'pick-from-list',
          questionNumbers: q.questionNumbers,
          pickCount: pickCount,
          score: 0,
          maxScore: pickCount,
          matched: [],
          missed: correctSet,
          extra: userPicks,
          userAnswer: userPicks,
          correctAnswer: correctSet,
          anyOrder: q.anyOrder,
          overSelected: true   // F3-fix: flag for UI to show warning
        });
        return;
      }
      
      // Set comparison (unordered)
      var matched = userPicks.filter(function(p) { return correctSet.indexOf(p) !== -1; });
      var missed  = correctSet.filter(function(a) { return userPicks.indexOf(a) === -1; });
      var extra   = userPicks.filter(function(p) { return correctSet.indexOf(p) === -1; });
      
      var score = matched.length;
      correctCount += score;
      
      results.push({
        type: 'pick-from-list',
        questionNumbers: q.questionNumbers,
        pickCount: pickCount,
        score: score,
        maxScore: pickCount,
        matched: matched,
        missed: missed,
        extra: extra,
        userAnswer: userPicks,
        correctAnswer: correctSet,
        anyOrder: q.anyOrder,
        overSelected: false
      });
    } else {
      // existing individual grading
      var key = getAnswerKey(q.number);
      var userAnswer = getUserAnswer(q.number, q.type);
      var correct = isCorrect(userAnswer, key);
      if (correct) correctCount++;
      results.push({
        number: q.number,
        correct: correct,
        userAnswer: userAnswer,
        correctAnswer: key ? key.answer : null,
        acceptable: key ? (key.acceptable || []) : []
      });
    }
  });
  
  return {
    total: totalMarks,
    correct: correctCount,
    results: results
  };
}
```

### 4.6 Update displayResults — group result + over-selection warning

```javascript
// Inside displayResults, for r.type === 'pick-from-list':
function displayResults(scoring) {
  if (!resultsPanel || !resultsList) return;
  resultsPanel.classList.remove('hidden');
  resultsHeading.textContent = 'Results: ' + scoring.correct + ' / ' + scoring.total;

  resultsList.innerHTML = '';
  scoring.results.forEach(function(r) {
    var item = document.createElement('div');
    
    if (r.type === 'pick-from-list') {
      var range = r.questionNumbers[0] + '-' + r.questionNumbers[r.questionNumbers.length - 1];
      var isFullCorrect = r.score === r.maxScore && !r.overSelected;
      item.className = 'result-item ' + (isFullCorrect ? 'correct' : 'wrong');
      
      // Header
      var header = document.createElement('div');
      header.className = 'result-group-header';
      header.innerHTML = '<strong>Questions ' + range + '</strong>: ' + r.score + '/' + r.maxScore + ' correct';
      item.appendChild(header);
      
      // F3-fix: Over-selection warning
      if (r.overSelected) {
        var warning = document.createElement('div');
        warning.className = 'over-selection-warning';
        warning.textContent = '⚠️ Bạn đã chọn ' + r.userAnswer.length + ' đáp án (chỉ được chọn ' + r.pickCount + '). Nhóm này bị tính 0 điểm.';
        item.appendChild(warning);
      }
      
      // Matched (green)
      r.matched.forEach(function(label) {
        var line = document.createElement('div');
        line.className = 'result-line matched';
        line.innerHTML = '✓ <span class="option-label-marker">' + escHtml(label) + '</span> ' + escHtml(optionTextForLabel(label, r));
        item.appendChild(line);
      });
      
      // Missed (red)
      r.missed.forEach(function(label) {
        var line = document.createElement('div');
        line.className = 'result-line missed';
        line.innerHTML = '✗ <span class="option-label-marker">' + escHtml(label) + '</span> (missed)';
        item.appendChild(line);
      });
      
      // Extra (red)
      r.extra.forEach(function(label) {
        var line = document.createElement('div');
        line.className = 'result-line extra';
        line.innerHTML = '✗ <span class="option-label-marker">' + escHtml(label) + '</span> (incorrect)';
        item.appendChild(line);
      });
      
    } else {
      // existing individual result display
      item.className = 'result-item ' + (r.correct ? 'correct' : 'wrong');
      item.innerHTML =
        '<span>Q' + r.number + ': ' + (r.correct ? '&#10004;' : '&#10008;') + '</span>' +
        '<span class="result-answer">' +
        'Your answer: <span class="' + (r.correct ? 'correct-answer' : 'wrong-answer') + '">' +
        escHtml(formatAnswer(r.userAnswer)) + '</span>' +
        (r.correct ? '' : ' → Correct: <span class="correct-answer">' + escHtml(formatAnswer(r.correctAnswer)) + '</span>') +
        '</span>';
    }
    
    resultsList.appendChild(item);
  });

  if (btnToggleAnswers) btnToggleAnswers.disabled = false;
}
```

### 4.7 Update revealAnswers — group checkbox highlight (B6-fix)

```javascript
function revealAnswers() {
  isAnswersRevealed = true;
  document.body.classList.add('answer-revealed');

  scoring.results.forEach(function(r) {
    if (r.type === 'pick-from-list') {
      var groupKey = getGroupKey(r.questionNumbers);
      var groupName = 'pick-group-' + groupKey;
      var allCB = document.querySelectorAll('input[name="' + groupName + '"]');
      
      // Build lookup for option text
      var groupEl = document.getElementById('question-group-' + groupKey);
      
      allCB.forEach(function(cb) {
        var label = cb.value;
        var item = cb.closest('.option-mc');
        cb.disabled = true;  // lock after reveal
        
        if (r.matched.indexOf(label) !== -1) {
          item.classList.add('option-correct');
          cb.checked = true;
        } else if (r.missed.indexOf(label) !== -1) {
          item.classList.add('option-missed');
          cb.checked = true;
        } else if (r.extra.indexOf(label) !== -1) {
          item.classList.add('option-wrong');
          cb.checked = true;
        }
      });
      
      // Summary text below group
      if (groupEl) {
        var summary = document.createElement('div');
        summary.className = 'pick-list-summary';
        var parts = [];
        parts.push('<span class="summary-score">' + r.score + '/' + r.maxScore + '</span>');
        if (r.matched.length > 0) parts.push('<span class="summary-matched">✓ ' + r.matched.join(', ') + '</span>');
        if (r.missed.length > 0) parts.push('<span class="summary-missed">✗ Missed: ' + r.missed.join(', ') + '</span>');
        if (r.extra.length > 0) parts.push('<span class="summary-extra">✗ Extra: ' + r.extra.join(', ') + '</span>');
        if (r.overSelected) parts.push('<span class="summary-over-selected">⚠️ Over-selected: ' + r.userAnswer.length + '/' + r.pickCount + '</span>');
        summary.innerHTML = parts.join(' ');
        groupEl.appendChild(summary);
      }
      
    } else {
      // existing individual reveal
      var qEl = document.getElementById('question-' + r.number);
      if (!qEl) return;
      qEl.classList.add(r.correct ? 'correct-answer' : 'wrong-answer');
      if (!r.correct) {
        var hint = document.createElement('div');
        hint.className = 'result-answer';
        hint.style.marginTop = '8px';
        hint.innerHTML = '🔒 Correct: <span class="correct-answer">' + escHtml(formatAnswer(r.correctAnswer)) + '</span>';
        qEl.appendChild(hint);
      }
    }
  });

  if (btnToggleAnswers) {
    btnToggleAnswers.innerHTML = '🔓 Hide Answers';
    btnToggleAnswers.disabled = false;
  }
}
```

### 4.8 Repeat for reading-section.html

---

## Phase 5: ielts-json-init SKILL.md

**File:** `skills/ielts-json-init/SKILL.md`

### 5.1 Add pick-from-list to Step 4 (Parse questions) marker table

After the existing marker table row:
```markdown
| `- **N** question text` | Numbered question (list format) | Create new question |

Add:
| `Choose {N} letters {A}-{Z}` | Pick-from-list group question | Tạo 1 entry `pick-from-list` thay vì N câu riêng lẻ |
```

### 5.2 Add CRITICAL block: pick-from-list detection

After the matching-headings CRITICAL block (~line 165), add a new CRITICAL block:

```markdown
**CRITICAL: pick-from-list detection — 2 mandatory + 1 optional constraints (F2-fix).** 

Một dạng câu hỏi phổ biến trong Listening: "Choose THREE letters A-F" — học sinh chọn N đáp án từ 1 danh sách, không phân biệt thứ tự.

**Detection — constraints:**

1. **[MANDATORY] Phrase match:** Question text chứa "Choose {TWO/THREE/FOUR/FIVE} letters {X}-{Y}"
2. **[MANDATORY] Same stem:** Tất cả các câu trong range (N, N+1, N+2) có CÙNG MỘT question stem — hoặc không có stem riêng (toàn bộ text nằm trước option list). Nếu mỗi câu có stem riêng → individual `multiple-choice`, KHÔNG phải pick-from-list.
3. **[OPTIONAL — F2-fix] Answer key confirms:** Answer key row có ghi "in any order" hoặc "in either order". Nếu thiếu → VẪN tạo pick-from-list (constraints 1+2 pass), nhưng flag `_missingAnyOrderNote: true` để human review textbook.

**JSON format:**
```json
{
  "type": "pick-from-list",
  "questionNumbers": [6, 7, 8],
  "pickCount": 3,
  "text": "What types of films does Louise like?",
  "instructions": "Choose THREE letters A-F.",
  "options": [
    {"label": "A", "text": "Action"},
    ...
  ],
  "answers": ["B", "D", "F"],
  "anyOrder": true
}
```

**Parsing steps:**
1. Khi gặp "Choose {N} letters" → kiểm tra constraint 2 (cùng stem)
2. Nếu pass → đọc options từ bullet list `- **A** text`
3. **F4-fix:** `questionNumbers` luôn lấy từ parsed question numbers thực tế (các số câu xuất hiện trong markdown), KHÔNG suy từ `pickCount`. Nếu markdown ghi `**16**`, `**17**`, `**18**` → `questionNumbers: [16, 17, 18]`.
4. Đọc answer key, validate: `len(answers) == len(questionNumbers)`. Nếu không → ERROR.
5. So sánh pickCount từ question text với len(answers). Nếu mismatch → WARNING, dùng len(answers), flag `_pickCountMismatch: true`.
6. Nếu answer key KHÔNG có "in any order" → VẪN tạo pick-from-list, flag `_missingAnyOrderNote: true` (F2-fix).
```

### 5.3 Update Step 5 (Extract answer keys)

Update the multi-answer row section to produce group entries:

```markdown
**Multi-answer row với group context:** `| 11-13 | E F H (in any order) |`

1. Parse answers: `"E F H"` → `["E", "F", "H"]`
2. Validate: `len(answers)` phải = range size. Nếu không → **ERROR**.
3. Tạo group answer entry:
   ```json
   {"groupType": "pick-from-list", "questionNumbers": [11,12,13], "answers": ["E","F","H"], "pickCount": 3, "anyOrder": true, "maxMarks": 3}
   ```
4. Nếu "in either order" → chuẩn hóa về `anyOrder: true`.
```

### 5.4 Update Step 6 (Verification)

Add to verification checklist:
```markdown
8. **pick-from-list validation:** Every pick-from-list entry has `len(answers) == len(questionNumbers)`. Report mismatch as ERROR.
9. **pickCount matches:** Every pick-from-list entry has `pickCount == len(answers)`. Report mismatch as WARNING with `_pickCountMismatch: true` flag.
```

---

## Phase 6: ielts-teacher SKILL.md

**File:** `skills/ielts-teacher/SKILL.md`

### 6.1 Update Step 4 (Categorize errors by KC — Listening, line ~629)

Add rows to the error pattern table:

```markdown
| Pick-from-list: missed correct option(s) — không chọn đáp án đúng | `kc-listen-mc` |
| Pick-from-list: selected wrong option(s) — chọn đáp án sai | `kc-listen-mc` |
```

### 6.2 Add pick-from-list scoring rules block

After the error pattern table, add:

```markdown
**pick-from-list scoring rules (Listening + Reading):**

Khi gặp câu hỏi `type: "pick-from-list"` trong JSON:

1. Đây là câu hỏi chọn NHIỀU đáp án từ 1 danh sách chung
2. Mỗi group có `pickCount` marks (vd: Q6-8 = 3 marks)
3. **Set comparison:** `score = len(userPicks ∩ correctAnswers)` — KHÔNG quan tâm thứ tự
4. `{B, D, F}` = `{F, B, D}` = `{D, F, B}` → đều là 3/3
5. `errors = pickCount - score`
6. Với answer key cũ có `"note": "in any order with Qx, Qy"` → grade cả cụm như 1 unordered set

**Qualitative feedback cho pick-from-list:**
- missed only: "bỏ sót — không nhận ra paraphrase hoặc chưa nghe được thông tin"
- extra only: "chọn sai — bị distractor đánh lừa bởi từ khóa tương tự"
- cả missed và extra: "cần luyện thêm paraphrase + distractor"
```

### 6.3 Update KC mastery calculation

No formula change needed — just note that `session_errorRate = session_errors / session_total` where errors from pick-from-list = `pickCount - score`.

---

## Phase 7: Regenerate + Validate

### 7.1 Regenerate all HTML

```bash
.venv/bin/python3 shared/generate_test_html.py --skill listening --source cambridge-2 --all
```

### 7.2 Targeted regression tests (F6-fix)

**F1 regression — substring selector collision:**
- [ ] Test Q1 of a pick-from-list group — verify `getUserAnswer(1, 'pick-from-list')` does NOT match checkboxes from group Q10-12
- [ ] Test Q10 of a group Q10-12 — verify it does NOT match group Q1-3
- [ ] Method: create 2 groups with overlapping digits (Q1-2 and Q10-12), call `getUserAnswer(1, ...)` → must return checkboxes for Q1-2 only

**F3 regression — over-selection bypass:**
- [ ] Programmatically check 4 boxes in a pickCount=3 group via DevTools console
- [ ] Call `checkAnswers()` → verify group score = 0, `overSelected: true`
- [ ] Verify results panel shows warning message
- [ ] Verify KC error rate counts all 3 as errors (not 1)

**F5 regression — group identity:**
- [ ] Verify `getGroupKey([8, 6, 7])` === `getGroupKey([6, 7, 8])` === `"6-7-8"`
- [ ] Verify no duplicate grading when 3 questions in same group iterate in checkAnswers

**Listening/Reading parity:**
- [ ] Verify listening template and reading template both have `case 'pick-from-list'`
- [ ] Verify both templates use identical `getGroupKey()`, `findGroupByQuestionNumber()`
- [ ] Verify both templates have `overSelected` handling in checkAnswers

### 7.3 Manual spot checks

Open 3 HTML files and verify:
- [ ] Pick-from-list groups render as checkboxes (not radio buttons)
- [ ] Pick N badge visible
- [ ] Can only select exactly N options (rest greyed out)
- [ ] Check answers — set comparison (order-independent)
- [ ] PIN reveal — correct/missed/extra labels highlighted correctly
- [ ] Results panel shows matched/missed/extra breakdown
- [ ] Over-selection warning appears when checking >N via DevTools

### 7.4 KC scoring smoke test

Take a sample student answer set (known correct/incorrect picks) → run through checkAnswers → verify:
- [ ] score matches expected
- [ ] KC error rate matches expected
- [ ] No NaN or division-by-zero
- [ ] Over-selected group contributes pickCount errors, not userPicks.length errors

### 7.5 Regression check

Run existing gapfill, form-completion, matching, and individual multiple-choice questions — verify no breakage.

---

## Rollback Plan

If something breaks:
1. `git checkout -- shared/listening/listening_cambridge-2.json` — revert JSON
2. Comment out `case 'pick-from-list'` in templates — fall through to default text input
3. Regenerate HTML — all circle-N questions become text inputs (degraded but functional)

---

## Files Changed Summary

| File | Change | Risk |
|------|--------|------|
| `shared/listening/listening_cambridge-2.json` | 17 circle-N → ~6 pick-from-list groups + answer keys | Medium |
| `shared/generate_test_html.py` | +1 canonical type, +1 count branch | Low |
| `listening-section.html` | +CSS, +renderPickFromList, +enforcePickLimit, +case, +getUserAnswer, +getAnswerKey, +checkAnswers, +revealAnswers, +displayResults | High |
| `reading-section.html` | Same changes as listening template | Medium |
| `ielts-json-init/SKILL.md` | +detection rules, +answer key parsing, +validation | Low |
| `ielts-teacher/SKILL.md` | +error patterns, +scoring rules, +qualitative feedback | Low |
