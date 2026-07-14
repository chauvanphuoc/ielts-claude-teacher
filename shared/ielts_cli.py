#!/usr/bin/env python3
"""IELTS Claude Teacher — Data Layer CLI.

Single-file, stdlib-only Python script for managing all IELTS data.
Called by SKILL.md prompts and Claude workflows via Bash.

All data lives in .ielts/ at the project root — never in home directory.

Usage:
  .venv/bin/python3 shared/ielts_cli.py init
  .venv/bin/python3 shared/ielts_cli.py migrate-profile
  .venv/bin/python3 shared/ielts_cli.py settings get
  .venv/bin/python3 shared/ielts_cli.py settings set language en
  .venv/bin/python3 shared/ielts_cli.py status
  .venv/bin/python3 shared/ielts_cli.py backup
  .venv/bin/python3 shared/ielts_cli.py lesson-library list
  .venv/bin/python3 shared/ielts_cli.py lesson-library sync
  .venv/bin/python3 shared/ielts_cli.py lesson-library add --id ... --title ... --skill ... --file ...
  .venv/bin/python3 shared/ielts_cli.py lesson-library mark-used --id ...
  .venv/bin/python3 shared/ielts_cli.py migrate-lesson-library
  .venv/bin/python3 shared/ielts_cli.py reset-profile --yes
"""

import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, date, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
# Resolve project root: this file lives at shared/ielts_cli.py
CLI_FILE = Path(__file__).resolve()
PROJECT_ROOT = CLI_FILE.parent.parent
IELTS_DIR = PROJECT_ROOT / ".ielts"
BACKUP_DIR = IELTS_DIR / "backup"
ARCHIVE_DIR = IELTS_DIR / "archive"

ROADMAP_FILE = IELTS_DIR / "roadmap.json"
PROFILE_FILE = IELTS_DIR / "student-profile.json"
KC_GRAPH_FILE = IELTS_DIR / "kc-graph-ielts.json"
SETTINGS_FILE = IELTS_DIR / "settings.json"
LESSON_LIBRARY_FILE = IELTS_DIR / "lesson-library.json"
LESSON_PLANS_DIR = IELTS_DIR / "lesson-plans"


# ── Utilities ──────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_json(path: Path, data):
    _ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)  # atomic on same filesystem


def _backup_file(path: Path):
    """Create a timestamped backup of a file before modifying it."""
    if not path.exists():
        return None
    _ensure_dir(BACKUP_DIR)
    stem = path.stem
    backup_path = BACKUP_DIR / f"{stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(path, backup_path)
    return backup_path


# ── Lesson Library Helpers ─────────────────────────────────────────

