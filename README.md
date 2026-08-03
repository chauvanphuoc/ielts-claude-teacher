# IELTS Claude Teacher

> **Your personal AI IELTS coach — running inside Claude Code.**
>
> You just talk to your teacher. Claude handles everything else: it remembers your band scores, diagnoses your weak areas, builds your practice, grades your work, and plans your next session — from band 4.0 all the way to 9.0.

IELTS Claude Teacher is an open-source **Claude Code skill suite** that turns Claude into a data-driven IELTS tutor. It is not a chatbot that answers questions — it is a *teacher* that owns an entire teaching loop:

**Diagnose → Plan → Teach → Evaluate → Close**

Every session, the teacher reads your learning history from a local student profile, picks the *root-cause* skill you should work on (down to a specific Knowledge Component such as *"T/F/NG — confusing FALSE with NOT GIVEN"*), generates an authentic practice test, grades your answers, updates your mastery model, and suggests what to do next.

Built on top of real Cambridge IELTS materials, it ships with a file bridge server, self-contained HTML test templates, a JSON textbook pipeline, and a quality-control plane that continuously measures — and improves — the teaching itself.

---

## ✨ Features

- **🎓 A complete teaching loop (Phase 0–6)** — not a chat. Claude runs the full cycle: one-time first-session diagnostic → load context → diagnosis → lesson plan → teaching → evaluation → close.
- **🧠 Knowledge Component (KC) system** — IELTS is broken down into 28 measurable knowledge components (e.g. `kc-read-tfng`, `kc-listen-distractor`, `kc-write-lr`). Each has an error rate, spaced-repetition schedule, and dependency chain, so the teacher fixes *root causes*, not symptoms.
- **📊 Data-driven personalization** — a single local `student-profile.json` remembers every essay, test, and weak area across sessions. Claude knows who you are.
- **🗣️ Real practice, real feedback** — the File Bridge server (`localhost:8765`) serves self-contained HTML tests with embedded Cambridge audio, auto-scoring, and Azure Speech pronunciation assessment for Speaking.
- **📚 Authentic Cambridge materials** — a pipeline (`/init-textbook-{skill}`) converts textbook markdown into structured JSON, and `/create-test-html` generates PIN-protected section-level HTML tests you can even cross-check against the original PDF. Cambridge 1 test data is included under `shared/`.
- **📈 Self-improving teacher** — every teaching decision is traced, a weekly digest scores the teacher's quality (0–100 TQS), and periodic prompt-tuning suggests concrete `SKILL.md` improvements.
- **🔒 100% local & private** — all learner data lives in `.ielts/` at the project root. No cloud accounts, no telemetry, no data leaving your machine (except optional Azure Speech).

---

## Table of Contents

