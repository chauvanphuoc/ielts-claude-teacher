#!/bin/bash
# DeepEval vibe coding loop for IELTS Claude Teacher
#
# Usage:
#   bash evals/run_loop.sh            # 5 rounds (default)
#   bash evals/run_loop.sh 3          # 3 rounds
#   DETERMINISTIC_ONLY=1 bash evals/run_loop.sh  # skip LLM-as-judge tests
#
# Each round:
#   1. Runs the full eval suite
#   2. Summarizes pass/fail
#   3. Fails the loop if any test fails

set -euo pipefail

ROUNDS="${1:-5}"
DEEPEVAL=".venv/bin/deepeval"
EVALS_DIR="evals"

echo "=== DeepEval Vibe Coding Loop ==="
echo "Project: IELTS Claude Teacher"
echo "Rounds: $ROUNDS"
echo ""

if [[ "${DETERMINISTIC_ONLY:-}" == "1" ]]; then
    TEST_FILES="$EVALS_DIR/test_kc_mastery.py $EVALS_DIR/test_trace_quality.py $EVALS_DIR/test_cli_correctness.py"
    echo "Mode: Deterministic only (no LLM key needed)"
else
    TEST_FILES="$EVALS_DIR/"
    echo "Mode: Full suite (LLM-as-judge included if API key set)"
fi
echo ""

PASSED_ALL_ROUNDS=true

for i in $(seq 1 "$ROUNDS"); do
    echo "=============================================="
    echo "  Round $i/$ROUNDS"
    echo "=============================================="

    if .venv/bin/deepeval test run $TEST_FILES 2>&1; then
        echo ""
        echo "  ✅ Round $i PASSED"
    else
        echo ""
        echo "  ❌ Round $i FAILED — review output above"
        PASSED_ALL_ROUNDS=false
    fi

    if [[ $i -lt $ROUNDS ]]; then
        echo "  Waiting before next round..."
        sleep 1
    fi
    echo ""
done

echo "=============================================="
if $PASSED_ALL_ROUNDS; then
    echo "✅ All $ROUNDS rounds passed!"
    exit 0
else
    echo "❌ Some rounds failed. Review the failures above."
    exit 1
fi
