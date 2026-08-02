# Reset Student Profile

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