def _scan_lesson_html(filepath: Path) -> dict | None:
    """Extract lesson metadata from an HTML file.

    Reads <title> for the lesson title, looks for <meta name="kc-tags">
    for KC tags, and infers skill from filename or KC tag prefixes.
    Returns None if the file can't be read or isn't a lesson.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(4096)  # first 4KB is enough for head
    except (IOError, OSError):
        return None

    # Extract title from <title> tag
    import re
    title_match = re.search(r"<title>(.*?)</title>", content)
    title = title_match.group(1).strip() if title_match else filepath.stem

    # Strip the " — IELTS Claude Teacher" suffix
    title = re.sub(r"\s*[—–-]\s*IELTS Claude Teacher\s*$", "", title)

    # Extract KC tags from <meta name="kc-tags">
    kc_match = re.search(r'<meta\s+name="kc-tags"\s+content="([^"]*)"', content)
    kc_tags = []
    if kc_match:
        kc_tags = [t.strip() for t in kc_match.group(1).split(",") if t.strip()]

    # Infer skill from KC tags or filename
    skill = "general"
    if kc_tags:
        for tag in kc_tags:
            if tag.startswith("kc-read"):
                skill = "reading"; break
            elif tag.startswith("kc-listen"):
                skill = "listening"; break
            elif tag.startswith("kc-write"):
                skill = "writing"; break
            elif tag.startswith("kc-speak"):
                skill = "speaking"; break
    else:
        # Infer from filename
        name_lower = filepath.stem.lower()
        if "writing" in name_lower:
            skill = "writing"
        elif "listening" in name_lower:
            skill = "listening"
        elif "speaking" in name_lower:
            skill = "speaking"
        elif "reading" in name_lower:
            skill = "reading"
        elif "diagnostic" in name_lower:
            skill = "general"
        elif "dashboard" in name_lower:
            skill = "general"

    # Extract creation date from filename pattern: *-YYYYMMDD-*.html
    date_match = re.search(r"(\d{4})(\d{2})(\d{2})", filepath.stem)
    if date_match:
        created_at = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}T12:00:00Z"
    else:
        # Fall back to file modification time
        from datetime import timezone
        mtime = filepath.stat().st_mtime
        created_at = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lesson_id = filepath.stem

    return {
        "id": lesson_id,
        "title": title,
        "kcTags": kc_tags,
        "skill": skill,
        "file": str(filepath.relative_to(PROJECT_ROOT)),
        "createdAt": created_at,
        "source": "generated",
        "timesUsed": 0,
        "lastUsed": None
    }


# ── Commands ───────────────────────────────────────────────────────

def _build_fresh_profile(kc_graph: dict | None, target_band: float = 0, exam_date: str | None = None) -> dict:
    """Build a fresh student-profile.json v2.0.0 from a KC graph.

    Used by both cmd_migrate_profile (full migration path) and
    cmd_reset_profile. Returns a complete profile dict with all KCs
    at default state (weak, 0 attempts).
    """
    learner = {
        "targetBand": target_band,
        "examDate": exam_date,
        "activeSkills": ["listening", "reading", "writing", "speaking"],
        "startedAt": _now(),
        "lastSessionAt": _now(),
        "sessionsCompleted": 0,
        "diagnosticCompleted": False
    }

    skills = {}
    for skill_name in ["listening", "reading", "writing", "speaking"]:
        skills[skill_name] = {
            "currentBand": 0,
            "bandHistory": [],
            "practiceCount": 0,
            "lastPracticeDate": None,
            "kcMastery": {}
        }

    # Populate kcMastery from KC graph
    if kc_graph:
        for skill_name in ["listening", "reading", "writing", "speaking"]:
            skill_kcs = kc_graph.get("skills", {}).get(skill_name, {}).get("kcs", [])
            for kc in skill_kcs:
                skills[skill_name]["kcMastery"][kc["id"]] = {
                    "level": "weak",
                    "errorRate": 0.0,
                    "attempts": 0,
                    "lastTested": None,
                    "nextReviewDate": None
                }

    profile = {
        "version": "2.0.0",
        "learner": learner,
        "skills": skills,
        "vocabulary": {
            "misspelledWords": [],
            "weakTopics": [],
            "lastVocabReview": None
        },
        "grammar": {
            "weakPoints": []
        },
        "testHistory": [],
        "crossSkillPatterns": [],
        "coachNotes": [
            {
                "date": _now(),
                "category": "system",
                "skill": "general",
                "content": "Fresh profile created via reset.",
                "priority": "low"
            }
        ]
    }

    return profile


def cmd_init():
    """Initialize .ielts/ directory structure."""
    dirs = [
        IELTS_DIR,
        BACKUP_DIR,
        ARCHIVE_DIR,
        IELTS_DIR / "lesson-plans",
        IELTS_DIR / "listening",
        IELTS_DIR / "reading",
        IELTS_DIR / "writing",
        IELTS_DIR / "speaking",
        IELTS_DIR / "listening" / "archive",
        IELTS_DIR / "reading" / "archive",
        IELTS_DIR / "writing" / "archive",
        IELTS_DIR / "speaking" / "archive",
    ]
    for d in dirs:
        _ensure_dir(d)

    # Create settings.json if missing
    if not SETTINGS_FILE.exists():
        _save_json(SETTINGS_FILE, {
            "language": "vi",
            "availableLanguages": ["vi", "en", "zh"],
            "teacherName": "Claude",
            "teacherPersonality": "encouraging"
        })

    # Create roadmap.json if missing (minimal starting state)
    if not ROADMAP_FILE.exists():
        _save_json(ROADMAP_FILE, {
            "version": "1.0.0",
            "learner": {
                "targetBand": 0,
                "examDate": None,
                "activeSkills": ["listening", "reading", "writing", "speaking"],
                "startedAt": _now(),
                "lastSessionAt": _now()
            },
            "skills": {
                "listening": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None},
                "reading": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None},
                "writing": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None},
                "speaking": {"currentBand": 0, "bandHistory": [], "weakAreas": [], "practiceCount": 0, "lastPracticeDate": None}
            },
            "history": [],
            "crossSkillPatterns": [],
            "coachNotes": []
        })

    # Create lesson-library.json if missing (separate from student profile —
    # survives profile resets, protects the self-reinforcing learning loop)
    if not LESSON_LIBRARY_FILE.exists():
        _save_json(LESSON_LIBRARY_FILE, {
            "version": "1.0.0",
            "totalLessons": 0,
            "lessons": []
        })

    print(json.dumps({"status": "ok", "message": "IELTS data directory initialized", "path": str(IELTS_DIR)}))
    return 0


def cmd_migrate_profile():
    """Migrate old roadmap.json → new student-profile.json.

    If student-profile.json already exists: only ADD new KCs from KC graph
    without overwriting existing mastery data. Preserves all test history,
    lesson library, vocabulary, grammar, and coach notes.

    If student-profile.json does not exist: full migration from roadmap.json.

    Creates backup before modifying.
    """
    if not ROADMAP_FILE.exists():
        print(json.dumps({"status": "error", "message": f"{ROADMAP_FILE} not found. Run init first."}))
        return 1

    old = _load_json(ROADMAP_FILE)
    if not old:
        print(json.dumps({"status": "error", "message": "roadmap.json is empty or corrupt."}))
        return 1

    kc_graph = _load_json(KC_GRAPH_FILE)

    # ── Incremental mode: profile exists, only sync new KCs ──
    if PROFILE_FILE.exists():
        profile = _load_json(PROFILE_FILE)
        if not profile:
            print(json.dumps({"status": "error", "message": "student-profile.json is corrupt."}))
            return 1

        _backup_file(PROFILE_FILE)
        kcs_added = 0

        for skill_name in ["listening", "reading", "writing", "speaking"]:
            skill_kcs = kc_graph.get("skills", {}).get(skill_name, {}).get("kcs", []) if kc_graph else []
            if skill_name not in profile["skills"]:
                profile["skills"][skill_name] = {"currentBand": 0, "bandHistory": [], "practiceCount": 0, "lastPracticeDate": None, "kcMastery": {}}
            if "kcMastery" not in profile["skills"][skill_name]:
                profile["skills"][skill_name]["kcMastery"] = {}

            mastery = profile["skills"][skill_name]["kcMastery"]
            for kc in skill_kcs:
                if kc["id"] not in mastery:
                    mastery[kc["id"]] = {
                        "level": "weak",
                        "errorRate": 0.0,
                        "attempts": 0,
                        "lastTested": None,
                        "nextReviewDate": None
                    }
                    kcs_added += 1

        _save_json(PROFILE_FILE, profile)

        result = {
            "status": "ok",
            "message": f"Incremental sync: {kcs_added} new KCs added",
            "mode": "incremental",
            "profile": str(PROFILE_FILE),
            "summary": {
                "kcsAdded": kcs_added,
                "totalKCs": sum(len(profile["skills"][s].get("kcMastery", {})) for s in profile["skills"]),
                "testHistoryPreserved": len(profile.get("testHistory", [])),
                "diagnosticPreserved": profile["learner"].get("diagnosticCompleted", False)
            }
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # ── Full migration mode: no profile exists yet ──
    backup_path = _backup_file(ROADMAP_FILE)

    # ── Build new student profile ──────────────────────────────────
    old_learner = old.get("learner", {})
    old_skills = old.get("skills", {})
    old_coach = old.get("coachNotes", [])

    # Map learner section
    learner = {
        "targetBand": old_learner.get("targetBand", 0),
        "examDate": old_learner.get("examDate"),
        "activeSkills": old_learner.get("activeSkills", ["listening", "reading", "writing", "speaking"]),
        "startedAt": old_learner.get("startedAt", _now()),
        "lastSessionAt": old_learner.get("lastSessionAt", _now()),
        "sessionsCompleted": len(old.get("history", [])),
        "diagnosticCompleted": False
    }

    # Map each skill
    skills = {}
    for skill_name in ["listening", "reading", "writing", "speaking"]:
        old_skill = old_skills.get(skill_name, {})
        skills[skill_name] = {
            "currentBand": old_skill.get("currentBand", 0),
            "bandHistory": old_skill.get("bandHistory", []),
            "practiceCount": old_skill.get("practiceCount", 0),
            "lastPracticeDate": old_skill.get("lastPracticeDate"),
            "kcMastery": {}  # no old data — starts empty
        }

    # Convert old weakAreas → coachNotes
    weak_area_notes = []
    for skill_name, skill_data in old_skills.items():
        for area in skill_data.get("weakAreas", []):
            weak_area_notes.append({
                "date": _now(),
                "category": "observation",
                "skill": skill_name,
                "content": f"[Migrated from roadmap.json] Previously identified weak area: {area}",
                "priority": "medium"
            })

    # Map old coachNotes + add migration entry
    migration_note = {
        "date": _now(),
        "category": "system",
        "skill": "general",
        "content": f"Migrated from roadmap.json v{old.get('version', '1.0.0')} to student-profile.json v2.0.0. Backup: {backup_path.name if backup_path else 'none'}",
        "priority": "low"
    }
    coach_notes = [migration_note] + old_coach + weak_area_notes

    # Build new profile
    profile = {
        "version": "2.0.0",
        "learner": learner,
        "skills": skills,
        "vocabulary": {
            "misspelledWords": [],
            "weakTopics": [],
            "lastVocabReview": None
        },
        "grammar": {
            "weakPoints": []
        },
        "lessonLibrary": {
            "totalLessons": 0,
            "lessons": []
        },
        "testHistory": [],
        "crossSkillPatterns": [],
        "coachNotes": coach_notes
    }

    # Load KC graph for initial kcMastery population
    kc_graph = _load_json(KC_GRAPH_FILE)
    if kc_graph:
        for skill_name in ["listening", "reading", "writing", "speaking"]:
            skill_kcs = kc_graph.get("skills", {}).get(skill_name, {}).get("kcs", [])
            for kc in skill_kcs:
                skills[skill_name]["kcMastery"][kc["id"]] = {
                    "level": "weak",        # default — no data yet
                    "errorRate": 0.0,
                    "attempts": 0,
                    "lastTested": None,
                    "nextReviewDate": None  # for spaced repetition
                }

    # Write new profile
    _save_json(PROFILE_FILE, profile)

    result = {
        "status": "ok",
        "message": "Migration complete",
        "backup": str(backup_path) if backup_path else None,
        "profile": str(PROFILE_FILE),
        "summary": {
            "targetBand": learner["targetBand"],
            "sessionsCompleted": learner["sessionsCompleted"],
            "kcMasteryEntries": sum(len(skills[s]["kcMastery"]) for s in skills),
            "coachNotesMigrated": len(old_coach),
            "weakAreasConverted": len(weak_area_notes)
        }
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_settings_get():
    """Read and output settings.json."""
    settings = _load_json(SETTINGS_FILE, {
        "language": "vi",
        "availableLanguages": ["vi", "en", "zh"],
        "teacherName": "Claude",
        "teacherPersonality": "encouraging"
    })
    print(json.dumps(settings, ensure_ascii=False, indent=2))
    return 0


def cmd_settings_set(args):
    """Update settings fields."""
    settings = _load_json(SETTINGS_FILE, {
        "language": "vi",
        "availableLanguages": ["vi", "en", "zh"],
        "teacherName": "Claude",
        "teacherPersonality": "encouraging"
    })

    settable = ["language", "teacherName", "teacherPersonality"]
    updated = False

    for key in settable:
        val = getattr(args, key, None)
        if val is not None:
            if key == "language" and val not in settings.get("availableLanguages", []):
                print(json.dumps({"status": "error", "message": f"Language '{val}' not available. Options: {settings.get('availableLanguages')}"}))
                return 1
            settings[key] = val
            updated = True

    if updated:
        _save_json(SETTINGS_FILE, settings)

    print(json.dumps({"status": "ok", "settings": settings}, ensure_ascii=False))
    return 0


def cmd_validate():
    """Validate data integrity: profile schema, KC cross-references, errorRate formula."""
    errors = []
    warnings = []

    profile = _load_json(PROFILE_FILE)
    kc_graph = _load_json(KC_GRAPH_FILE)

    # ── Profile existence ──
    if not profile:
        errors.append("student-profile.json not found. Run migrate-profile first.")
    else:
        # Required top-level fields (lessonLibrary moved to standalone lesson-library.json)
        for field in ["version", "learner", "skills", "vocabulary", "grammar", "testHistory", "coachNotes"]:
            if field not in profile:
                errors.append(f"student-profile.json missing field: {field}")

        # Learner fields
        learner = profile.get("learner", {})
        for field in ["targetBand", "activeSkills", "startedAt"]:
            if field not in learner:
                errors.append(f"learner missing: {field}")

        # Skill consistency
        for skill_name in ["listening", "reading", "writing", "speaking"]:
            if skill_name not in profile.get("skills", {}):
                errors.append(f"skills missing: {skill_name}")
                continue
            skill = profile["skills"][skill_name]
            for field in ["currentBand", "bandHistory", "practiceCount", "kcMastery"]:
                if field not in skill:
                    errors.append(f"skills.{skill_name} missing: {field}")

    # ── KC graph integrity ──
    if not kc_graph:
        warnings.append("kc-graph-ielts.json not found. KC cross-reference check skipped.")
    elif profile:
        all_kc_ids = set()
        for skill_name, skill_data in kc_graph.get("skills", {}).items():
            for kc in skill_data.get("kcs", []):
                all_kc_ids.add(kc["id"])

        # Check kcMastery tags exist in KC graph
        for skill_name, skill_data in profile.get("skills", {}).items():
            for kc_id in skill_data.get("kcMastery", {}):
                if kc_id not in all_kc_ids:
                    errors.append(f"Orphaned KC tag in kcMastery: '{kc_id}' not found in KC graph")

        # Check level = derived from errorRate
        for skill_name, skill_data in profile.get("skills", {}).items():
            for kc_id, kc_data in skill_data.get("kcMastery", {}).items():
                error_rate = kc_data.get("errorRate", 0)
                stored_level = kc_data.get("level", "")
                if error_rate >= 0.40 and stored_level != "weak":
                    errors.append(f"skills.{skill_name}.kcMastery.{kc_id}: errorRate={error_rate} should derive to 'weak', got '{stored_level}'")
                elif 0.15 <= error_rate < 0.40 and stored_level != "ok":
                    errors.append(f"skills.{skill_name}.kcMastery.{kc_id}: errorRate={error_rate} should derive to 'ok', got '{stored_level}'")
                elif error_rate < 0.15 and stored_level != "mastered" and error_rate > 0:
                    errors.append(f"skills.{skill_name}.kcMastery.{kc_id}: errorRate={error_rate} should derive to 'mastered', got '{stored_level}'")

    result = {
        "status": "ok" if not errors else "issues_found",
        "errors": errors,
        "warnings": warnings
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def cmd_reset_profile(args):
    """Reset student-profile.json to factory-fresh state.

    Backs up current profile (if exists), then writes a fresh v2.0.0
    profile with all KCs at default state. Cleans up legacy auxiliary
    files and transient test results. Does NOT touch lesson-library.json
    or lesson-plans/ — the teaching library survives resets.

    Requires --yes flag to confirm (one-way door — data cannot be
    recovered except from backup).
    """
    if not getattr(args, 'yes', False):
        print(json.dumps({
            "status": "blocked",
            "message": "Reset requires --yes flag. This is a one-way operation. "
                       "Your current profile will be backed up to .ielts/backup/."
        }, ensure_ascii=False))
        return 1

    kc_graph = _load_json(KC_GRAPH_FILE)
    if not kc_graph:
        print(json.dumps({
            "status": "error",
            "message": f"{KC_GRAPH_FILE} not found. Cannot build fresh profile without KC graph."
        }, ensure_ascii=False))
        return 1

    # ── Backup current profile ──
    backup_path = None
    if PROFILE_FILE.exists():
        backup_path = _backup_file(PROFILE_FILE)
        old_profile = _load_json(PROFILE_FILE)
        old_target = (old_profile or {}).get("learner", {}).get("targetBand", 0)
        old_exam = (old_profile or {}).get("learner", {}).get("examDate")
    else:
        old_target = 0
        old_exam = None

    # Preserve target band and exam date from args or old profile
    target_band = getattr(args, 'target_band', None)
    if target_band is None:
        target_band = old_target
    exam_date = getattr(args, 'exam_date', None)
    if exam_date is None:
        exam_date = old_exam

    # ── Build and save fresh profile ──
    profile = _build_fresh_profile(kc_graph, target_band, exam_date)

    # Add reset note to coach notes
    profile["coachNotes"].insert(0, {
        "date": _now(),
        "category": "system",
        "skill": "general",
        "content": f"Profile reset. Backup: {backup_path.name if backup_path else 'none'}",
        "priority": "high"
    })

    _save_json(PROFILE_FILE, profile)

    # ── Cleanup legacy files ──
    legacy_files = [
        IELTS_DIR / "roadmap.json",
        IELTS_DIR / "config.json",
        IELTS_DIR / "progress.json",
        IELTS_DIR / "memories.json",
        IELTS_DIR / "errors.json",
        IELTS_DIR / "vocab.json",
        IELTS_DIR / "synonyms.json",
    ]
    cleaned_legacy = []
    for fp in legacy_files:
        if fp.exists():
            try:
                fp.unlink()
                cleaned_legacy.append(fp.name)
            except OSError:
                pass

    # ── Clear transient latest.json files ──
    transient_skills = ["listening", "reading", "writing", "speaking"]
    cleaned_transient = []
    for skill in transient_skills:
        skill_dir = IELTS_DIR / skill
        if not skill_dir.exists():
            continue
        # Clear latest.json
        latest = skill_dir / "latest.json"
        if latest.exists():
            try:
                latest.unlink()
                cleaned_transient.append(f"{skill}/latest.json")
            except OSError:
                pass
        # Clear latest.webm (speaking)
        latest_webm = skill_dir / "latest.webm"
        if latest_webm.exists():
            try:
                latest_webm.unlink()
                cleaned_transient.append(f"{skill}/latest.webm")
            except OSError:
                pass
        # Clear archive directory
        archive_dir = skill_dir / "archive"
        if archive_dir.exists():
            try:
                for af in archive_dir.iterdir():
                    if af.is_file():
                        af.unlink()
                cleaned_transient.append(f"{skill}/archive/*")
            except OSError:
                pass

    # ── Report ──
    total_kcs = sum(len(profile["skills"][s]["kcMastery"]) for s in profile["skills"])
    result = {
        "status": "ok",
        "message": "Profile reset complete. Diagnostic will run on next session.",
        "backup": str(backup_path) if backup_path else None,
        "profile": str(PROFILE_FILE),
        "summary": {
            "targetBand": target_band,
            "diagnosticCompleted": False,
            "totalKCs": total_kcs,
            "lessonLibraryPreserved": LESSON_LIBRARY_FILE.exists(),
            "cleanedLegacy": cleaned_legacy,
            "cleanedTransient": cleaned_transient
        }
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backup():
    """Create a zip backup of .ielts/."""
    output = PROJECT_ROOT / f"ielts-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(IELTS_DIR):
            for f in files:
                fp = Path(root) / f
                arcname = fp.relative_to(IELTS_DIR.parent)
                zf.write(fp, arcname)

    print(json.dumps({"status": "ok", "path": str(output), "size": output.stat().st_size}))
    return 0


# ── Lesson Library Commands ─────────────────────────────────────────

def cmd_lesson_library_list():
    """List all lessons in the library."""
    lib = _load_json(LESSON_LIBRARY_FILE)
    if not lib:
        print(json.dumps({"status": "ok", "totalLessons": 0, "lessons": []}))
        return 0

    # Verify each lesson's HTML file still exists
    available = []
    missing = []
    for lesson in lib.get("lessons", []):
        fp = PROJECT_ROOT / lesson["file"]
        if fp.exists():
            available.append(lesson)
        else:
            missing.append(lesson["id"])

    result = {
        "status": "ok",
        "totalLessons": len(available),
        "lessons": available
    }
    if missing:
        result["warnings"] = [f"File missing for: {', '.join(missing)}"]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_lesson_library_add(args):
    """Add a lesson entry to the library."""
    lib = _load_json(LESSON_LIBRARY_FILE, {"version": "1.0.0", "totalLessons": 0, "lessons": []})

    # Parse KC tags
    kc_tags = []
    if args.kc_tags:
        kc_tags = [t.strip() for t in args.kc_tags.split(",")]

    lesson = {
        "id": args.id,
        "title": args.title,
        "kcTags": kc_tags,
        "skill": args.skill,
        "file": args.file,
        "createdAt": args.date if args.date else _now(),
        "source": args.source if args.source else "generated",
        "timesUsed": 0,
        "lastUsed": None
    }

    # Add triggerError if provided
    if hasattr(args, 'trigger_error') and args.trigger_error:
        lesson["triggerError"] = args.trigger_error

    # Check for duplicates
    existing_ids = {l["id"] for l in lib["lessons"]}
    if lesson["id"] in existing_ids:
        # Update existing entry
        for i, l in enumerate(lib["lessons"]):
            if l["id"] == lesson["id"]:
                lib["lessons"][i] = lesson
                break
        action = "updated"
    else:
        lib["lessons"].append(lesson)
        action = "added"

    lib["totalLessons"] = len(lib["lessons"])
    _save_json(LESSON_LIBRARY_FILE, lib)

    print(json.dumps({"status": "ok", "action": action, "id": lesson["id"], "totalLessons": lib["totalLessons"]}, ensure_ascii=False))
    return 0


def cmd_lesson_library_mark_used(args):
    """Increment timesUsed for a lesson."""
    lib = _load_json(LESSON_LIBRARY_FILE)
    if not lib:
        print(json.dumps({"status": "error", "message": "lesson-library.json not found. Run init first."}))
        return 1

    for lesson in lib["lessons"]:
        if lesson["id"] == args.id:
            lesson["timesUsed"] = lesson.get("timesUsed", 0) + 1
            lesson["lastUsed"] = _today()
            _save_json(LESSON_LIBRARY_FILE, lib)
            print(json.dumps({"status": "ok", "id": args.id, "timesUsed": lesson["timesUsed"], "lastUsed": lesson["lastUsed"]}, ensure_ascii=False))
            return 0

    print(json.dumps({"status": "error", "message": f"Lesson '{args.id}' not found in library."}))
    return 1


def cmd_lesson_library_sync():
    """Scan .ielts/lesson-plans/ and rebuild lesson-library.json.

    Preserves usage stats (timesUsed, lastUsed) for existing lessons.
    Adds new lessons found on disk. Warns about lessons in the library
    whose HTML files no longer exist.
    """
    lib = _load_json(LESSON_LIBRARY_FILE, {"version": "1.0.0", "totalLessons": 0, "lessons": []})

    # Build lookup of existing lessons by id
    existing = {}
    for l in lib["lessons"]:
        existing[l["id"]] = l

    # Scan disk
    new_lessons = []
    disk_ids = set()

    if LESSON_PLANS_DIR.exists():
        for fp in sorted(LESSON_PLANS_DIR.glob("*.html")):
            meta = _scan_lesson_html(fp)
            if meta is None:
                continue

            disk_ids.add(meta["id"])

            if meta["id"] in existing:
                # Preserve usage stats
                old = existing[meta["id"]]
                meta["timesUsed"] = old.get("timesUsed", 0)
                meta["lastUsed"] = old.get("lastUsed")
                # Update KC tags if newly discovered
                if not meta["kcTags"] and old.get("kcTags"):
                    meta["kcTags"] = old["kcTags"]
                if meta["skill"] == "general" and old.get("skill", "general") != "general":
                    meta["skill"] = old["skill"]
            else:
                # New lesson found on disk
                pass

            new_lessons.append(meta)
    else:
        _ensure_dir(LESSON_PLANS_DIR)

    # Check for orphaned entries (in library but file missing)
    orphaned = set(existing.keys()) - disk_ids
    warnings = []
    if orphaned:
        warnings.append(f"Orphaned entries (file missing): {', '.join(sorted(orphaned))}")

    lib["lessons"] = new_lessons
    lib["totalLessons"] = len(new_lessons)
    _save_json(LESSON_LIBRARY_FILE, lib)

    result = {
        "status": "ok",
        "totalLessons": lib["totalLessons"],
        "added": len(disk_ids - set(existing.keys())),
        "preserved": len(disk_ids & set(existing.keys())),
        "orphaned": len(orphaned)
    }
    if warnings:
        result["warnings"] = warnings

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_migrate_lesson_library():
    """One-time migration: extract lessonLibrary from student-profile.json
    and write to standalone lesson-library.json. Removes lessonLibrary
    from student-profile.json after successful migration.
    """
    profile = _load_json(PROFILE_FILE)
    if not profile:
        print(json.dumps({"status": "error", "message": "student-profile.json not found."}))
        return 1

    old_library = profile.get("lessonLibrary")
    if old_library is None:
        print(json.dumps({"status": "ok", "message": "No lessonLibrary in student-profile.json. Nothing to migrate."}))
        return 0

    # Backup both files
    _backup_file(PROFILE_FILE)
    if LESSON_LIBRARY_FILE.exists():
        _backup_file(LESSON_LIBRARY_FILE)

    # Write standalone lesson library
    lib = {
        "version": "1.0.0",
        "totalLessons": old_library.get("totalLessons", len(old_library.get("lessons", []))),
        "lessons": old_library.get("lessons", [])
    }
    _save_json(LESSON_LIBRARY_FILE, lib)

    # Remove lessonLibrary from profile
    del profile["lessonLibrary"]
    _save_json(PROFILE_FILE, profile)

    # Now sync from disk to find any orphaned lessons
    sync_result = json.loads(json.dumps({"status": "ok"}))  # placeholder
    # Run sync to pick up lessons on disk that weren't tracked
    if LESSON_PLANS_DIR.exists():
        disk_count = len(list(LESSON_PLANS_DIR.glob("*.html")))
    else:
        disk_count = 0

    print(json.dumps({
        "status": "ok",
        "message": "Lesson library migrated to standalone file",
        "migrated": lib["totalLessons"],
        "filesOnDisk": disk_count,
        "note": "Run 'lesson-library sync' to scan disk for orphaned lessons"
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_status():
    """Output a brief status summary."""
    profile = _load_json(PROFILE_FILE)
    settings = _load_json(SETTINGS_FILE)

    if not profile:
        print("IELTS: run 'migrate-profile' to set up")
        return 0

    learner = profile.get("learner", {})
    skills = profile.get("skills", {})
    lang = (settings or {}).get("language", "vi")

    parts = []
    target = learner.get("targetBand", 0)
    if target:
        parts.append(f"🎯 {target}")

    for s in ["reading", "listening", "speaking", "writing"]:
        band = skills.get(s, {}).get("currentBand", 0)
        if band:
            parts.append(f"{s[0].upper()}:{band}")

    sessions = learner.get("sessionsCompleted", 0)
    if sessions:
        parts.append(f"📚 {sessions} sessions")

    lesson_lib = _load_json(LESSON_LIBRARY_FILE)
    lesson_count = (lesson_lib or {}).get("totalLessons", 0) if lesson_lib else 0
    if lesson_count:
        parts.append(f"📝 {lesson_count} lessons")

    print("IELTS " + " · ".join(parts) if parts else "IELTS: ready")
    return 0


# ── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="IELTS Claude Teacher — Data Layer CLI")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sub.add_parser("init", help="Initialize .ielts/ directory structure")

    # migrate-profile
    sub.add_parser("migrate-profile", help="Migrate roadmap.json → student-profile.json v2")

    # validate
    sub.add_parser("validate", help="Validate data integrity (profile + KC graph)")

    # settings
    p_settings = sub.add_parser("settings", help="Settings management")
    p_settings_sub = p_settings.add_subparsers(dest="settings_action")
    p_settings_sub.add_parser("get", help="Read settings")
    p_set = p_settings_sub.add_parser("set", help="Update settings")
    p_set.add_argument("--language", choices=["vi", "en", "zh"])
    p_set.add_argument("--teacher-name")
    p_set.add_argument("--teacher-personality")

    # backup
    sub.add_parser("backup", help="Create zip backup of .ielts/")

    # status
    sub.add_parser("status", help="Show brief status summary")

    # lesson-library
    p_ll = sub.add_parser("lesson-library", help="Lesson library management")
    p_ll_sub = p_ll.add_subparsers(dest="ll_action")
    p_ll_sub.add_parser("list", help="List all lessons")
    p_ll_sub.add_parser("sync", help="Scan lesson-plans/ and rebuild library")
    p_ll_add = p_ll_sub.add_parser("add", help="Add a lesson entry")
    p_ll_add.add_argument("--id", required=True, help="Lesson ID (e.g., lesson-20260713-001)")
    p_ll_add.add_argument("--title", required=True, help="Lesson title")
    p_ll_add.add_argument("--skill", required=True, choices=["reading", "listening", "writing", "speaking", "general"])
    p_ll_add.add_argument("--file", required=True, help="Relative path to HTML file")
    p_ll_add.add_argument("--kc-tags", help="Comma-separated KC tag IDs")
    p_ll_add.add_argument("--date", help="Creation date (ISO format)")
    p_ll_add.add_argument("--source", help="Source (generated/cambridge/manual)")
    p_ll_add.add_argument("--trigger-error", help="Error that triggered this lesson")
    p_ll_mark = p_ll_sub.add_parser("mark-used", help="Increment timesUsed for a lesson")
    p_ll_mark.add_argument("--id", required=True, help="Lesson ID")

    # reset-profile
    p_reset = sub.add_parser("reset-profile", help="Factory reset student-profile.json to initial state")
    p_reset.add_argument("--yes", action="store_true", help="Confirm reset (required — one-way operation)")
    p_reset.add_argument("--target-band", type=float, help="Target band for new profile (default: preserve from old)")
    p_reset.add_argument("--exam-date", help="Exam date for new profile (default: preserve from old)")

    # migrate-lesson-library (one-time)
    sub.add_parser("migrate-lesson-library", help="Migrate lessonLibrary from student-profile.json to standalone file")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init":
        return cmd_init()
    elif args.command == "migrate-profile":
        return cmd_migrate_profile()
    elif args.command == "validate":
        return cmd_validate()
    elif args.command == "settings":
        if args.settings_action == "get":
            return cmd_settings_get()
        elif args.settings_action == "set":
            return cmd_settings_set(args)
        else:
            print("Usage: ielts_cli.py settings [get|set]")
            return 1
    elif args.command == "backup":
        return cmd_backup()
    elif args.command == "status":
        return cmd_status()
    elif args.command == "lesson-library":
        if args.ll_action == "list":
            return cmd_lesson_library_list()
        elif args.ll_action == "sync":
            return cmd_lesson_library_sync()
        elif args.ll_action == "add":
            return cmd_lesson_library_add(args)
        elif args.ll_action == "mark-used":
            return cmd_lesson_library_mark_used(args)
        else:
            print("Usage: ielts_cli.py lesson-library [list|sync|add|mark-used]")
            return 1
    elif args.command == "reset-profile":
        return cmd_reset_profile(args)
    elif args.command == "migrate-lesson-library":
        return cmd_migrate_lesson_library()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
