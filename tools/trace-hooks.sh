#!/bin/bash
# tools/trace-hooks.sh — PostToolUse hook for auto-trace.
#
# Installed as a PostToolUse hook in .claude/settings.local.json.
# Reads stdin JSON from Claude Code's hook protocol:
#   {tool_name, tool_input: {command, ...}, ...}
#
# On Bash commands containing "quality trace-emit":
#   1. Auto-validate the daily trace file
#   2. If --decision-type close, auto-generate weekly digest
#
# Silent exit = no effect on main conversation.
set -euo pipefail

# Read stdin once
INPUT=$(cat)

# Only process Bash tool calls
TOOL=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)
if [ "$TOOL" != "Bash" ]; then
  exit 0
fi

# Extract the command string
CMD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

# Check if this is a trace-emit command
if ! echo "$CMD" | grep -q "quality trace-emit"; then
  exit 0
fi

# ── Auto-validate the daily trace file ──
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TRACE_FILE="$PROJECT_DIR/.ielts/quality/traces/$(date +%Y-%m-%d).jsonl"

if [ -f "$TRACE_FILE" ]; then
  "$PROJECT_DIR/.venv/bin/python3" "$PROJECT_DIR/shared/ielts_cli.py" \
    quality trace-validate --file "$TRACE_FILE" >/dev/null 2>/dev/null || true
fi

# ── If close → auto-generate weekly digest ──
if echo "$CMD" | grep -q "close"; then
  "$PROJECT_DIR/.venv/bin/python3" "$PROJECT_DIR/shared/ielts_cli.py" \
    quality weekly-digest >/dev/null 2>/dev/null || true
fi

exit 0
