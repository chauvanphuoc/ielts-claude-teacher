"""Evals configuration loader for IELTS Teacher.

Reads sampling config from .ielts/settings.json and determines
whether a given session should be evaluated by GEval.

Config schema (in .ielts/settings.json):
{
  "evals": {
    "mode": "sampled",        // "always" | "sampled" | "never"
    "sampleRate": 0.25,       // fraction of sessions to evaluate (sampled mode only)
    "minimumIntervalHours": 24 // minimum hours between evals (sampled mode only)
  }
}
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Project root relative to this file (evals/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IELTS_DIR = PROJECT_ROOT / ".ielts"
SETTINGS_FILE = IELTS_DIR / "settings.json"
EVALS_DIR = IELTS_DIR / "quality" / "evals"

DEFAULT_CONFIG = {
    "mode": "sampled",
    "sampleRate": 0.25,
    "minimumIntervalHours": 24,
}


def load_evals_config() -> dict:
    """Load evals section from .ielts/settings.json, merging with defaults."""
    config = dict(DEFAULT_CONFIG)
    if not SETTINGS_FILE.exists():
        return config

    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        user_evals = settings.get("evals", {})
        if isinstance(user_evals, dict):
            config.update(user_evals)
    except (json.JSONDecodeError, IOError, OSError):
        pass

    return config


def should_evaluate(run_id: str, config: dict | None = None) -> bool:
    """Determine whether this session should be evaluated by GEval.

    Args:
        run_id: Session run ID (e.g. session-2026-07-28-001)
        config: Evals config dict. Loaded from settings.json if None.

    Returns:
        True if GEval should run for this session.
    """
    if config is None:
        config = load_evals_config()

    mode = config.get("mode", "never")

    if mode == "always":
        return True
    elif mode == "never":
        return False
    elif mode == "sampled":
        return _sampled_check(run_id, config)
    else:
        return False


def _sampled_check(run_id: str, config: dict) -> bool:
    """Deterministic sampling: hash(runId + salt) % 10000 < sampleRate * 10000.

    Also enforces minimumIntervalHours: if the last eval was within the
    interval window, skip regardless of hash result.
    """
    # Interval check first
    min_interval = config.get("minimumIntervalHours", 24)
    last_eval_time = _get_last_eval_time()
    if last_eval_time is not None:
        elapsed = datetime.now(timezone.utc) - last_eval_time
        if elapsed < timedelta(hours=min_interval):
            return False

    # Deterministic hash sampling
    sample_rate = config.get("sampleRate", 0.25)
    salt = "ielts-eval-sampling-v1"
    key = f"{run_id}:{salt}"
    hash_val = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return (hash_val % 10000) < (sample_rate * 10000)


def _get_last_eval_time() -> datetime | None:
    """Read the timestamp of the most recent eval from latest.json."""
    latest_file = EVALS_DIR / "latest.json"
    if not latest_file.exists():
        # Also check for any session files
        session_files = sorted(EVALS_DIR.glob("session-*.json"))
        if session_files:
            latest_file = session_files[-1]
        else:
            return None

    try:
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        ts = data.get("timestamp", "")
        if ts:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
    except (json.JSONDecodeError, ValueError, IOError, OSError):
        pass

    return None
