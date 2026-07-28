"""IELTS Teacher Eval Runner — trace-to-GEval pipeline.

Reads traces from .ielts/quality/traces/, builds LLMTestCases,
runs GEval on 3 phases (diagnose, plan, evaluate), computes TQS.

Usage:
  .venv/bin/python3 evals/eval_teacher.py --run-id session-2026-07-28-001 [--date 2026-07-28] [--dry-run]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve project root and add to path BEFORE local imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "shared"))

# Load .env for API keys BEFORE DeepEval imports
_dotenv_path = PROJECT_ROOT / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)
    # Bridge LLM_API_KEY -> OPENAI_API_KEY for DeepEval (DeepSeek OpenAI-compatible)
    _llm_key = os.getenv("LLM_API_KEY")
    _llm_url = os.getenv("LLM_API_URL", "")
    if _llm_key and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = _llm_key
        _base = _llm_url.rstrip("/").replace("/chat/completions", "")
        if _base and not os.getenv("OPENAI_BASE_URL"):
            os.environ["OPENAI_BASE_URL"] = _base

import evals.config as config  # noqa: E402

from ielts_cli import _load_json, _parse_json_or_jsonl, QUALITY_TRACES_DIR

IELTS_DIR = PROJECT_ROOT / ".ielts"
EVALS_DIR = IELTS_DIR / "quality" / "evals"


def load_traces_for_session(run_id: str, date_key: str | None = None) -> list[dict]:
    """Load all trace records for a given runId from the date's trace file.

    Args:
        run_id: The session run ID (e.g. session-2026-07-28-001)
        date_key: ISO date string (e.g. 2026-07-28). Defaults to today.

    Returns:
        List of trace records matching the runId, sorted by timestamp.
    """
    if date_key is None:
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    trace_file = QUALITY_TRACES_DIR / f"{date_key}.jsonl"
    if not trace_file.exists():
        return []

    all_records = _parse_json_or_jsonl(trace_file)
    matching = [r for r in all_records if isinstance(r, dict) and r.get("runId") == run_id]
    matching.sort(key=lambda r: r.get("timestamp", ""))
    return matching


def extract_phase_transcripts(traces: list[dict]) -> dict[str, dict]:
    """Extract teacherTranscript per phase from trace records.

    Returns dict mapping decisionType -> trace record.
    Only returns phases that have a non-empty teacherTranscript.
    """
    phases = {}
    for trace in traces:
        dt = trace.get("decisionType")
        transcript = trace.get("teacherTranscript", "")
        if dt and transcript:
            phases[dt] = trace
    return phases


def build_geval_input(traces: list[dict]) -> dict:
    """Build the evaluation input context for GEval from session traces.

    Extracts: student profile context (from evidenceRefs + action fields),
    teacher transcripts per phase, and session metadata.
    """
    # Gather context from traces
    kc_targets = set()
    evidence_files = set()
    actions = {}

    for t in traces:
        for kc in t.get("kcTargets", []):
            kc_targets.add(kc)
        for ref in t.get("evidenceRefs", []):
            evidence_files.add(ref)
        actions[t.get("decisionType", "unknown")] = t.get("action", "")

    # Read student profile summary if available
    profile_path = IELTS_DIR / "student-profile.json"
    profile_context = ""
    if profile_path.exists():
        profile = _load_json(profile_path)
        if profile:
            learner = profile.get("learner", {})
            skills = profile.get("skills", {})
            summary_parts = [
                f"Target band: {learner.get('targetBand', 'N/A')}",
                f"Exam date: {learner.get('examDate', 'N/A')}",
                f"Sessions: {learner.get('sessionsCompleted', 0)}",
            ]
            for skill_name, skill_data in skills.items():
                mastery = skill_data.get("kcMastery", {})
                tested = {k: v for k, v in mastery.items() if v.get("attempts", 0) > 0}
                if tested:
                    kc_str = ", ".join(
                        f"{k}(err={v['errorRate']:.2f},lvl={v['level']})"
                        for k, v in tested.items()
                    )
                    summary_parts.append(f"{skill_name}: {kc_str}")
            profile_context = "\n".join(summary_parts)

    return {
        "kcTargets": sorted(kc_targets),
        "evidenceFiles": sorted(evidence_files),
        "actions": actions,
        "profileContext": profile_context,
    }


def run_geval_on_phases(phases: dict[str, dict], context: dict) -> dict:
    """Run GEval on each pedagogical phase and return scores.

    Only evaluates phases that have teacherTranscript data.
    Phases: diagnose, plan, evaluate (teach excluded — circular LLM judge).

    Returns:
        dict with scores per phase, each containing score, reason, and error.
    """
    from deepeval.test_case import LLMTestCase, SingleTurnParams
    from deepeval.metrics import GEval

    model = os.getenv("LLM_MODEL", "deepseek-v4-flash")

    # GEval rubric per phase (same criteria as test_teacher_decision.py)
    phase_configs = {
        "diagnose": GEval(
            name="Diagnose Quality",
            criteria="Determine if the teacher correctly diagnosed the student's weaknesses.",
            evaluation_steps=[
                "Check: does the diagnosis identify the most impactful KC based "
                "on error rate and dependency chain evidence from the profile?",
                "Check: does the diagnosis cite specific error rates and SRS "
                "status from the student profile?",
                "Check: is the diagnosis explained in a way the student can "
                "understand?",
            ],
            threshold=0.5,
            model=model,
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
        ),
        "plan": GEval(
            name="Plan Quality",
            criteria="Determine if the lesson plan is appropriate for the diagnosed KCs.",
            evaluation_steps=[
                "Check: does the plan target the KCs identified in the diagnose phase?",
                "Check: are question types appropriate for the target KC?",
                "Check: does the plan follow the lesson-library reuse rule "
                "(timesUsed < 2 -> reuse; else -> create)?",
                "Check: does the plan respect the max 3 new lessons per session "
                "guardrail?",
            ],
            threshold=0.5,
            model=model,
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
        ),
        "evaluate": GEval(
            name="Evaluate Quality",
            criteria="Determine if the evaluation feedback is specific and actionable.",
            evaluation_steps=[
                "Check: is per-question feedback specific (references question "
                "numbers, explains why an answer was wrong)?",
                "Check: does the feedback identify error patterns (not just "
                "'wrong' but the specific misconception)?",
                "Check: are KC mastery updates correct per the Phase 5.3 formula?",
                "Check: does the feedback include actionable next steps?",
            ],
            threshold=0.5,
            model=model,
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
        ),
    }

    results = {}
    profile_context = context.get("profileContext", "")

    for phase, trace in phases.items():
        if phase not in phase_configs:
            continue

        metric = phase_configs[phase]
        teacher_text = trace.get("teacherTranscript", "")
        if not teacher_text:
            continue

        test_case = LLMTestCase(
            input=profile_context,
            actual_output=teacher_text,
        )

        try:
            metric.measure(test_case)
            results[phase] = {
                "score": round(metric.score, 3),
                "reason": metric.reason or "",
                "passed": metric.is_successful(),
            }
        except Exception as e:
            results[phase] = {
                "score": 0.0,
                "reason": f"GEval error: {str(e)[:200]}",
                "passed": False,
            }

    return results


def compute_tqs(scores: dict) -> float:
    """Compute Teacher Quality Score as mean of available phase scores."""
    if not scores:
        return 0.0
    values = [s["score"] for s in scores.values()]
    return round(sum(values) / len(values), 3)


def write_eval_output(run_id: str, scores: dict, tqs: float, context: dict,
                      mode: str) -> Path:
    """Write eval results to .ielts/quality/evals/.

    Writes both a per-session file and latest.json for Phase 1 consumption.
    """
    _ensure_dir(EVALS_DIR)

    output = {
        "runId": run_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "scores": scores,
        "tqs": tqs,
        "kcTargets": context.get("kcTargets", []),
        "model": os.getenv("LLM_MODEL", "deepseek-v4-flash"),
    }

    # Per-session file
    session_file = EVALS_DIR / f"{run_id}.json"
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # latest.json for Phase 1 consumption
    latest_file = EVALS_DIR / "latest.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return session_file


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="IELTS Teacher Eval Runner")
    parser.add_argument("--run-id", required=True, help="Session run ID")
    parser.add_argument("--date", help="Date override (default: today)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip GEval, just test trace loading")
    args = parser.parse_args()

    # Load sampling config
    evals_config = config.load_evals_config()

    # Dry-run always runs — bypass sampling
    if args.dry_run:
        traces = load_traces_for_session(args.run_id, args.date)
        phases = extract_phase_transcripts(traces)
        context = build_geval_input(traces)
        print(json.dumps({
            "status": "dry_run",
            "runId": args.run_id,
            "phasesFound": list(phases.keys()),
            "traceCount": len(traces),
            "context": context,
        }, ensure_ascii=False, indent=2))
        return 0

    # Check if we should evaluate this session
    if not config.should_evaluate(args.run_id, evals_config):
        print(json.dumps({
            "status": "skipped",
            "runId": args.run_id,
            "reason": f"Sampling mode={evals_config.get('mode', 'never')} "
                      f"— eval not selected for this session",
        }, ensure_ascii=False))
        return 0

    # Load traces
    traces = load_traces_for_session(args.run_id, args.date)
    if len(traces) < 3:
        print(json.dumps({
            "status": "skipped",
            "runId": args.run_id,
            "reason": f"Incomplete session: {len(traces)} traces found, need >= 3 "
                      f"(diagnose + plan + evaluate)",
        }, ensure_ascii=False))
        return 0

    # Extract teacher transcripts per phase
    phases = extract_phase_transcripts(traces)
    if not phases:
        print(json.dumps({
            "status": "skipped",
            "runId": args.run_id,
            "reason": "No teacherTranscript data in any trace — "
                      "teacher may not have captured responses",
        }, ensure_ascii=False))
        return 0

    context = build_geval_input(traces)

    # Run GEval
    print(f"Evaluating session {args.run_id} "
          f"(mode={evals_config.get('mode', 'unknown')}, "
          f"phases={list(phases.keys())})...", file=sys.stderr)

    scores = run_geval_on_phases(phases, context)
    tqs = compute_tqs(scores)

    # Write output
    output_path = write_eval_output(args.run_id, scores, tqs, context,
                                    evals_config.get("mode", "unknown"))

    result = {
        "status": "ok",
        "runId": args.run_id,
        "tqs": tqs,
        "phasesEvaluated": list(scores.keys()),
        "outputFile": str(output_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
