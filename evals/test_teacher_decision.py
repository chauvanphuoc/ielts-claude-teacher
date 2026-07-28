"""Teacher Decision Quality evals — LLM-as-judge using DeepEval GEval.

Evaluates whether the IELTS teacher's pedagogical decisions are sound.
Uses mock teacher responses as actual_output and GEval to judge quality.

Uses LLM_API_KEY and LLM_MODEL from .env (DeepSeek by default).
The .env is loaded automatically — no manual export needed.

Usage:
  .venv/bin/deepeval test run evals/test_teacher_decision.py
"""

import os
import json
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load project .env before anything else
_project_root = Path(__file__).resolve().parent.parent
_dotenv_path = _project_root / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

# Bridge .env LLM_API_KEY -> DeepEval's OPENAI_API_KEY (DeepSeek is OpenAI-compatible)
_llm_api_key = os.getenv("LLM_API_KEY")
_llm_api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/chat/completions")
_llm_model = os.getenv("LLM_MODEL", "deepseek-v4-flash")

if _llm_api_key and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _llm_api_key
    _base_url = _llm_api_url.rstrip("/").replace("/chat/completions", "")
    if _base_url and not os.getenv("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = _base_url

from deepeval import assert_test
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval

from evals.fixtures.sample_profiles import (
    PROFILE_TFNG_STRUGGLE,
    PROFILE_MIXED,
    PROFILE_SRS_DUE,
)

JUDGE_MODEL = _llm_model  # deepseek-v4-flash from .env


def _has_llm_key() -> bool:
    """Check if an LLM API key is configured for GEval."""
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("LLM_API_KEY")
    )


def _describe_profile(profile: dict) -> str:
    """Summarize a student profile as input context for the teacher."""
    summary = []
    summary.append(f"Target band: {profile['learner']['targetBand']}")
    summary.append(f"Exam date: {profile['learner']['examDate']}")
    summary.append(f"Sessions completed: {profile['learner']['sessionsCompleted']}")

    for skill_name, skill_data in profile["skills"].items():
        mastery = skill_data.get("kcMastery", {})
        summaries = []
        for kc_id, kc in mastery.items():
            if kc.get("attempts", 0) > 0:
                summaries.append(
                    f"{kc_id}(lvl={kc['level']}, err={kc['errorRate']:.2f}, "
                    f"att={kc['attempts']})"
                )
        if summaries:
            summary.append(f"{skill_name} KCs: {', '.join(summaries)}")

    if profile.get("testHistory"):
        recent = profile["testHistory"][-3:]
        summary.append(f"Recent tests: {json.dumps(recent)}")
    return "\n".join(summary)


# ── GEval Tests ─────────────────────────────────────────────────────
# Each test provides:
#   input = student profile context (what the teacher sees)
#   actual_output = a mock teacher response (what the teacher says)
# GEval judges: is the response pedagogically sound?

@pytest.mark.skipif(not _has_llm_key(), reason="No LLM API key configured for GEval")
def test_diagnose_identifies_root_cause_kc():
    """Teacher correctly identifies inference as root cause of T/F/NG errors."""
    profile_desc = _describe_profile(PROFILE_TFNG_STRUGGLE)

    # A GOOD teacher response — should score >= 0.5
    teacher_response = (
        "Today we focus on kc-read-inference as priority #1 (score 5.5). "
        "This is the root cause: kc-read-tfng depends on kc-read-inference, "
        "and inference has a 60% error rate after 2 attempts. Your T/F/NG "
        "errors (80% after 5 attempts, still at 'weak') trace back to "
        "difficulty distinguishing implied vs stated meaning — that's inference.\n\n"
        "Priority #2 is kc-read-main-idea (score 3.5). It has a 50% error rate "
        "and its SRS review was due yesterday. Since main-idea is a parent of "
        "inference in the dependency chain, strengthening it will help both "
        "inference and T/F/NG.\n\n"
        "Chain: main-idea → inference → tfng. We fix from the root up."
    )

    metric = GEval(
        name="Diagnose Root Cause",
        criteria="Determine if the diagnosis correctly identifies root cause KCs.",
        evaluation_steps=[
            "Check: does the diagnosis identify kc-read-inference as a HIGHER "
            "priority than kc-read-tfng because tfng depends on inference?",
            "Check: does the diagnosis cite specific error rates from the "
            "profile (tfng=0.80, inference=0.60)?",
            "Check: does the diagnosis mention SRS-due KCs like "
            "kc-read-main-idea for review?",
            "Check: does the explanation follow a logical dependency chain: "
            "main-idea -> inference -> tfng?",
        ],
        threshold=0.5,
        model=JUDGE_MODEL,
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
    )

    test_case = LLMTestCase(
        input=profile_desc,
        actual_output=teacher_response,
    )
    assert_test(test_case, [metric])


