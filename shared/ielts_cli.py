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


# ── Commands ───────────────────────────────────────────────────────

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
        # Required top-level fields
        for field in ["version", "learner", "skills", "vocabulary", "grammar", "lessonLibrary", "testHistory", "coachNotes"]:
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

    lesson_count = profile.get("lessonLibrary", {}).get("totalLessons", 0)
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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
