# IELTS Claude Teacher — DeepEval Evals Suite

DeepEval-based evaluation system for the IELTS Claude Teacher agent.
Uses the [DeepEval vibe coding](https://deepeval.com/docs/vibe-coding) approach:
run evals → read failures → fix code → re-run.

## Quick Start

```bash
# Install DeepEval (already done if you're reading this)
.venv/bin/python3 -m pip install -U deepeval

# Run all deterministic evals (no API key needed)
.venv/bin/deepeval test run evals/test_kc_mastery.py evals/test_trace_quality.py evals/test_cli_correctness.py

# Run the vibe coding loop (5 rounds)
bash evals/run_loop.sh

# Run deterministic-only loop
DETERMINISTIC_ONLY=1 bash evals/run_loop.sh
```

## Test Files

| File | What it tests | Type |
|------|--------------|------|
| `test_kc_mastery.py` | Cumulative error rate formula, level thresholds, SRS intervals, subjective scoring | Deterministic |
| `test_trace_quality.py` | Trace record validation (required fields, enums, confidence range, security) | Deterministic |
| `test_cli_correctness.py` | CLI functions: `_build_fresh_profile`, `validate`, `status`, `lesson-library` | Deterministic |
| `test_teacher_decision.py` | Teacher diagnosis, planning, evaluation, and cross-skill pattern detection | LLM-as-judge (GEval) |

## Fixtures

Shared test data in `evals/fixtures/`:

| File | Contents |
|------|----------|
| `sample_profiles.py` | Pre-built student profiles: `PROFILE_ALL_WEAK`, `PROFILE_TFNG_STRUGGLE`, `PROFILE_MIXED`, `PROFILE_SRS_DUE` |
| `sample_traces.py` | Valid/invalid trace records for trace quality evals |
| `kc_scenarios.py` | Test vectors for error rate, level thresholds, SRS intervals, subjective scoring |

## LLM-as-Judge (GEval)

`test_teacher_decision.py` requires an LLM API key. Set one of:

```bash
# Option A: Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPEVAL_MODEL_PROVIDER="anthropic"

# Option B: OpenAI
export OPENAI_API_KEY="sk-..."

# Option C: DeepSeek (via OpenAI-compatible endpoint)
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.deepseek.com"
```

Without a key, LLM-as-judge tests are **automatically skipped** — deterministic tests still run.

## Known Gaps

The `_validate_trace_record` function in `shared/ielts_cli.py` currently does **not** enforce path-traversal checks on `evidenceRefs`. The trace quality tests document this. When the validator is hardened, flip the two "known gap" tests from `expect_valid=True` to `expect_valid=False`.

## Vibe Coding Workflow

1. Run evals: `.venv/bin/deepeval test run evals/`
2. Read per-metric scores and `reason` strings
3. Pick the lowest-scoring metric, identify the failing test case
4. Fix the smallest plausible thing (prompt in SKILL.md, function in ielts_cli.py, or the eval itself)
5. Re-run: `.venv/bin/deepeval test run evals/`
6. Confirm the metric improved without regressions

**Guardrails:**
- Don't lower thresholds to make failures disappear
- Don't delete hard test cases
- Don't change the eval metric to match broken code

## Directory

```
evals/
├── __init__.py
├── conftest.py                  # Shared fixtures, sys.path, formula functions
├── test_kc_mastery.py           # KC mastery formula evals (32 tests)
├── test_trace_quality.py        # Trace quality evals (20 tests)
├── test_cli_correctness.py      # CLI correctness evals (8 tests)
├── test_teacher_decision.py     # LLM-as-judge evals (5 tests)
├── run_loop.sh                  # Vibe coding loop script
├── README.md                    # This file
└── fixtures/
    ├── __init__.py
    ├── sample_profiles.py       # Pre-built profile dicts
    ├── sample_traces.py         # Pre-built trace dicts
    └── kc_scenarios.py          # KC mastery test vectors
```
