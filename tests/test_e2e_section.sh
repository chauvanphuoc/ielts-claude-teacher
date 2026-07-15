#!/bin/bash
# E2E test for section HTML generation pipeline.
# Tests: single generation, batch generation, --force overwrite, --all-skills.
# Usage: bash tests/test_e2e_section.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

PASS=0
FAIL=0
GEN_SCRIPT="shared/generate_test_html.py"
OUT_DIR=".ielts/test-html"

pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1 — $2"; FAIL=$((FAIL + 1)); }

echo "=== E2E Section HTML Tests ==="
echo ""

# ── Flow 1: Generate 1 section ──
echo "-- Flow 1: Single section generation --"

# Clean any existing file
rm -f "$OUT_DIR/cambridge-1_listening_test-1_section-1.html"

python3 "$GEN_SCRIPT" --skill listening --source cambridge-1 --test 1 --section 1 --force > /dev/null 2>&1
FILE="$OUT_DIR/cambridge-1_listening_test-1_section-1.html"
[ -f "$FILE" ] && pass "File created: $FILE" || fail "File created" "missing: $FILE"
[ -s "$FILE" ] && pass "File has content ($(wc -c < "$FILE") bytes)" || fail "File has content" "empty file"

# Verify HTML structure
grep -q '<!DOCTYPE html>' "$FILE" && pass "Has DOCTYPE" || fail "Has DOCTYPE" "missing"
grep -q 'questions-container' "$FILE" && pass "Has questions container" || fail "Has questions container" "missing"
grep -q 'pin-overlay' "$FILE" && pass "Has PIN modal" || fail "Has PIN modal" "missing"

# Verify no leftover placeholders
! grep -q '{{SECTION_DATA}}' "$FILE" && pass "SECTION_DATA replaced" || fail "SECTION_DATA replaced" "{{SECTION_DATA}} still present"
! grep -q '{{ANSWER_KEYS}}' "$FILE" && pass "ANSWER_KEYS replaced" || fail "ANSWER_KEYS replaced" "{{ANSWER_KEYS}} still present"
! grep -q '{{TITLE}}' "$FILE" && pass "TITLE replaced" || fail "TITLE replaced" "{{TITLE}} still present"

# Verify question count in index
QCOUNT=$(python3 -c "
import json, sys
try:
    idx = json.load(open('.ielts/test-html/_generated.json'))
    for s in idx['sections']:
        if 'listening' in s.get('path','') and 'test-1_section-1' in s.get('path',''):
            print(s['questionCount'])
            sys.exit(0)
    print('NOT_FOUND')
except: print('ERROR')
")
[ "$QCOUNT" != "NOT_FOUND" ] && [ "$QCOUNT" != "ERROR" ] && pass "Index updated: $QCOUNT questions" || fail "Index updated" "got: $QCOUNT"

# Verify --force overwrite works
python3 "$GEN_SCRIPT" --skill listening --source cambridge-1 --test 1 --section 1 --force > /dev/null 2>&1
[ -f "$FILE" ] && pass "--force overwrite works" || fail "--force overwrite" "file missing after force"

# Verify overwrite without --force fails
python3 "$GEN_SCRIPT" --skill listening --source cambridge-1 --test 1 --section 1 2>/dev/null && fail "--force required" "should have failed without --force" || pass "--force required (correctly fails)"
python3 "$GEN_SCRIPT" --skill listening --source cambridge-1 --test 1 --section 1 --force > /dev/null 2>&1 && pass "--force allows overwrite" || fail "--force allows overwrite" "failed"

echo ""

# ── Flow 2: Generate --all and verify index ──
echo "-- Flow 2: Batch generation (--all) --"

python3 "$GEN_SCRIPT" --skill reading --source cambridge-1 --all --force > /dev/null 2>&1
READING_COUNT=$(ls "$OUT_DIR"/cambridge-1_reading_*.html 2>/dev/null | wc -l | tr -d ' ')
[ "$READING_COUNT" -gt 0 ] && pass "Reading batch: $READING_COUNT files" || fail "Reading batch" "no files generated"

python3 "$GEN_SCRIPT" --skill listening --source cambridge-1 --all --force > /dev/null 2>&1
LISTENING_COUNT=$(ls "$OUT_DIR"/cambridge-1_listening_*.html 2>/dev/null | wc -l | tr -d ' ')
[ "$LISTENING_COUNT" -ge 4 ] && pass "Listening batch: $LISTENING_COUNT files" || fail "Listening batch" "expected >=4, got $LISTENING_COUNT"

# Verify index exists and has entries
[ -f "$OUT_DIR/_generated.json" ] && pass "Index file exists" || fail "Index file" "missing _generated.json"
INDEX_COUNT=$(python3 -c "
import json
idx = json.load(open('.ielts/test-html/_generated.json'))
print(len(idx['sections']))
")
[ "$INDEX_COUNT" -ge 7 ] && pass "Index has $INDEX_COUNT entries (>=7)" || fail "Index entries" "got $INDEX_COUNT"

echo ""

# ── Flow 3: --all-skills and content validation ──
echo "-- Flow 3: Full batch (--all-skills) --"

python3 "$GEN_SCRIPT" --source cambridge-1 --all-skills --force > /dev/null 2>&1
TOTAL=$(ls "$OUT_DIR"/cambridge-1_*.html 2>/dev/null | wc -l | tr -d ' ')
[ "$TOTAL" -ge 20 ] && pass "All skills batch: $TOTAL total files" || fail "All skills batch" "expected >=20, got $TOTAL"

# Verify all files are valid HTML (no {{ }} leftovers)
UNFINISHED=$(grep -l '{{' "$OUT_DIR"/cambridge-1_*.html 2>/dev/null | wc -l | tr -d ' ')
[ "$UNFINISHED" -eq 0 ] && pass "No leftover {{ }} in any file" || fail "Leftover markers" "$UNFINISHED files have {{"

# Verify all files have <script> blocks
for f in "$OUT_DIR"/cambridge-1_listening_*.html; do
    grep -q '<script>' "$f" || { fail "Script block" "missing in $(basename "$f")"; }
done
pass "All listening files have <script> blocks"

echo ""

# ── Flow 4: Server route (if server is running) ──
echo "-- Flow 4: Server route (optional) --"

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/test-html/cambridge-1_listening_test-1_section-1.html 2>/dev/null | grep -q 200; then
    pass "Server route: /test-html/ serves files"
    # Test path traversal
    TRAVERSAL=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8765/test-html/../secret" 2>/dev/null)
    [ "$TRAVERSAL" != "200" ] && pass "Path traversal blocked ($TRAVERSAL)" || fail "Path traversal" "should block"
else
    echo "  SKIP  Server not running — start server.py to test routes"
fi

echo ""
echo "============================================"
echo "Results: $PASS passed, $FAIL failed"
echo "============================================"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