- [Quick start (vibe-code install)](#quick-start-vibe-code-install)
- [Manual installation](#manual-installation)
- [Usage](#usage)
  - [How to use — the golden rules](#how-to-use--the-golden-rules)
  - [Commands](#commands)
  - [What you can say](#what-you-can-say)
  - [Your first session](#your-first-session-diagnostic)
  - [A typical session](#a-typical-session)
  - [Practice by skill](#practice-by-skill)
  - [Full mock tests & cross-skill analysis](#full-mock-tests--cross-skill-analysis)
  - [Pre-test warnings](#pre-test-warnings)
  - [Progress & reports](#progress--reports)
  - [System health check](#system-health-check)
  - [Working with JSON and HTML tests](#working-with-json-and-html-tests)
- [How it works](#how-it-works)
- [Improving the teacher every week](#improving-the-teacher-every-week)
- [Project structure](#project-structure)
- [Configuration](#configuration)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

---

## Quick start (vibe-code install)

The fastest way to get started is to let Claude set everything up for you.

### Step 1: Install on your machine

Open Claude Code in your project directory and paste this. Claude does the rest.

> 💡 **Tip:** after pasting, switch to **auto mode** (Shift+Tab) so Claude can run the whole install without pausing to ask for permission on each step.
>
> ⚠️ **Note:** the install process **syncs the `skills/` folder with `.claude/`** so that Claude Code discovers the `/ielts-*` slash commands. This is step 1 in the prompt below. The symlinks are created under `.claude/` (which is gitignored), so they stay local to your machine and are never committed.

```
Install IELTS Claude Teacher: run

# 1. Sync the skills folder into .claude/ so the /ielts-* commands are discovered.
#    Symlinks are used so the skills stay in sync with the repo (copy instead on Windows).
mkdir -p .claude/skills
for d in skills/ielts-teacher skills/ielts-writing skills/ielts-reading \
         skills/ielts-listening skills/ielts-speaking \
         skills/ielts-json-init skills/ielts-test-html \
         skills/ielts-upgrade skills/developer-ielts-sys; do
  ln -sfn "$(pwd)/$d" ".claude/skills/$(basename "$d")"
done

# 2. Create the Python virtualenv and install the only required dependency
#    (Azure Speech SDK, used for Speaking pronunciation assessment).
python3 -m venv .venv
.venv/bin/pip install azure-cognitiveservices-speech

# 3. Initialize the local data directory and validate the install.
.venv/bin/python3 shared/ielts_cli.py init
.venv/bin/python3 shared/ielts_cli.py validate

# 4. Set up environment variables: copy the .env template, then fill in your keys.
#    The repo ships a template at .env.example — copy it so you don't lose the field names.
cp .env.example .env
#    Optional keys, edited in .env:
#      • Azure Speech (pronunciation assessment for Speaking) — free key at
#        https://speech.microsoft.com, then set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.
#      • LLM API (semantic checking of typed-answer questions) — any OpenAI-compatible
#        endpoint (OpenAI, DeepSeek…). Set LLM_API_URL, LLM_API_KEY, LLM_MODEL.
#    Everything is optional — the teacher runs fine with an empty .env.

# 5. Reply to the user: "✅ IELTS Claude Teacher is installed!
#    Start with /ielts-teacher — your first session runs a 20-question diagnostic."
```

Then add a `CLAUDE.md` section (or a short note) listing the available skills:

```markdown
## Skills

- `/ielts-teacher` — your personal AI IELTS coach (main entry point; start here)
- `/ielts-writing`, `/ielts-reading`, `/ielts-listening`, `/ielts-speaking` — per-skill coaches
- `/init-textbook-{skill}` — build JSON test data from a textbook
- `/create-test-html` — generate section-level HTML tests from JSON data
- `/ielts-upgrade` — safely upgrade IELTS Claude Teacher from GitHub
- `/developer-ielts-sys` — development mode for the IELTS system
```

> If you haven't cloned the repository yet, first run:
>
> ```bash
> git clone https://github.com/chauvanphuoc/ielts-claude-teacher.git
> cd ielts-claude-teacher
> ```
>
> Then paste the install prompt above.

### What happens next

Run `/ielts-teacher`. On your first session the teacher will:

1. Ask your **target band** and **exam date**;
2. Ask which skills you want to practice (all four, or skip Speaking);
3. Open a **20-question diagnostic test** (5 per skill) in your browser;
4. Grade it, build your initial KC mastery model, and present your strongest/weakest areas.

From then on, every session starts with Claude loading your profile and telling you exactly what to work on today.

---

## Manual installation

Prefer to do it yourself? Here are the exact steps.

### Requirements

| Requirement | Notes |
|-------------|-------|
| **Claude Code** | The CLI harness that runs the skills. Install from [docs.claude.com](https://docs.claude.com/en/docs/claude-code). |
| **Python 3.9+** | The File Bridge server is stdlib-only; the venv only exists for the Azure Speech SDK. |
| **A modern browser** | Safari/Chrome/Edge recommended (used for in-template speech recognition). |
| **Textbook materials** | Cambridge IELTS markdown + audio in `textbook/` (Cambridge 1 JSON test data is already included under `shared/`). |

### Setup

```bash
# 1. Get the code
git clone https://github.com/chauvanphuoc/ielts-claude-teacher.git
cd ielts-claude-teacher

# 2. Sync skills into .claude/ so Claude Code discovers /ielts-* commands
mkdir -p .claude/skills
for d in skills/ielts-teacher skills/ielts-writing skills/ielts-reading \
         skills/ielts-listening skills/ielts-speaking \
         skills/ielts-json-init skills/ielts-test-html; do
  ln -sfn "$PWD/$d" ".claude/skills/$(basename "$d")"
done

# 3. Python venv + the only pip dependency
python3 -m venv .venv
.venv/bin/pip install azure-cognitiveservices-speech

# 4. Initialize local data (.ielts/)
.venv/bin/python3 shared/ielts_cli.py init

# 5. Set up environment variables: copy the template, then fill in your keys.
#    The repo ships a template at .env.example — copy it so you don't lose the field names.
cp .env.example .env
#    Optional keys, edited in .env:
#      • Azure Speech (pronunciation assessment for Speaking) — free key at
#        https://speech.microsoft.com, then set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.
#      • LLM API (semantic checking of typed-answer questions) — any OpenAI-compatible
#        endpoint (OpenAI, DeepSeek…). Set LLM_API_URL, LLM_API_KEY, LLM_MODEL.
#    Everything is optional — the teacher runs fine with an empty .env. .env is gitignored.

# 6. Verify
.venv/bin/python3 shared/ielts_cli.py validate
```

> **⚠️ Important:** always run Python through `.venv/bin/python3`, never bare `python3`. The venv is the only thing that provides the Azure Speech SDK.

### Adding a new textbook

```bash
mkdir -p textbook/cambridge-2/textbook shared/reading/cambridge-2
cp ~/Downloads/cambridge-2/*.mp3        textbook/cambridge-2/
cp ~/Downloads/cambridge-2/textbook.md  textbook/cambridge-2/textbook/
```

Then ask Claude to build the JSON test data:

```
/init-textbook-reading   --source cambridge-2
/init-textbook-listening --source cambridge-2
/init-textbook-speaking  --source cambridge-2
/init-textbook-writing   --source cambridge-2
```

The File Bridge server auto-discovers new sources — no restart needed.

---

## Usage

### How to use — the golden rules

1. **You talk, Claude teaches.** The system is *pull-based*: Claude acts when you talk to it, and not otherwise. You never run scripts, never touch files, never think about "which command do I use."
2. **Talk naturally.** In Vietnamese, English, or Chinese — switch anytime with "đổi sang tiếng Anh" / "切换到中文". Test content is always in English.
3. **The teacher owns the loop.** Claude decides what to teach, when to grade, and what to do next — always justified by your data, and always open to your override.
4. **Don't end the session yourself — say when you're done.** The teacher keeps offering the next activity until you explicitly stop (e.g. "thôi", "nghỉ", "stop", "tạm biệt").
5. **No fabricated scores.** If the teacher can't grade fairly (e.g. the audio is missing), it will say so rather than invent a number.
6. **Your data stays local.** Everything lives in `.ielts/` at the project root. Back it up with `ielts_cli.py backup`.

### Commands

| Command | What it does |
|---------|--------------|
| `/ielts-teacher` | **Main entry point.** The personal AI coach. First run = diagnostic; afterwards it loads your profile and teaches. |
| `/ielts-listening` | Listening coach — section-by-section grading, error-type classification (spelling, numbers, distractors…), dictation drills. |
| `/ielts-reading` | Reading coach — question-by-question analysis, T/F/NG logic, synonym extraction. |
| `/ielts-speaking` | Speaking coach — Azure Speech pronunciation assessment + transcript content evaluation. |
| `/ielts-writing` | Writing coach — 4-dimension scoring (TR / CC / LR / GRA), sentence-level feedback, band-upgraded rewrite. |
| `/init-textbook-{reading\|listening\|speaking\|writing}` | Build structured JSON test data from a textbook's markdown. |
| `/create-test-html` | Generate PIN-protected, section-level HTML tests from the JSON data. |
| `/ielts-upgrade` | Safely pull the latest code from GitHub while preserving all learning data. |

### What you can say

You don't need to memorize commands — the teacher routes for you. Examples:

| You say | Claude does |
|---------|-------------|
| `học thôi` / `let's study` | Starts the teaching loop for today. |
| `chấm bài` / `grade my work` | Jumps to evaluation for the latest test. |
| `luyện nghe` / `luyện đọc` / `luyện nói` / `luyện viết` | Opens the right practice test for that skill. |
| `thi thử` / `mock test` | Generates a **Full Mock Test** — all 4 skills in one tabbed session. |
| `chấm bài full test` | Grades all 4 skills, runs cross-skill analysis, estimates an overall band. |
| `ôn từ vựng` / `vocab review` | Runs a spaced-repetition vocabulary review. |
| `xem tiến độ` / `progress` | Opens the progress dashboard (bands, weak KC radar, timeline). |
| `kiểm tra calibration` | Runs a Writing calibration exercise to detect scoring drift. |
| `tạo JSON cho Test 1` | Runs the textbook JSON pipeline. |
| `đổi sang tiếng Anh` / `切换到中文` | Switches the teacher's communication language. |

### Your first session (diagnostic)

> **Example transcript** (the teacher communicates in the language you set — English shown here):

```
You: /ielts-teacher

Teacher: Hi! Welcome to IELTS Claude Teacher.
  Before we start, I need to know a few things.
  🎯 What's your target band? (4.0 – 9.0)

You: 7.0

Teacher: 📅 Do you have an exam date? (YYYY-MM-DD, or skip)

You: 2026-12-15

Teacher: 📚 Which skills do you want to practice?
  A) All 4: Writing + Reading + Listening + Speaking
  B) Skip Speaking
  C) Custom

You: A

Teacher: ✅ Profile created!
  📊 Target: Band 7.0
  📅 156 days until your exam
  📚 Skills: Writing, Reading, Listening, Speaking

  Now let's run a 20-question diagnostic so I understand
  your current level. Ready?

[The diagnostic test opens in your browser — 5 questions per skill]
```

When you're done, say `chấm bài` / `grade my work`. The teacher grades it, builds your initial KC mastery model, and tells you your strongest and weakest areas.

### A typical session

```
You: /ielts-teacher

Teacher: Welcome back! 👋
  📊 Writing: 5.0 | Reading: 5.5 | Listening: 6.0 | Speaking: 5.5
  ⚠️ Top weak areas: T/F/NG (50% errors), Spelling (3 errors/test)
  📅 150 days left | 5 sessions completed

  Today we'll focus on T/F/NG — it has the highest error rate
  and it's blocking your inference skill.

  [Opens a 5-question T/F/NG mini test]

You: [does the test] Done — grade it for me.

Teacher: [reads your results, scores, updates KC mastery]

  📖 Score: 4/5 (80%)

  ✅ Q1, Q2, Q4, Q5 — correct
  ❌ Q3 — you chose NOT GIVEN, but the answer is FALSE.
     The passage says "X causes Y"; the statement says "X prevents Y".
     → FALSE, because the passage CONTRADICTS it directly.

  📊 kc-read-tfng: weak (50%) → ok (33%) 🎉
  🔄 Next review: in 3 days (2026-07-17)

  Next up: Spelling (Listening). Ready?
```

After every evaluation the teacher immediately offers the next activity and keeps teaching until *you* decide to stop.

### Practice by skill

#### Writing

```
You: Grade this essay for me

[Paste your essay]

Teacher: 📝 Essay assessment

  Task Response (TR):             5.5
  Coherence & Cohesion (CC):      5.0
  Lexical Resource (LR):          5.5
  Grammatical Range & Accuracy:   5.0

  📊 Overall: Band 5.0

  🔄 Upgraded to Band 6.5: [rewritten essay]

  💡 To reach Band 6.5:
  - TR: each paragraph needs one main idea + a concrete example
  - Learn 5 collocations on this topic
  - Practice complex sentences with "while", "although", "which"
```

Writing is graded on the official four dimensions (TR / CC / LR / GRA) with 0.5-band increments. A calibration system compares against pre-graded anchor essays so scores stay consistent over time.

#### Speaking

```
You: Let's practice speaking

Teacher: [Opens the Speaking template at localhost:8765/lessons/speaking-test.html]

  In the template:
  1. Navigate Part 1 / 2 / 3 — the cue card is shown
  2. Press Record and speak
  3. Your transcript appears in real time
  4. Press Submit

You: Grade my speaking

Teacher: 🎙️ Speaking assessment

  [Azure Speech assessment + transcript content evaluation]

  Fluency & Coherence:     5.5
  Lexical Resource:        5.0
  Grammatical Range:       5.5
  Pronunciation:           5.5 (Azure PronScore: 0.62)

  📊 Overall: Band 5.5

  Filler words: "um" (4×), "like" (3×) in 90 seconds
  💡 Try pausing instead of "um" — one silent second
     sounds more confident than a filler word
```

Speaking pairs Azure Speech pronunciation assessment with a transcript-based content evaluation, including filler-word analysis and per-word pronunciation feedback.

#### Reading — two modes

**Mode 1: Full Cambridge test (HTML template)**

```
You: Let's do Cambridge 1 Test 1 Reading

Teacher: [Opens the Reading template at localhost:8765/lessons/reading-test.html]

  Two-column layout: passage on the left, questions on the right.
  - Full passage text + illustrations
  - All question types: MC, T/F/NG, gap-fill, matching…
  - "Check Answers" to self-score
  - "Save & Ask Claude to Grade" to submit

You: Grade my reading

Teacher: 📖 Reading results
  Passage 1: 12/15 | Passage 2: 10/13 | Passage 3: 9/12
  📊 Total: 31/40 → Band 7.0
  ❌ T/F/NG (3 errors): Q18, Q21 — NOT GIVEN instead of FALSE
  🎯 Suggested practice: 5 T/F/NG questions from Test 2
```

**Mode 2: Conversation mode (no HTML needed)**

```
You: /ielts-reading — let's do test 1

Teacher: 📖 Reading Test 1 — Passage 1: A spark, a flint
  [Shows the passage text]
  Questions 1–5: choose words from the list to fill the gaps.
  Format: 1=preserve, 2=unaware, …

You: 1=preserve, 2=unaware, 3=chance, 4=friction, 5=rotating

Teacher: ✅ 5/5! Continue to Questions 6–8…
  [Continues through all 40 questions]
```

#### Listening

```
You: Let's do Cambridge 1 Test 1 Listening

Teacher: [Opens the Listening template]

  In the template:
  1. Navigate Sections 1–4
  2. Audio player loads the correct MP3 per section
  3. Answer MC, gap-fill, form-completion, matching
  4. Submit → saved to .ielts/listening/latest.json

You: Grade my listening

Teacher: 🎧 Listening results
  Section 1: 8/10 | Section 2: 6/10 | Section 3: 5/10 | Section 4: 4/10
  📊 Total: 23/40 → Band 6.0

  ❌ Spelling (3 errors): accomodation → accommodation, goverment → government
  ❌ Numbers (2 errors): 15 → 50, £16.50 → £60.50
  ❌ Distractor (2 errors): Q5, Q7 — chose the first answer before the speaker corrected it

  🎯 Practice: shadow Section 2 + spell the 20 most commonly misspelled IELTS words
```

### Full mock tests & cross-skill analysis

**Full Mock Test (all 4 skills).** Say `thi thử` / `mock test`. The teacher generates a single tabbed test (Reading | Listening | Speaking | Writing), you complete each tab and submit, then say `chấm bài full test` for a comprehensive band estimate.

**Cross-skill analysis.** After every evaluation, the teacher scans all four skills for *shared root causes*:

```
You: Analyze my weak areas

Teacher: 🧠 Cross-skill analysis

  Pattern found: DIFFICULTY DISTINGUISHING IMPLIED VS STATED

  Reading T/F/NG:    50% errors — NOT GIVEN instead of FALSE
  Listening MC:      60% distractor errors — picking the first answer

  → Root cause: you select an answer when information is IMPLIED
    but not STATED directly.

  📝 Fixes that help BOTH skills:
  1. When reading, mark "Direct" vs "Implied" in the passage
  2. When listening, write down what the speaker says before and after correcting
  3. Do 5 T/F/NG questions — explain exactly which statement contradicts
```

### Pre-test warnings

Before you take a Cambridge test, the teacher warns you about traps it can predict from your history:

```
You: I'm about to do Cambridge 1 Test 2

Teacher: ⚠️ Before you start:

  Section 3 Q17–20 (Multiple Choice):
  → The speaker corrects themselves mid-sentence. DON'T pick the first answer.

  Section 1 Q5 (Form Completion):
  → Spelling trap: "accommodation" — you've missed it twice.

  Reading Passage 2:
  → 3 T/F/NG questions. Remember: FALSE = the passage says the OPPOSITE.
    NOT GIVEN = the passage doesn't mention it.

  Ready?
```

### Progress & reports

```
You: Show my progress

Teacher: [Opens the progress dashboard]

📊 IELTS roadmap — 150 days left
  Writing:   ████████░░░░░░░░░░ Band 5.0 → Target 7.0
  Reading:   █████████░░░░░░░░░ Band 5.5 → Target 7.0
  Listening: ████████░░░░░░░░░░ Band 6.0 → Target 7.0
  Speaking:  █████████░░░░░░░░░ Band 5.5 → Target 7.0

  ⚠️ Top weak areas:
  - T/F/NG Reading (50% errors) → kc-read-tfng
  - Spelling Listening (3 errors/test) → kc-listen-spelling
  - Task Response Writing → kc-write-tr

  📅 Suggested practice today:
  1. 30 min: T/F/NG + implied vs stated
  2. 20 min: spell the 20 most commonly misspelled IELTS words
  3. 40 min: write one Task 2 essay, focusing on Task Response
```

### System health check

Ask the teacher to verify the whole setup, or run it yourself:

```bash
.venv/bin/python3 shared/ielts_cli.py validate   # integrity check of all data files
.venv/bin/python3 shared/ielts_cli.py status     # one-line status summary
```

The check covers Python + venv, the CLI, the data directory, the student profile, the KC graph, the templates, the File Bridge server, and the JSON test data.

### Working with JSON and HTML tests

The pipeline that powers the tests is fully controllable from the chat:

```
You: /create-test-html --skill listening --section-key cambridge-1_test-1_section-1

Teacher: ✅ Generated: .ielts/test-html/cambridge-1_listening_test-1_section-1.html
  📋 10 questions rendered (matches JSON: 10)
  🔒 Answers locked behind PIN (default: 1234567890)
  🔑 Teacher bypass: Ctrl+Shift+U
  📂 Open: open .ielts/test-html/cambridge-1_listening_test-1_section-1.html
  🌐 Serve: http://localhost:8765/test-html/cambridge-1_listening_test-1_section-1.html
```

**Generate everything for one book:**

```
You: /create-test-html --source cambridge-1 --all-skills --force

Teacher: 27 files generated across all skills
  (listening: 4 · reading: 3 · speaking: 12 · writing: 8)
```

**Cross-check JSON against the original PDF:**

1. Open the generated HTML next to the PDF.
2. Press `Ctrl+Shift+U` and enter the PIN to reveal answers.
3. Compare each question + answer with the PDF.
4. If you find an error, fix the JSON source and re-run `/create-test-html --force`.

> Note: Listening files must be opened via the server (`http://localhost:8765/test-html/...`) for audio to work. Reading/Speaking/Writing files can be opened directly.

---

## How it works

### The teaching loop (Phase 0–6)

Every interaction flows through the same loop. Claude decides which phase to enter based on what you say and what your profile shows. **Phase 0 is a one-time first-session diagnostic; Phases 1–6 form the recurring loop:**

```
        ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
        │ PHASE 0 │───▶│ PHASE 1 │───▶│ PHASE 2 │───▶│ PHASE 3 │
        │ First   │     │ Load    │     │ Diagnose│     │ Plan    │
        │ Session │     │ Context │     │         │     │         │
        └─────────┘     └─────────┘     └─────────┘     └────┬────┘
                                                              │
        ┌─────────┐     ┌─────────┐     ┌────────────────────┘
        │ PHASE 6 │◀───│ PHASE 5 │◀───│ PHASE 4
        │ Close   │     │ Evaluate│     │ Teach
        └─────────┘     └─────────┘     └──────────────────────┘
```

- **Phase 0 — First Session:** welcome, target band + exam date, 20-question diagnostic (5 per skill), initial KC mastery.
- **Phase 1 — Load Context:** validates data integrity and loads `student-profile.json`, the KC graph, and settings. Shows a welcome summary (bands, top weak KCs, days to exam).
- **Phase 2 — Diagnose:** scans spaced-repetition due reviews, weak KCs, vocab/grammar, and coach notes, then runs a **priority algorithm** that resolves dependency chains to find the *root-cause* KC.
- **Phase 3 — Plan:** decides mini-test (focused KC drill) vs. authentic test-html, reuses or creates a lesson, and applies guardrails (max 3 new lessons/session).
- **Phase 4 — Teach:** brief theory (3–4 sentences max), then opens the test via the File Bridge server. Real learning = doing.
- **Phase 5 — Evaluate:** reads results, grades each question, updates KC mastery with a cumulative error rate + spaced-repetition schedule, archives results, and checks for escalation (3 fails on the same KC → change approach).
- **Phase 6 — Close:** summarizes the session and suggests the next focus — but only after *you* say you're done.

### The Knowledge Component system

Instead of saying *"your reading is weak"*, the teacher says *"you struggle to distinguish FALSE from NOT GIVEN."* IELTS is decomposed into **28 Knowledge Components** across the four skills:

| Skill | Example KCs |
|-------|-------------|
| Reading | `kc-read-tfng`, `kc-read-inference`, `kc-read-mc`, `kc-read-gapfill`, `kc-read-matching` … |
| Listening | `kc-listen-spelling`, `kc-listen-numbers`, `kc-listen-distractor`, `kc-listen-map`, `kc-listen-inference` … |
| Writing | `kc-write-tr`, `kc-write-cc`, `kc-write-lr`, `kc-write-gra` (+ articles, tenses, complex sentences) |
| Speaking | `kc-speak-fluency`, `kc-speak-coherence`, `kc-speak-lexical`, `kc-speak-grammar`, `kc-speak-pronunciation` |

Each KC carries a **dependency chain** (e.g. T/F/NG depends on inference), a cumulative **error rate**, and a **spaced-repetition schedule** (review after 1 / 3 / 7 / 30 days). The priority algorithm in Phase 2 uses all of this to fix root causes instead of symptoms — and the cross-skill analyzer finds patterns like *"implied-vs-stated confusion"* that span Reading T/F/NG *and* Listening MC.

### Architecture at a glance

```
┌──────────────┐
│   STUDENT    │
│  (browser)   │
       │  you talk: "học thôi" / "grade my work" …
       ▼
┌────────────────────────────────────────┐
│            CLAUDE CODE                 │
│                                        │
│  ielts-teacher — 6-phase loop (0–6)    │
│    └─ sub-skills: writing · reading ·  │
│       listening · speaking             │
│                                        │
│  ┌──────────────────────────────┐      │
│  │  server.py :8765             │      │
│  │  serves HTML tests, audio,   │      │
│  │  POST /save → .ielts/{skill} │      │
│  └──────────────────────────────┘      │
└────────────────────────────────────────┘
       │  results auto-save
       ▼
┌────────────────────────────────────────────┐
│  .ielts/  (single source of truth)         │
│  student-profile.json · kc-graph-ielts.json│
│  lesson-library.json · quality/ · {skill}/ │
└────────────────────────────────────────────┘
```

The **File Bridge** (`skills/ielts-teacher/server.py`) is a stdlib-only HTTP server on `localhost:8765` that serves the HTML tests, the textbook audio/JSON, and receives submitted answers via `POST /save`. It binds to `127.0.0.1` only.

---

## Improving the teacher every week

The teacher measures itself and improves on a weekly cadence. Every teaching decision is automatically **traced** (`quality trace-emit`); at the end of the week, a **digest** scores overall teaching quality.

### The weekly loop

```bash
# 1. Start of week — check quality-plane phase status + review last week's digest
.venv/bin/python3 shared/ielts_cli.py quality phase-gate --action status
.venv/bin/python3 shared/ielts_cli.py quality weekly-digest --week 2026-W31

# 2. During the week — nothing to do. Each session auto-records 5-6 trace records.

# 3. End of week — review the digest and log the retrospective
.venv/bin/python3 shared/ielts_cli.py quality weekly-digest
.venv/bin/python3 shared/ielts_cli.py quality weekly-review-log \
  --week-key 2026-W31 --achieved "12 sessions, 65 traces" \
  --misses "listening KCs undertested" --risks "none" \
  --commitments "add listening gate set"

# 4. Keep the knowledge-transfer pack current
.venv/bin/python3 shared/ielts_cli.py quality kt-pack-update \
  --phase w3 --summary "weekly checkpoint complete"
```

### What the digest tells you

The weekly digest (`quality weekly-digest`) reports: total teaching decisions, trace completeness rate, distribution by skill/decision type, the top-10 most-tested KCs, and any malformed records. It also computes a **Teacher Quality Score (TQS, 0–100)** weighted across:

- **Calibration (30%)** — does the teacher's confidence match actual outcomes?
- **Completeness (25%)** — are all trace fields filled?
- **Follow-through (20%)** — do diagnoses lead to actual teaching?
- **Outcome evaluation (15%)** — are outcomes honestly evaluated at close?
- **Session hygiene (10%)** — are sessions closed properly?

### Making the teacher smarter

- **Prompt tuning (every 4 weeks)** — `quality prompt-tune --weeks 4` analyzes the traces and suggests concrete `SKILL.md` changes:
  ```bash
  .venv/bin/python3 shared/ielts_cli.py quality prompt-tune --weeks 4
  ```
- **Strategy A/B testing** — tag each lesson with a `--strategy` (e.g. `explicit-rule-first`, `discovery-learning`, `drill-practice`) and compare what works per KC:
  ```bash
  .venv/bin/python3 shared/ielts_cli.py quality strategy-compare --kc kc-read-tfng --weeks 8
  ```
- **Escalation detection** — if a KC shows no improvement after 3 attempts, the teacher switches methods (drill ↔ authentic test) instead of repeating the same approach.
- **Writing calibration** — a periodic calibration exercise re-scores anchor essays to detect scoring drift, keeping Writing grades consistent over time.

### Quality-plane phase gates

The quality control plane rolls out in phases (`w1` → `w4`): contracts → report-only guardrails → soft-gate → shadow lane & hard-gate readiness. Track and gate them with:

```bash
.venv/bin/python3 shared/ielts_cli.py quality phase-gate --action status
.venv/bin/python3 shared/ielts_cli.py quality phase-gate --action check --phase w3
.venv/bin/python3 shared/ielts_cli.py quality phase-gate --action complete --phase w1 --owner you --note "contracts done"
```

---

## Project structure

```
ielts-claude-teacher/
├── CLAUDE.md                     # Claude Code project instructions
├── README.md                     # This file
├── readme-ielts-system.md        # Full system documentation (deep dive, v2.1.0)
│
├── .claude/
│   └── skills/                   # Symlinks → skills/ (created by the install step; local only)
│
├── skills/
│   ├── ielts-teacher/            # Main teacher — the 6-phase loop (Phase 0–6)
│   │   ├── SKILL.md              #   main teacher prompt + phases/ loaded on demand
│   │   ├── phases/               #   on-demand workflows (evaluate-*, calibrate, vocab-review)
│   │   ├── server.py             #   File Bridge HTTP server (:8765)
│   │   ├── pronounce_cli.py      #   Azure Speech pronunciation CLI
│   │   └── templates/            #   reading/listening/speaking/writing/mini/
│   │                             #   diagnostic/full-test/progress-dashboard HTML
│   ├── ielts-writing/            # Writing coach (TR/CC/LR/GRA)
│   ├── ielts-reading/            # Reading coach
│   ├── ielts-listening/          # Listening coach
│   ├── ielts-speaking/           # Speaking coach (Azure Speech)
│   ├── ielts-json-init/          # Textbook markdown → JSON pipeline
│   └── ielts-test-html/          # JSON → section HTML test generator
│
├── shared/
│   ├── ielts_cli.py              # Data management CLI (init, validate, backup, quality…)
│   ├── generate_test_html.py     # Section HTML generator
│   ├── rubrics.md                # Official IELTS band descriptors (0.5 increments)
│   ├── reading/                  # Reading JSON test data (per-test)
│   ├── listening/                # Listening JSON test data (per-source)
│   ├── speaking/                 # Speaking JSON test data
│   └── writing/                  # Writing JSON test data
│
├── textbook/                     # Raw textbook materials (markdown + audio, gitignored)
├── tests/                        # Unit + E2E tests (27 HTML-generator tests + others)
├── evals/                        # GEval-based pedagogical quality evaluations
├── docs/                         # Reference documentation (gitignored)
└── .ielts/                       # ⚠️ Learner data — LOCAL, keep out of version control
    ├── student-profile.json      #   ⭐ single source of truth
    ├── kc-graph-ielts.json       #   KC taxonomy (28 KCs)
    ├── lesson-library.json       #   lesson index (survives profile resets)
    ├── settings.json             #   language + personality
    ├── {skill}/latest.json       #   latest test results (speaking: index.json + archive/)
    └── quality/                  #   traces, evals, gates, weekly digests
```

> **Privacy note:** `.ielts/` holds personal learner data. Make sure it stays **out of any public repository** (add `.ielts/*` to `.gitignore` if it isn't already).

---

## Configuration

| Setting | Where | Description |
|---------|-------|-------------|
| Teacher language | `.ielts/settings.json` → `language` | `vi` (default), `en`, `zh` |
| Azure Speech | `.env` → `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Enables pronunciation assessment for Speaking |
| LLM API | `.env` → `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL` | Semantic checking for typed-answer questions (OpenAI, DeepSeek…) |
| Permissions / hooks | `.claude/settings.local.json` | Claude Code allow-lists (e.g. `.venv/bin/python3 *`, `open http://localhost:8765/*`) |

---

## FAQ

**Does Claude hear audio?** No. Speaking is graded from the transcript (browser speech recognition) plus Azure Speech for pronunciation. Listening is graded from your typed answers.

**Is my data private?** Yes. Everything lives locally in `.ielts/`. Only Claude Code and the local bridge server touch it. Optional Azure Speech sends your speaking audio to Microsoft's API.

**Do I need internet?** Claude Code and (optionally) Azure Speech need it. The HTML templates themselves run offline with no CDN.

**How do I add another student?** The system is designed for one student per project. Use a separate profile or project directory per student.

**Can I skip Speaking?** Yes — choose that option during the first-session setup; Speaking disappears from your roadmap.

**How do I back up my data?** Run `.venv/bin/python3 shared/ielts_cli.py backup` to create a zip of everything in `.ielts/`.

---

## Contributing

Contributions are welcome! The most valuable ways to help:

- **Add textbook data** — drop a new Cambridge book into `textbook/` and run the JSON pipeline.
- **Improve the teacher** — run `quality prompt-tune`, apply its suggestions to `SKILL.md`, and open a PR.
- **Fix or extend the generators** — `ielts_cli.py` and `generate_test_html.py` are pure stdlib Python with a test suite (`tests/`).
- **Report issues** — scoring bugs, template rendering bugs, or pedagogy problems you notice during use.

Please keep changes aligned with the existing structure: skills live in `skills/`, shared Python in `shared/`, and learner data is never committed.

1. Fork the repo and create a branch: `git checkout -b feat/my-change`
2. Make your change and add/update tests.
3. Open a pull request with a clear description of what and why.

---

## License

MIT. Free forever. Go build something. See [LICENSE](LICENSE).

---

*Built with deepseek-v4-pro & deepseek-v4-flash. Inspired by the vibe-code install pattern from [gstack](https://github.com/garrytan/gstack).*
