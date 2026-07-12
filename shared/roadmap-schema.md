# Roadmap Schema — Calibration Examples

Three example learner states for validating the roadmap.json schema.

## Example 1: Band 5.0 Learner (early stage)

```json
{
  "version": "1.0.0",
  "learner": {
    "targetBand": 7.0,
    "examDate": "2026-12-15",
    "activeSkills": ["writing", "reading", "listening"],
    "startedAt": "2026-07-01T10:00:00Z",
    "lastSessionAt": "2026-07-12T14:30:00Z"
  },
  "skills": {
    "writing": {
      "currentBand": 5.0,
      "bandHistory": [
        {"date": "2026-07-01", "band": 4.5, "source": "initial diagnostic essay"},
        {"date": "2026-07-08", "band": 5.0, "source": "Cambridge 1 Test 1 Task 2"}
      ],
      "weakAreas": [
        {"tag": "TR-main-ideas", "errorRate": 0.7, "lastSeen": "2026-07-08", "trend": "stable"},
        {"tag": "CC-paragraphing", "errorRate": 0.6, "lastSeen": "2026-07-01", "trend": "improving"}
      ],
      "practiceCount": 2,
      "lastPracticeDate": "2026-07-08"
    },
    "reading": {
      "currentBand": 5.5,
      "bandHistory": [{"date": "2026-07-05", "band": 5.5, "source": "Cambridge 1 Test 1"}],
      "weakAreas": [
        {"tag": "T/F/NG", "errorRate": 0.5, "lastSeen": "2026-07-05", "trend": "stable"},
        {"tag": "headings-matching", "errorRate": 0.6, "lastSeen": "2026-07-05", "trend": "stable"}
      ],
      "practiceCount": 1,
      "lastPracticeDate": "2026-07-05"
    },
    "listening": {
      "currentBand": 5.0,
      "bandHistory": [{"date": "2026-07-03", "band": 5.0, "source": "Cambridge 1 Test 1"}],
      "weakAreas": [
        {"tag": "spelling", "errorRate": 0.4, "lastSeen": "2026-07-03", "trend": "stable"},
        {"tag": "MC-distractors", "errorRate": 0.6, "lastSeen": "2026-07-03", "trend": "stable"}
      ],
      "practiceCount": 1,
      "lastPracticeDate": "2026-07-03"
    },
    "speaking": {
      "currentBand": 0,
      "bandHistory": [],
      "weakAreas": [],
      "practiceCount": 0,
      "lastPracticeDate": null
    }
  },
  "history": [
    {"date": "2026-07-01T10:00:00Z", "skill": "writing", "activity": "essay-submit", "scores": {"TR": 4.5, "CC": 5.0, "LR": 4.5, "GRA": 4.5}, "duration": 45, "sourceMaterial": "diagnostic"},
    {"date": "2026-07-03T11:00:00Z", "skill": "listening", "activity": "test-complete", "scores": {"correct": 20, "total": 40, "band": 5.0}, "duration": 40, "sourceMaterial": "Cambridge 1 Test 1"},
    {"date": "2026-07-05T09:00:00Z", "skill": "reading", "activity": "test-complete", "scores": {"correct": 23, "total": 40, "band": 5.5}, "duration": 60, "sourceMaterial": "Cambridge 1 Test 1"},
    {"date": "2026-07-08T14:00:00Z", "skill": "writing", "activity": "essay-submit", "scores": {"TR": 5.0, "CC": 5.0, "LR": 5.0, "GRA": 5.0}, "duration": 40, "sourceMaterial": "Cambridge 1 Test 1 Task 2"}
  ],
  "crossSkillPatterns": [
    {
      "id": "csp-001",
      "pattern": "Difficulty distinguishing implied vs stated information",
      "affectedSkills": ["reading", "listening"],
      "evidence": "Reading T/F/NG (50% error) and listening MC distractors (60% error) share the same root: not recognizing when information is implied rather than directly stated.",
      "prescription": "Practice explicitly identifying whether each answer is 'directly stated', 'implied/synonymous', or 'not mentioned'. Start with reading passages, then apply to listening transcripts.",
      "identifiedAt": "2026-07-08",
      "resolvedAt": null
    }
  ],
  "coachNotes": [
    {"date": "2026-07-01T10:00:00Z", "category": "observation", "skill": "writing", "content": "Strong opinions but weak structure. Ideas are good — needs paragraph discipline.", "priority": "high"},
    {"date": "2026-07-05T09:00:00Z", "category": "weakness", "skill": "reading", "content": "T/F/NG questions consistently wrong. Rushes to True/False without checking for Not Given.", "priority": "high"},
    {"date": "2026-07-08T14:30:00Z", "category": "strategy", "skill": "general", "content": "Learning path excludes speaking by choice. Focus all energy on writing, reading, listening.", "priority": "medium"}
  ]
}
```

