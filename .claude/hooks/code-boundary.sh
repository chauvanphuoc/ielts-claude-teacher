#!/usr/bin/env bash
# Code boundary hook (PreToolUse)
# Blocks Read/Edit/Write on *.py and *.js unless .ielts/dev-mode.active exists
# (created by the /developer-ielts-sys skill). CSS/HTML/templates are NOT blocked.
# Exit 2 = block the tool call; stderr shown to the user.

set -uo pipefail

INPUT=$(cat)

TOOL_NAME=$(printf '%s' "$INPUT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_name",""))' 2>/dev/null || true)
FILE_PATH=$(printf '%s' "$INPUT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)

# Only guard the relevant tools
case "$TOOL_NAME" in
  Read|Edit|Write|MultiEdit|NotebookEdit) ;;
  *) exit 0 ;;
esac

# Only code files matter
case "$FILE_PATH" in
  *.py|*.js) ;;
  *) exit 0 ;;
esac

# Dev mode unlock (marker created by /developer-ielts-sys)
for dir in "${CLAUDE_PROJECT_DIR:-}" "$PWD"; do
  if [ -n "$dir" ] && [ -f "$dir/.ielts/dev-mode.active" ]; then
    exit 0
  fi
done

echo "🚫 Code boundary: không được đọc/sửa file code (.py/.js) khi chạy skill ielts-*. Chạy /developer-ielts-sys để mở khóa." >&2
exit 2
