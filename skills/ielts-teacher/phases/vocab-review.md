# Vocabulary SRS Review Session

Triggered when student says "ôn từ vựng", "vocab review", OR when teacher Phase 2 detects >= 5 words with `nextReviewDate <= today`.

---

## Step 1 — Load due words

Read `.ielts/student-profile.json` → `vocabulary.words`. Filter words where `nextReviewDate <= today` (or `level == "new"`).

If < 3 words due: "Bạn chưa có từ nào cần ôn hôm nay. Tôi sẽ lấy thêm vài từ mới học gần đây."

Target: 5-7 words per session.

---

## Step 2 — Present words in batches

For each word, present:

```
📝 Từ: _______ (hint: context gốc)
   Context: [listening Q1 — booking form]
   Bạn đã sai [errorCount] lần. Đây là lần ôn thứ [attempts + 1].
```

Student types the word.

---

## Step 3 — Check and update

**If correct:**
```
✅ Đúng! "accommodation"
   → vocab review --word "accomodation" --passed true
```

**If wrong:**
```
❌ Chưa đúng. Đáp án: "accommodation"
   → vocab review --word "accomodation" --passed false
   Từ này sẽ được ôn lại vào ngày mai.
```

---

## Step 4 — Context recall (bonus round)

For words at `level >= "learning"`: give the original context, ask student to recall the word without seeing it.

```
📝 Bạn đã viết sai từ này trong bài Listening, câu hỏi về "booking form".
   Đó là từ gì?
   → "accommodation"
```

---

## Step 5 — Summary

```
📊 Kết quả ôn tập từ vựng:
   ✅ Đúng: [n]/[total]
   📝 Từ đã mastered: [list]
   🔄 Từ cần ôn lại: [list với nextReviewDate mới]
   📅 Buổi ôn tập tiếp theo: [earliest nextReviewDate]
```

Update `lastVocabReview`:
```bash
.venv/bin/python3 shared/ielts_cli.py vocab review --word "..." --passed true
```
(This automatically updates lastVocabReview in profile.)

---

## Step 6 — Coach note

```bash
.venv/bin/python3 shared/ielts_cli.py memory add \
  --content "Vocab review: ${correct}/${total} correct. ${mastered} mastered. Next review: ${earliestDate}." \
  --category observation \
  --skill general \
  --priority low
```
