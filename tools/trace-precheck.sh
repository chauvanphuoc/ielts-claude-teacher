#!/bin/bash
# tools/trace-precheck.sh — PreToolUse hook for trace checklist validation.
#
# Installed as a PreToolUse hook in .claude/settings.local.json.
# Reads stdin JSON from Claude Code's hook protocol:
#   {tool_name, tool_input: {command, ...}, ...}
#
# On Bash commands containing "trace-emit" with "--decision-type close":
#   Checks that all 4 required phases (diagnose, plan, teach, evaluate)
#   have trace records for today's session.
#
# Outputs warnings to stderr (visible to the agent) when phases are missing.
# Always exits 0 — never blocks the main conversation.
set -euo pipefail

INPUT=$(cat)

TOOL=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)
if [ "$TOOL" != "Bash" ]; then
  exit 0
fi

CMD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

# Only intercept trace-emit --decision-type close (or close-like patterns)
if ! echo "$CMD" | grep -q "trace-emit"; then
  exit 0
fi
if ! echo "$CMD" | grep -qE "\-\-decision-type[= ]+close"; then
  exit 0
fi

# Extract run-id from command (optional — default to today's session)
RUN_ID=$(echo "$CMD" | sed -nE 's/.*--run-id[= ]+([^ ]+).*/\1/p' | head -1)
if [ -z "$RUN_ID" ]; then
  RUN_ID="session-$(date +%Y-%m-%d)"
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TRACE_FILE="$PROJECT_DIR/.ielts/quality/traces/$(date +%Y-%m-%d).jsonl"

# ── Check which phases have been traced today ──
REQUIRED_PHASES=("diagnose" "plan" "teach" "evaluate")
MISSING=()

if [ -f "$TRACE_FILE" ]; then
  for phase in "${REQUIRED_PHASES[@]}"; do
    if ! grep -q "\"decisionType\": \"$phase\"" "$TRACE_FILE" 2>/dev/null; then
      MISSING+=("$phase")
    fi
  done
else
  MISSING=("${REQUIRED_PHASES[@]}")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "⚠️  [trace-precheck] Missing phase traces before close: ${MISSING[*]}" >&2
  echo "   Expected: diagnose → plan → teach → evaluate → close" >&2
  echo "   Emit missing traces before closing, or the session will be incomplete in the weekly review." >&2
else
  echo "✅ [trace-precheck] All 4 phases traced — ready to close." >&2
fi

exit 0
