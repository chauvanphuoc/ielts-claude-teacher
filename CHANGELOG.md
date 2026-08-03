# Changelog

Tất cả thay đổi đáng chú ý của IELTS Claude Teacher được ghi lại tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
và project này tuân theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---
## [Unreleased]

---

## [2.3.2] - 2026-08-03

### Added

- `.claude/plans/` — implementation plans (pick-from-list)
- `.claude/projects/memory/` — project memory (precise-html-generation)

### Changed

- `.claude/settings.local.json` — updated permissions and hooks config

---

## [2.3.1] - 2026-08-03

### Fixed

- `.gitignore` blanket ignore `.claude` → chỉ ignore `.claude/skills/` (symlink)
- Track được `.claude/hooks/` và `.claude/settings.local.json` lên GitHub

---

## [2.3.0] - 2026-08-03

### Added
- `/ielts-upgrade` slash command for safe GitHub upgrades — preserves all learning data while pulling latest code

---

## [2.2.0] - 2026-08-03

### Added
- Web-enhanced mini test creation with hybrid fetch strategy (Phase 3.3.1)
- TheConversation.com: full article text via WebFetch for authentic academic passages
- Aeon.co: detailed article summaries via WebSearch (bypasses Cloudflare 429)
- New `phases/web-research.md` — detailed web research playbook with KC→Source mapping
- `{{SOURCE_ATTRIBUTION_HTML}}` placeholder in mini-test.html template
- Source attribution CSS for web-sourced content
- Web research guardrails: max 2 WebFetch + 2 WebSearch per mini-test

### Changed
- SKILL.md Phase 3.3 restructured into 4 sub-sections (3.3.0–3.3.3)
- Content source priority: web research → Cambridge JSON → Claude knowledge
- Lesson library `--source` field: `web` for web-sourced, `generated` for fallback
- SKILL.md version bumped 2.1.0 → 2.2.0

### Fixed
- T/F/NG question fidelity: every answer key must trace to source text

---

## [2.1.0] - 2026-07-27

### Added
- Quality improvement loop (v3): Teacher Quality Score (TQS), prompt tuning, strategy A/B testing
- Trace enforcement (v2): closed-loop session recording with teacher transcript capture
- Session lifecycle rule: never end a session proactively
- CODE BOUNDARY blocks translated from Vietnamese to English

### Changed
- All evaluate-*.md phase files updated with testHtmlUrl context loading patterns
- `latest.json` now includes `testHtmlUrl` for full passage context during grading

### Fixed
- Progress dashboard crash on string scores + calendar coverage

---

## [2.0.0] - 2026-07-13

### Added
- IELTS Claude Teacher v2: autonomous AI IELTS coach
- 6-phase teaching loop: diagnose → plan → teach → evaluate → close
- 28-KC taxonomy (`.ielts/kc-graph-ielts.json`) with `commonErrors` and `exerciseTemplates`
- Priority algorithm for KC selection (reverse deps + chain boost + SRS bonus)
- Mini test system with self-contained HTML template
- Cambridge test-html integration (Reading, Listening, Speaking, Writing)
- Full Mock Test (4-tabbed HTML with cross-skill analysis)
- Lesson library (`.ielts/lesson-library.json`) with reuse tracking
- Student profile (`.ielts/student-profile.json`) with SRS vocabulary/grammar
- File Bridge server (`server.py`) on port 8765
- Azure Speech pronunciation assessment for Speaking
- Progress dashboard (`templates/progress-dashboard.html`)

---

## Phiên bản đầu tiên (trước 2.0.0)

Các phiên bản trước 2.0.0 chưa được ghi lại trong changelog này.