## Example 2: Band 6.5 Learner (mid-stage)

```json
{
  "version": "1.0.0",
  "learner": {
    "targetBand": 7.5,
    "examDate": "2026-09-01",
    "activeSkills": ["writing", "reading", "listening", "speaking"],
    "startedAt": "2026-04-01T08:00:00Z",
    "lastSessionAt": "2026-07-12T16:00:00Z"
  },
  "skills": {
    "writing": {
      "currentBand": 6.5,
      "bandHistory": [
        {"date": "2026-04-01", "band": 5.5, "source": "diagnostic"},
        {"date": "2026-05-15", "band": 6.0, "source": "practice essay"},
        {"date": "2026-06-20", "band": 6.5, "source": "Cambridge 3 Test 2 Task 2"}
      ],
      "weakAreas": [
        {"tag": "LR-collocations", "errorRate": 0.3, "lastSeen": "2026-06-20", "trend": "improving"},
        {"tag": "GRA-complex-sentences", "errorRate": 0.4, "lastSeen": "2026-06-20", "trend": "stable"}
      ],
      "practiceCount": 12,
      "lastPracticeDate": "2026-06-20"
    },
    "reading": {
      "currentBand": 7.0,
      "bandHistory": [
        {"date": "2026-04-01", "band": 6.0, "source": "diagnostic"},
        {"date": "2026-06-10", "band": 7.0, "source": "Cambridge 2 Test 4"}
      ],
      "weakAreas": [
        {"tag": "sentence-completion", "errorRate": 0.2, "lastSeen": "2026-06-10", "trend": "improving"}
      ],
      "practiceCount": 8,
      "lastPracticeDate": "2026-06-10"
    },
    "listening": {
      "currentBand": 6.5,
      "bandHistory": [
        {"date": "2026-04-01", "band": 6.0, "source": "diagnostic"},
        {"date": "2026-05-20", "band": 6.5, "source": "Cambridge 2 Test 3"}
      ],
      "weakAreas": [
        {"tag": "S4-lecture", "errorRate": 0.35, "lastSeen": "2026-05-20", "trend": "stable"},
        {"tag": "number-dates", "errorRate": 0.15, "lastSeen": "2026-05-20", "trend": "improving"}
      ],
      "practiceCount": 6,
      "lastPracticeDate": "2026-05-20"
    },
    "speaking": {
      "currentBand": 6.0,
      "bandHistory": [
        {"date": "2026-04-01", "band": 5.5, "source": "diagnostic"},
        {"date": "2026-07-10", "band": 6.0, "source": "practice Part 2"}
      ],
      "weakAreas": [
        {"tag": "fluency-hesitation", "errorRate": 0.4, "lastSeen": "2026-07-10", "trend": "improving"},
        {"tag": "lexical-range", "errorRate": 0.35, "lastSeen": "2026-07-10", "trend": "stable"}
      ],
      "practiceCount": 5,
      "lastPracticeDate": "2026-07-10"
    }
  },
  "history": [],
  "crossSkillPatterns": [],
  "coachNotes": [
    {"date": "2026-07-12T16:00:00Z", "category": "strength", "skill": "reading", "content": "Consistently scoring Band 7 on reading. Speed and accuracy both solid.", "priority": "medium"},
    {"date": "2026-07-12T16:00:00Z", "category": "strategy", "skill": "general", "content": "On track for 7.5 by September. Focus on writing GRA complex sentences and speaking fluency.", "priority": "high"}
  ]
}
```

