# Commands Reference

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

```bash
# Data management
.venv/bin/python3 shared/ielts_cli.py init              # Initialize .ielts/
.venv/bin/python3 shared/ielts_cli.py migrate-profile   # Create student-profile.json v2
.venv/bin/python3 shared/ielts_cli.py validate          # Check data integrity
.venv/bin/python3 shared/ielts_cli.py settings get      # Read settings
.venv/bin/python3 shared/ielts_cli.py settings set --language en  # Change language
.venv/bin/python3 shared/ielts_cli.py status            # Brief status
.venv/bin/python3 shared/ielts_cli.py backup            # Create zip backup

# Coach memory
.venv/bin/python3 shared/ielts_cli.py memory add --content "..." --category observation --skill reading --priority high

# Lesson library
.venv/bin/python3 shared/ielts_cli.py lesson-library list
.venv/bin/python3 shared/ielts_cli.py lesson-library sync
.venv/bin/python3 shared/ielts_cli.py lesson-library add --id "..." --title "..." --skill reading --file ".ielts/lesson-plans/..." --kc-tags "kc-read-tfng"
.venv/bin/python3 shared/ielts_cli.py lesson-library mark-used --id "..."

# Profile reset
.venv/bin/python3 shared/ielts_cli.py reset-profile --yes
.venv/bin/python3 shared/ielts_cli.py reset-profile --yes --target-band 6.5  # preserve target band

# Full Mock Test (4 skills in tabs)
.venv/bin/python3 shared/ielts_cli.py create-full-test --random
open http://localhost:8765/test-html/$(ls -t .ielts/test-html/full-test_*.html | head -1 | xargs basename)

# Server (required for all HTML tests)
.venv/bin/python3 skills/ielts-teacher/server.py &

# Speaking evaluation
.venv/bin/python3 skills/ielts-teacher/pronounce_cli.py --audio .ielts/speaking/latest.webm --json
```
