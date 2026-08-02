---
name: developer-ielts-sys
description: |
  Development mode for the IELTS system. THE ONLY command allowed to read and
  edit code (shared/*.py, skills/ielts-teacher/server.py, templates/, JS/CSS).
  All ielts-* skills are code-blind; use this to develop, fix bugs, add CLI
  commands. Usage: /developer-ielts-sys <task>
metadata:
  version: 1.0.0
---

# Developer Mode — IELTS System Code

You are the maintenance channel for the IELTS teaching system. Every `ielts-*` skill is **code-blind** (see CODE BOUNDARY in those SKILL.md files). This is the ONLY command that may read and edit code files: `.py`, `.js`, `.css`, `templates/**`, `server.py`, `ielts_cli.py`, `generate_test_html.py`, `pronounce_cli.py`, `extract_listening.py`.

---

## STEP 0 — UNLOCK CODE ACCESS (bắt buộc, làm NGAY ĐẦU)

```bash
touch .ielts/dev-mode.active
```

The PreToolUse hook (`code-boundary.sh`) blocks Read/Edit/Write on `.py`/`.js` unless this marker exists. Without it, every code tool call will be rejected. After finishing, offer to clean up:

```bash
rm .ielts/dev-mode.active
```

---

## REPO MAP — where the code lives

| Path | Purpose |
|------|---------|
| `shared/ielts_cli.py` | Main CLI — data mgmt, memory, lesson-library, quality traces, create-full-test |
| `shared/generate_test_html.py` | Renders section-level test HTML from JSON (used by /create-test-html) |
| `shared/listening/extract_listening.py` | Listening JSON validation script (run by /init-textbook-listening) |
| `skills/ielts-teacher/server.py` | File Bridge server (port 8765) — serves lessons/test-html, saves results |
| `skills/ielts-teacher/pronounce_cli.py` | Azure Speech pronunciation assessment (speaking) |
| `skills/ielts-teacher/ielts-studio.*` | Legacy studio (html/css/js) |
| `skills/ielts-teacher/templates/**` | Test templates: full/mock/mini/diagnostic + section-templates + shared/base-test.js |
| `skills/ielts-teacher/phases/*.md` | Workflow docs (code-blind skills read these; edit with care) |

---

## DEVELOPMENT CHECKLIST

1. **Understand the task** — read the relevant code + the SKILL.md contract it serves.
2. **Make the change** — code only; data files (`.ielts/**`, `shared/**/*.json`) should stay untouched unless the task explicitly requires it.
3. **Validate:**
   ```bash
   .venv/bin/python3 shared/ielts_cli.py validate
   ```
   Run a smoke test of the affected flow (e.g., generate one test-html, run one CLI command).
4. **Report** — what changed, what was tested, and remind the user dev mode is active (`rm .ielts/dev-mode.active` khi xong).

---

## RULE BẮT BUỘC — chống drift contract (quan trọng)

Các SKILL.md của skill ielts-* chứa **API contract** mà agent code-blind dựa vào để làm việc mà không cần đọc code (vd: question JSON schema tại `skills/ielts-teacher/SKILL.md` Phase 3.3, placeholder list). Mỗi lần bạn đổi:

- template HTML/JS (`templates/**`, `base-test.js`) — **phải cập nhật contract JSON tương ứng trong SKILL.md** (schema, placeholders, common mistakes).
- CLI arguments (`ielts_cli.py`) — phải cập nhật các lệnh được ghi trong SKILL.md / `phases/commands.md`.

Nếu không, agent code-blind sẽ render sai và không thể tự phát hiện (vì cấm đọc `.js`).

---

## GUARDRAILS

- **Không sửa data học sinh** (`.ielts/student-profile.json`, `.ielts/{skill}/latest.json`, …) trừ khi user yêu cầu rõ.
- **Không xóa file trong `textbook/`** — dữ liệu gốc Cambridge.
- Lỗi runtime → sửa code + validate + smoke test trước khi báo "xong".
