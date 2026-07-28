"""Pre-built student profile dicts for deterministic evals.

Usage:
    from evals.fixtures.sample_profiles import PROFILE_ALL_WEAK, PROFILE_MIXED
"""

from datetime import date, timedelta


def _d(n: int) -> str:
    """Return ISO date string n days from today."""
    return (date.today() + timedelta(days=n)).isoformat()


# ── Fresh profile: all KCs at default state ─────────────────────────

PROFILE_ALL_WEAK = {
    "version": "2.0.0",
    "learner": {
        "targetBand": 6.0,
        "examDate": "2027-07-27",
        "activeSkills": ["listening", "reading", "writing", "speaking"],
        "sessionsCompleted": 0,
        "diagnosticCompleted": False,
    },
    "skills": {
        "listening": {
            "currentBand": 0,
            "kcMastery": {
                "kc-listen-spelling": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-numbers": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-distractor": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-mc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-gapfill": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-map": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-inference": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
        "reading": {
            "currentBand": 0,
            "kcMastery": {
                "kc-read-main-idea": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-detail": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-inference": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-tfng": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-ynng": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-mc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-gapfill": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-matching": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-vocab-context": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
        "writing": {
            "currentBand": 0,
            "kcMastery": {
                "kc-write-tr": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-cc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-lr": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra-articles": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra-tenses": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra-complex": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
        "speaking": {
            "currentBand": 0,
            "kcMastery": {
                "kc-speak-fluency": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-pronunciation": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-lexical": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-grammar": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-coherence": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
    },
    "vocabulary": {"weakTopics": [], "words": {}},
    "grammar": {"weakPoints": []},
    "testHistory": [],
    "coachNotes": [],
}


# ── T/F/NG struggle: high error on tfng, root cause may be inference ─

PROFILE_TFNG_STRUGGLE = {
    "version": "2.0.0",
    "learner": {
        "targetBand": 7.0,
        "examDate": "2027-07-27",
        "activeSkills": ["listening", "reading", "writing", "speaking"],
        "sessionsCompleted": 5,
        "diagnosticCompleted": True,
    },
    "skills": {
        "listening": {
            "currentBand": 0,
            "kcMastery": {
                "kc-listen-spelling": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-numbers": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-distractor": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-mc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-gapfill": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-map": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-inference": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
        "reading": {
            "currentBand": 5.5,
            "kcMastery": {
                "kc-read-main-idea": {"level": "weak", "errorRate": 0.50, "attempts": 1, "nextReviewDate": _d(-1)},
                "kc-read-detail": {"level": "weak", "errorRate": 0.60, "attempts": 2, "nextReviewDate": _d(1)},
                "kc-read-inference": {"level": "weak", "errorRate": 0.60, "attempts": 2, "nextReviewDate": _d(-2)},
                "kc-read-tfng": {"level": "weak", "errorRate": 0.80, "attempts": 5, "nextReviewDate": _d(1)},
                "kc-read-ynng": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-mc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-gapfill": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-matching": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-vocab-context": {"level": "ok", "errorRate": 0.30, "attempts": 3, "nextReviewDate": _d(5)},
            },
        },
        "writing": {
            "currentBand": 6.0,
            "kcMastery": {
                "kc-write-tr": {"level": "mastered", "errorRate": 0.10, "attempts": 2, "nextReviewDate": _d(10)},
                "kc-write-cc": {"level": "ok", "errorRate": 0.20, "attempts": 2, "nextReviewDate": _d(3)},
                "kc-write-lr": {"level": "ok", "errorRate": 0.25, "attempts": 2, "nextReviewDate": _d(3)},
                "kc-write-gra": {"level": "ok", "errorRate": 0.33, "attempts": 3, "nextReviewDate": _d(1)},
                "kc-write-gra-articles": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra-tenses": {"level": "weak", "errorRate": 1.0, "attempts": 1, "nextReviewDate": _d(-1)},
                "kc-write-gra-complex": {"level": "weak", "errorRate": 1.0, "attempts": 1, "nextReviewDate": _d(-2)},
            },
        },
        "speaking": {
            "currentBand": 0,
            "kcMastery": {
                "kc-speak-fluency": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-pronunciation": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-lexical": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-grammar": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-coherence": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
    },
    "vocabulary": {"weakTopics": [], "words": {}},
    "grammar": {"weakPoints": []},
    "testHistory": [
        {"date": _d(-5), "type": "mini-test", "skill": "reading", "title": "T/F/NG test", "score": "1/5", "pct": 20},
        {"date": _d(-3), "type": "mini-test", "skill": "reading", "title": "T/F/NG retake", "score": "2/5", "pct": 40},
    ],
    "coachNotes": [
        {"date": _d(-5), "category": "weakness", "skill": "reading",
         "content": "T/F/NG: Confused NOT GIVEN with TRUE. Needs practice distinguishing 'not stated' from 'stated as true'.",
         "priority": "high"},
    ],
}


# ── SRS due: many KCs with nextReviewDate in the past ───────────────

PROFILE_SRS_DUE = {
    "version": "2.0.0",
    "learner": {
        "targetBand": 6.5,
        "examDate": "2027-07-27",
        "activeSkills": ["listening", "reading", "writing", "speaking"],
        "sessionsCompleted": 10,
        "diagnosticCompleted": True,
    },
    "skills": {
        "listening": {
            "currentBand": 5.0,
            "kcMastery": {
                "kc-listen-spelling": {"level": "weak", "errorRate": 0.80, "attempts": 3, "nextReviewDate": _d(-3)},
                "kc-listen-numbers": {"level": "ok", "errorRate": 0.20, "attempts": 2, "nextReviewDate": _d(-1)},
                "kc-listen-distractor": {"level": "ok", "errorRate": 0.33, "attempts": 1, "nextReviewDate": _d(-2)},
                "kc-listen-mc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-gapfill": {"level": "weak", "errorRate": 0.50, "attempts": 1, "nextReviewDate": _d(5)},
                "kc-listen-map": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-inference": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
        "reading": {
            "currentBand": 6.0,
            "kcMastery": {
                "kc-read-main-idea": {"level": "mastered", "errorRate": 0.10, "attempts": 4, "nextReviewDate": _d(30)},
                "kc-read-detail": {"level": "mastered", "errorRate": 0.05, "attempts": 3, "nextReviewDate": _d(25)},
                "kc-read-inference": {"level": "ok", "errorRate": 0.25, "attempts": 2, "nextReviewDate": _d(3)},
                "kc-read-tfng": {"level": "ok", "errorRate": 0.30, "attempts": 3, "nextReviewDate": _d(7)},
                "kc-read-ynng": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-mc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-gapfill": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-matching": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-vocab-context": {"level": "ok", "errorRate": 0.20, "attempts": 3, "nextReviewDate": _d(5)},
            },
        },
        "writing": {
            "currentBand": 6.0,
            "kcMastery": {
                "kc-write-tr": {"level": "mastered", "errorRate": 0.10, "attempts": 2, "nextReviewDate": _d(28)},
                "kc-write-cc": {"level": "ok", "errorRate": 0.20, "attempts": 2, "nextReviewDate": _d(7)},
                "kc-write-lr": {"level": "ok", "errorRate": 0.25, "attempts": 2, "nextReviewDate": _d(7)},
                "kc-write-gra": {"level": "ok", "errorRate": 0.30, "attempts": 3, "nextReviewDate": _d(10)},
                "kc-write-gra-articles": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra-tenses": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra-complex": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
        "speaking": {
            "currentBand": 4.5,
            "kcMastery": {
                "kc-speak-fluency": {"level": "weak", "errorRate": 0.40, "attempts": 1, "nextReviewDate": _d(-1)},
                "kc-speak-pronunciation": {"level": "weak", "errorRate": 0.50, "attempts": 1, "nextReviewDate": _d(-2)},
                "kc-speak-lexical": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-grammar": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-speak-coherence": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
    },
    "vocabulary": {"weakTopics": [], "words": {}},
    "grammar": {"weakPoints": []},
    "testHistory": [],
    "coachNotes": [],
}


# ── Mixed mastery: realistic mid-study state ────────────────────────

PROFILE_MIXED = {
    "version": "2.0.0",
    "learner": {
        "targetBand": 7.0,
        "examDate": "2027-07-27",
        "activeSkills": ["listening", "reading", "writing", "speaking"],
        "sessionsCompleted": 8,
        "diagnosticCompleted": True,
    },
    "skills": {
        "listening": {
            "currentBand": 5.5,
            "kcMastery": {
                "kc-listen-spelling": {"level": "weak", "errorRate": 0.70, "attempts": 3, "nextReviewDate": _d(-1)},
                "kc-listen-numbers": {"level": "mastered", "errorRate": 0.10, "attempts": 4, "nextReviewDate": _d(20)},
                "kc-listen-distractor": {"level": "ok", "errorRate": 0.33, "attempts": 1, "nextReviewDate": _d(3)},
                "kc-listen-mc": {"level": "weak", "errorRate": 0.50, "attempts": 1, "nextReviewDate": _d(1)},
                "kc-listen-gapfill": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-map": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-listen-inference": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
        "reading": {
            "currentBand": 6.0,
            "kcMastery": {
                "kc-read-main-idea": {"level": "ok", "errorRate": 0.20, "attempts": 3, "nextReviewDate": _d(5)},
                "kc-read-detail": {"level": "ok", "errorRate": 0.25, "attempts": 2, "nextReviewDate": _d(2)},
                "kc-read-inference": {"level": "ok", "errorRate": 0.30, "attempts": 2, "nextReviewDate": _d(4)},
                "kc-read-tfng": {"level": "ok", "errorRate": 0.35, "attempts": 4, "nextReviewDate": _d(10)},
                "kc-read-ynng": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-mc": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-gapfill": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-matching": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-read-vocab-context": {"level": "weak", "errorRate": 0.60, "attempts": 2, "nextReviewDate": _d(-1)},
            },
        },
        "writing": {
            "currentBand": 6.0,
            "kcMastery": {
                "kc-write-tr": {"level": "mastered", "errorRate": 0.08, "attempts": 3, "nextReviewDate": _d(25)},
                "kc-write-cc": {"level": "mastered", "errorRate": 0.12, "attempts": 3, "nextReviewDate": _d(20)},
                "kc-write-lr": {"level": "ok", "errorRate": 0.20, "attempts": 2, "nextReviewDate": _d(3)},
                "kc-write-gra": {"level": "ok", "errorRate": 0.25, "attempts": 3, "nextReviewDate": _d(5)},
                "kc-write-gra-articles": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
                "kc-write-gra-tenses": {"level": "weak", "errorRate": 0.70, "attempts": 2, "nextReviewDate": _d(-1)},
                "kc-write-gra-complex": {"level": "weak", "errorRate": 0.80, "attempts": 2, "nextReviewDate": _d(-1)},
            },
        },
        "speaking": {
            "currentBand": 5.0,
            "kcMastery": {
                "kc-speak-fluency": {"level": "weak", "errorRate": 0.45, "attempts": 2, "nextReviewDate": _d(-1)},
                "kc-speak-pronunciation": {"level": "ok", "errorRate": 0.33, "attempts": 2, "nextReviewDate": _d(2)},
                "kc-speak-lexical": {"level": "weak", "errorRate": 0.50, "attempts": 1, "nextReviewDate": _d(1)},
                "kc-speak-grammar": {"level": "weak", "errorRate": 0.60, "attempts": 1, "nextReviewDate": _d(1)},
                "kc-speak-coherence": {"level": "weak", "errorRate": 0.0, "attempts": 0, "nextReviewDate": None},
            },
        },
    },
    "vocabulary": {"weakTopics": [], "words": {}},
    "grammar": {"weakPoints": []},
    "testHistory": [],
    "coachNotes": [],
}


# ── Helper: build a profile with specific KC overrides ──────────────
def build_profile_with_kcs(skill: str, overrides: dict[str, dict]) -> dict:
    """Create a copy of PROFILE_ALL_WEAK with specific KC mastery overrides.

    Args:
        skill: One of 'listening', 'reading', 'writing', 'speaking'
        overrides: Dict mapping kc_id -> {level, errorRate, attempts, nextReviewDate}
    """
    import copy
    profile = copy.deepcopy(PROFILE_ALL_WEAK)
    for kc_id, values in overrides.items():
        if kc_id in profile["skills"][skill]["kcMastery"]:
            profile["skills"][skill]["kcMastery"][kc_id].update(values)
    return profile