@pytest.mark.skipif(not _has_llm_key(), reason="No LLM API key configured for GEval")
def test_diagnose_prioritizes_srs_due_kcs():
    """Teacher correctly prioritizes KCs due for spaced repetition review."""
    profile_desc = _describe_profile(PROFILE_SRS_DUE)

    teacher_response = (
        "Today's top priority is SRS review — you have 5 KCs past their "
        "review dates:\n\n"
        "1. kc-listen-spelling (SRS due 3 days ago, 80% error, weak). "
        "This is critical — spelling errors compound across all listening tasks.\n"
        "2. kc-listen-distractor (SRS due 2 days ago, 33% error, ok). "
        "3. kc-listen-numbers (SRS due yesterday, 20% error, ok).\n"
        "4. kc-speak-pronunciation (SRS due 2 days ago, 50% error).\n"
        "5. kc-speak-fluency (SRS due yesterday, 40% error).\n\n"
        "Per our priority algorithm, SRS-due KCs get +2 bonus points. "
        "We should do a quick review of all 5 before starting new material. "
        "Forgetting is worse than not knowing."
    )

    metric = GEval(
        name="SRS Due Prioritization",
        criteria="Determine if the diagnosis correctly prioritizes SRS-due KCs.",
        evaluation_steps=[
            "Check: are KCs with nextReviewDate in the past listed and "
            "prioritized first?",
            "Check: does the diagnosis mention at least 2 specific KCs with "
            "SRS due (spelling, numbers, distractor, fluency, pronunciation)?",
            "Check: does the diagnosis explain that SRS-due KCs get "
            "+2 priority boost?",
        ],
        threshold=0.5,
        model=JUDGE_MODEL,
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
    )

    test_case = LLMTestCase(
        input=profile_desc,
        actual_output=teacher_response,
    )
    assert_test(test_case, [metric])


@pytest.mark.skipif(not _has_llm_key(), reason="No LLM API key configured for GEval")
def test_plan_creates_appropriate_lesson():
    """Teacher creates an appropriate lesson plan for weak grammar KC."""
    profile_desc = _describe_profile(PROFILE_MIXED)

    teacher_response = (
        "Lesson plan for kc-write-gra-tenses (70% error rate, SRS due):\n\n"
        "First, checking lesson-library... no existing lesson for tenses with "
        "timesUsed<2. Creating new mini-test.\n\n"
        "5 questions targeting verb tense errors:\n"
        "- Q1-2: Gap-fill with present perfect vs past simple (your most "
        "common error from last essay)\n"
        "- Q3: Error correction — identify wrong tense in a sentence\n"
        "- Q4: Sentence transformation — change tense while keeping meaning\n"
        "- Q5: Contextual fill — choose correct tense in a paragraph\n\n"
        "This is our 1st new lesson this session (max 3). "
        "Answer key provided with Vietnamese explanations for each error pattern."
    )

    metric = GEval(
        name="Lesson Plan Appropriateness",
        criteria="Determine if the lesson plan is appropriate for the target KC.",
        evaluation_steps=[
            "Check: does the plan target kc-write-gra-tenses specifically?",
            "Check: does the plan suggest appropriate question types "
            "(gap-fill, error correction, sentence transformation)?",
            "Check: does the plan mention checking lesson-library first "
            "(Phase 3.2 reuse rule)?",
            "Check: does the plan respect max 3 new lessons per session?",
        ],
        threshold=0.5,
        model=JUDGE_MODEL,
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
    )

    test_case = LLMTestCase(
        input=profile_desc,
        actual_output=teacher_response,
    )
    assert_test(test_case, [metric])


