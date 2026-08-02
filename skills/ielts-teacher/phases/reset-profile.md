# Reset Student Profile

## CODE BOUNDARY (invariant)

- Agent MAY READ data: `.ielts/**`, `shared/**/*.json`, `shared/**/*.md`,
  `textbook/**/*.md`, `phases/*.md`.
- Agent MAY READ for rendering/grading: `*.html`, `*.css`, `templates/**`
  (reading HTML to render tests or evaluate answers — system workflow, kept intact).
- Agent MUST NOT READ code: all `.py`, `.js`, `server.py`, `ielts_cli.py`,
  `generate_test_html.py`, `pronounce_cli.py`, `extract_listening.py`.
  Code is a black box — only run via CLI commands documented in this SKILL.
- Agent MUST NOT EDIT: any code file (especially `.py` and `.js`). Code errors
  → report the error + invite user to run `/developer-ielts-sys`.
- Missing CLI/renderer → report to user, DO NOT craft HTML/JS by hand.
- Data that MAY be edited: `.ielts/**`, `shared/**/*.json`, `textbook/**/*.md`.

---

Trigger: student says "reset profile", "xóa profile", "bắt đầu lại", "reset student profile", or `/reset-student-profile`.

**This is a one-way door.** The profile is backed up but the active state is destroyed. Always confirm before executing.

## Confirmation Flow

1. Tell the student what will happen:
   - "Tôi sẽ: (1) backup student-profile.json hiện tại vào .ielts/backup/, (2) xóa toàn bộ dữ liệu học tập — test history, KC mastery, vocabulary, grammar, coach notes, (3) tạo profile mới với tất cả KCs ở trạng thái ban đầu, (4) dọn các file tạm. **Bài giảng trong lesson library được giữ nguyên.** Không thể undo — chỉ có thể restore thủ công từ backup."
2. Ask: "Bạn có chắc muốn reset không? Gõ 'có' hoặc 'yes' để xác nhận."
3. **Wait for explicit confirmation.** If the student says anything other than a clear yes, abort.
4. If confirmed, execute:
   ```bash
   .venv/bin/python3 shared/ielts_cli.py reset-profile --yes
   ```
5. Report results:
   - Backup location
   - Number of KCs reset (28)
   - Legacy files cleaned (7)
   - Transient files cleared
   - Lesson library preserved (N lessons)
   - "Diagnostic test sẽ chạy lại vào buổi học sau."
6. **Note:** If student wants to keep their target band, pass `--target-band <band>`. The reset preserves the current target band by default.

## Restore from Backup

If the student regrets the reset, they can restore manually:
```bash
cp .ielts/backup/student-profile-{timestamp}.json .ielts/student-profile.json
```
Tell them the exact backup filename from the reset output.
