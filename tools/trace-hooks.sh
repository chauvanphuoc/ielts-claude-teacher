#!/bin/bash
# tools/trace-hooks.sh — PostToolUse hook for auto-trace + GEval.
#
# Installed as a PostToolUse hook in .claude/settings.local.json.
# Reads stdin JSON from Claude Code's hook protocol:
#   {tool_name, tool_input: {command, ...}, ...}
#
# On Bash commands containing "quality trace-emit":
#   1. Auto-validate the daily trace file
#   2. If --decision-type close:
#      a. Auto-generate weekly digest (TQS completeness/calibration)
#      b. Run GEval pedagogical quality scoring (async, best-effort)
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

# ── If close → weekly digest + GEval scoring ──
if echo "$CMD" | grep -q "close"; then
  # Weekly digest (completeness/calibration TQS)
  "$PROJECT_DIR/.venv/bin/python3" "$PROJECT_DIR/shared/ielts_cli.py" \
    quality weekly-digest >/dev/null 2>/dev/null || true

  # Extract runId from the command
  RUN_ID=$(echo "$CMD" | grep -oP '(?<=--run-id )[^ ]+' || echo "")

  # GEval pedagogical scoring (best-effort, sync — ~20s for 3 phases)
  if [ -n "$RUN_ID" ]; then
    "$PROJECT_DIR/.venv/bin/python3" "$PROJECT_DIR/evals/eval_teacher.py" \
      --run-id "$RUN_ID" >/dev/null 2>/dev/null || true
  fi
fi

exit 0