@pytest.mark.skipif(not _has_llm_key(), reason="No LLM API key configured for GEval")
def test_evaluate_provides_specific_feedback():
    """Teacher provides specific, actionable feedback after grading."""
    profile_desc = _describe_profile(PROFILE_TFNG_STRUGGLE)

    teacher_response = (
        "Results: 3/5 (60%) on T/F/NG practice. Here's the breakdown:\n\n"
        "✅ Q1 (TRUE): Correct — you matched the passage statement.\n"
        "✅ Q2 (FALSE): Correct — you caught the contradiction. Good.\n"
        "❌ Q3 (NOT GIVEN): You answered TRUE. The passage was silent about "
        "this point — it didn't say it was true OR false. This is a classic "
        "NG confusion: when the passage doesn't mention something, it's NG, "
        "even if it 'sounds true'.\n"
        "❌ Q4 (FALSE): You answered TRUE. The passage explicitly said the "
        "opposite. Key clue: look for contradiction words like 'however', "
        "'but', 'although'.\n"
        "✅ Q5 (NOT GIVEN): Correct — you correctly identified the passage "
        "was silent.\n\n"
        "Pattern: you're defaulting to TRUE when unsure. Strategy: when you "
        "can't find the statement in the passage, ask 'does the passage say "
        "the OPPOSITE?' If yes → FALSE. If no → NOT GIVEN.\n\n"
        "KC update: kc-read-tfng errorRate moves from 0.40 to 0.44 "
        "(still 'weak', 6 attempts). Escalation threshold reached — "
        "we should try a different approach next session."
    )

    metric = GEval(
        name="Evaluate Feedback Quality",
        criteria="Determine if the evaluation feedback is specific and actionable.",
        evaluation_steps=[
            "Check: is the feedback specific — does it reference Q3 and Q4 "
            "errors by question number with explanations?",
            "Check: does the feedback identify the error pattern: confusing "
            "NOT GIVEN (silent) with TRUE, and missing FALSE (contradiction)?",
            "Check: does the feedback include actionable strategy "
            "('ask: does the passage say the OPPOSITE?')?",
            "Check: does the feedback check escalation (5+ attempts without "
            "improvement → change approach)?",
        ],
        threshold=0.5,
        model=JUDGE_MODEL,
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
    )

    test_case = LLMTestCase(
        input=profile_desc,
        actual_output=teacher_response,
    )
    assert_test(test_case, [metric])


@pytest.mark.skipif(not _has_llm_key(), reason="No LLM API key configured for GEval")
def test_cross_skill_pattern_detection():
    """Teacher identifies overlapping weaknesses across reading and listening."""
    profile_desc = _describe_profile(PROFILE_MIXED)

    teacher_response = (
        "Cross-skill pattern detected — inference weakness spans both skills:\n\n"
        "1. kc-read-inference: 30% error rate (ok, 2 attempts)\n"
        "2. kc-listen-inference: untested, but your listening distractor errors "
        "(33%) suggest you may also struggle with implied meaning in audio.\n\n"
        "Integrated practice suggestion: do a combined exercise where you "
        "first read a short passage (inference practice), then listen to a "
        "related talk (listening inference). Compare how inference works in "
        "reading (you can re-read) vs listening (one chance).\n\n"
        "Also: kc-read-vocab-context (60% error) and kc-listen-spelling "
        "(70% error, SRS due) both point to vocabulary gap. Your vocabulary "
        "knowledge is weak in context — you recognize words but can't apply "
        "them. Combined vocab+spelling drill recommended."
    )

    metric = GEval(
        name="Cross-Skill Pattern Detection",
        criteria="Determine if the response identifies cross-skill patterns.",
        evaluation_steps=[
            "Check: does the response identify that inference weaknesses "
            "span both reading and listening?",
            "Check: does the response flag overlapping vocabulary/spelling "
            "weaknesses across skills (vocab-context + spelling)?",
            "Check: does the response suggest integrated practice combining "
            "both skills, not isolated exercises?",
        ],
        threshold=0.5,
        model=JUDGE_MODEL,
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.INPUT],
    )

    test_case = LLMTestCase(
        input=profile_desc,
        actual_output=teacher_response,
    )
    assert_test(test_case, [metric])