## Example 3: Band 8.0 Learner (advanced)

```json
{
  "version": "1.0.0",
  "learner": {
    "targetBand": 8.5,
    "examDate": "2026-08-01",
    "activeSkills": ["writing", "reading", "listening", "speaking"],
    "startedAt": "2025-09-01T08:00:00Z",
    "lastSessionAt": "2026-07-12T10:00:00Z"
  },
  "skills": {
    "writing": {
      "currentBand": 8.0,
      "bandHistory": [
        {"date": "2025-09-01", "band": 6.5, "source": "diagnostic"},
        {"date": "2026-01-15", "band": 7.5, "source": "practice"},
        {"date": "2026-06-01", "band": 8.0, "source": "Cambridge 5 Test 2 Task 2"}
      ],
      "weakAreas": [
        {"tag": "LR-idiomaticity", "errorRate": 0.15, "lastSeen": "2026-06-01", "trend": "improving"}
      ],
      "practiceCount": 30,
      "lastPracticeDate": "2026-06-01"
    },
    "reading": {
      "currentBand": 8.5,
      "bandHistory": [
        {"date": "2025-09-01", "band": 7.0, "source": "diagnostic"},
        {"date": "2026-03-10", "band": 8.5, "source": "Cambridge 4 Test 3"}
      ],
      "weakAreas": [],
      "practiceCount": 20,
      "lastPracticeDate": "2026-03-10"
    },
    "listening": {
      "currentBand": 8.0,
      "bandHistory": [
        {"date": "2025-09-01", "band": 7.0, "source": "diagnostic"},
        {"date": "2026-04-20", "band": 8.0, "source": "Cambridge 4 Test 2"}
      ],
      "weakAreas": [
        {"tag": "S4-academic-vocab", "errorRate": 0.1, "lastSeen": "2026-04-20", "trend": "improving"}
      ],
      "practiceCount": 18,
      "lastPracticeDate": "2026-04-20"
    },
    "speaking": {
      "currentBand": 7.5,
      "bandHistory": [
        {"date": "2025-09-01", "band": 6.5, "source": "diagnostic"},
        {"date": "2026-05-10", "band": 7.5, "source": "practice full mock"}
      ],
      "weakAreas": [
        {"tag": "pronunciation-stress", "errorRate": 0.2, "lastSeen": "2026-05-10", "trend": "improving"},
        {"tag": "part3-depth", "errorRate": 0.15, "lastSeen": "2026-05-10", "trend": "stable"}
      ],
      "practiceCount": 15,
      "lastPracticeDate": "2026-05-10"
    }
  },
  "history": [],
  "crossSkillPatterns": [
    {
      "id": "csp-002",
      "pattern": "Academic vocabulary depth limits top-band performance",
      "affectedSkills": ["writing", "speaking"],
      "evidence": "Writing LR (8.0) and speaking lexical range (7.5) both plateaued at sub-8.5. The gap is not word count but depth: lacks idiomatic collocations and discipline-specific precision in Part 3/scientific topics.",
      "prescription": "Targeted academic word list practice focused on collocations, not individual words. Read one academic article per week and extract 10 natural collocations. Practice using them in speaking Part 3 answers.",
      "identifiedAt": "2026-06-15",
      "resolvedAt": null
    }
  ],
  "coachNotes": [
    {"date": "2026-07-12T10:00:00Z", "category": "strength", "skill": "reading", "content": "Reading is consistently 8.5. Near-ceiling performance.", "priority": "low"},
    {"date": "2026-07-12T10:00:00Z", "category": "strategy", "skill": "general", "content": "The gap from 8.0 to 8.5 overall is in academic vocabulary depth. Not a knowledge gap — a precision gap.", "priority": "high"}
  ]
}
```
