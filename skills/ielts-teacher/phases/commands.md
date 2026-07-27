# Commands Reference

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

# HTML Studio (full Cambridge tests)
.venv/bin/python3 skills/ielts-teacher/server.py &
open http://localhost:8765/ielts-studio.html

# Speaking evaluation
.venv/bin/python3 skills/ielts-teacher/pronounce_cli.py --audio .ielts/speaking/latest.webm --json
```
