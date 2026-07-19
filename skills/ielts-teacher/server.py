#!/usr/bin/env python3
"""IELTS File Bridge Server — stdlib-only HTTP server for the HTML studio.

Serves: HTML studio, textbook materials (MP3s, images, markdown), student profile.
Accepts: POST /save to persist studio results to .ielts/.
Accepts: POST /check-text-answers for LLM-based semantic answer checking.

The /textbook directory is the single source of truth for all study materials.
Everything under it is auto-discovered — no hardcoded subdirectory names.

Usage:
  python3 server.py              # default port 8765
  python3 server.py --port 9000  # custom port
"""

import argparse, base64, json, os, re, sys, shutil, subprocess, urllib.request
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

STUDIO_DIR = Path(__file__).resolve().parent

# Find project root — the single source of truth for textbook/ and studio files.
# Uses git to find the repo root, then looks for textbook/ under it.
# This works regardless of where server.py is invoked from (project skills/,
# .claude/skills/ symlink, or ~/.claude/skills/ copy).
def _find_project_root():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=STUDIO_DIR, timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass
    # Fallback: walk up from STUDIO_DIR looking for textbook/
    d = STUDIO_DIR
    for _ in range(5):
        if (d / "textbook").exists():
            return d
        d = d.parent
    return STUDIO_DIR.parent.parent  # last resort

PROJECT_ROOT = _find_project_root()
IELTS_DIR = PROJECT_ROOT / ".ielts"
TEXTBOOK_DIR = PROJECT_ROOT / "textbook"
SHARED_DIR = PROJECT_ROOT / "shared"

for d in [IELTS_DIR, IELTS_DIR/"speaking", IELTS_DIR/"listening", IELTS_DIR/"writing", IELTS_DIR/"reading"]:
    d.mkdir(parents=True, exist_ok=True)

# Ensure shared skill directories exist
for skill_dir in ["listening", "speaking", "writing"]:
    (SHARED_DIR / skill_dir).mkdir(parents=True, exist_ok=True)


# ── Auto-discover materials ──

def _build_materials():
    """Scan textbook/ recursively and return a manifest of everything found."""
    manifest = {"root": str(TEXTBOOK_DIR), "sources": [], "totalSources": 0}

    if not TEXTBOOK_DIR.exists():
        return manifest

    for entry in sorted(TEXTBOOK_DIR.iterdir()):
        if entry.name.startswith('.'):
            continue

        source = {
            "name": entry.name,
            "type": "directory" if entry.is_dir() else "file",
            "path": entry.name,
        }

        if entry.is_dir():
            # Collect all files in this source
            files = {"mp3s": [], "images": [], "markdown": [], "pdfs": [], "other": []}
            for f in sorted(entry.rglob("*")):
                if f.is_file() and not f.name.startswith('.'):
                    rel = str(f.relative_to(entry))
                    if f.suffix.lower() == '.mp3':
                        files["mp3s"].append(rel)
                    elif f.suffix.lower() in ('.jpeg', '.jpg', '.png', '.gif', '.webp'):
                        files["images"].append(rel)
                    elif f.suffix.lower() == '.md':
                        files["markdown"].append(rel)
                    elif f.suffix.lower() == '.pdf':
                        files["pdfs"].append(rel)
                    else:
                        files["other"].append(rel)

            mp3_count = len(files["mp3s"])
            img_count = len(files["images"])
            md_count = len(files["markdown"])
            source["files"] = files
            source["summary"] = f"{mp3_count} mp3s, {img_count} images, {md_count} markdown"
            source["totalFiles"] = mp3_count + img_count + md_count + len(files["pdfs"]) + len(files["other"])
        else:
            source["size"] = entry.stat().st_size

        manifest["sources"].append(source)

    manifest["totalSources"] = len(manifest["sources"])
    return manifest

_materials_cache = _build_materials()


# ── Auto-discover skill sources (listening, speaking, etc.) ──

def _build_skill_sources(skill):
    """Scan shared/{skill}/ for {skill}_*.json files. Returns metadata list."""
    sources = []
    skill_dir = SHARED_DIR / skill
    if not skill_dir.exists():
        return sources

    for entry in sorted(skill_dir.iterdir()):
        if entry.name.startswith('.') or entry.suffix != '.json':
            continue
        # Extract source name from filename: {skill}_{source}.json → source
        name = entry.stem  # e.g., "listening_cambridge-1"
        prefix = f"{skill}_"
        if name.startswith(prefix):
            name = name[len(prefix):]
        try:
            with open(entry, "r", encoding="utf-8") as f:
                data = json.load(f)
            sources.append({
                "id": name,
                "file": str(entry.relative_to(PROJECT_ROOT)),
                "testCount": len(data.get("tests", [])),
                "generatedAt": data.get("generatedAt", ""),
            })
        except (json.JSONDecodeError, OSError):
            sources.append({
                "id": name,
                "file": str(entry.relative_to(PROJECT_ROOT)),
                "error": "Failed to parse JSON"
            })

    return sources

# Pre-build caches for skills that have content
_skill_sources_cache = {}
for _skill in ["listening", "speaking", "writing"]:
    _cache = _build_skill_sources(_skill)
    if _cache:
        _skill_sources_cache[_skill] = _cache


def _serve_skill_api(handler, skill, source_id=None):
    """Handle /api/{skill}[/{source}] — generic across listening, speaking, etc.
    Returns True if the request was handled, False if the handler should continue.
    """
    # Security: prevent path traversal
    if source_id is not None:
        if ".." in source_id or "/" in source_id or "\\" in source_id:
            handler.send_error(403, "Invalid source name")
            return True
        if not source_id:
            handler._serve_json({"sources": _skill_sources_cache.get(skill, [])})
            return True
        json_path = SHARED_DIR / skill / f"{skill}_{source_id}.json"
        if json_path.exists() and json_path.is_file():
            handler._serve_file(json_path, "application/json; charset=utf-8")
            return True
        handler.send_error(404, f"{skill.capitalize()} source not found: {source_id}")
        return True
    # List sources
    handler._serve_json({"sources": _skill_sources_cache.get(skill, [])})
    return True


def _build_reading_sources():
    """Scan shared/reading/{source}/test-*.json for available reading sources."""
    sources = []
    reading_dir = SHARED_DIR / "reading"
    if not reading_dir.exists():
        return sources
    for source_dir in sorted(reading_dir.iterdir()):
        if source_dir.name.startswith('.') or not source_dir.is_dir():
            continue
        tests = sorted(source_dir.glob("test-*.json"))
        if tests:
            sources.append({
                "id": source_dir.name,
                "testCount": len(tests),
            })
    return sources


def _build_reading_tests(source_id):
    """List reading tests for a source. Returns list or None if not found."""
    json_dir = SHARED_DIR / "reading" / source_id
    if not json_dir.exists():
        return None
    tests = []
    for f in sorted(json_dir.glob("test-*.json")):
        m = re.match(r'test-(.+)\.json$', f.name)
        if not m:
            continue
        test_id = m.group(1)
        tests.append({
            "testId": test_id,
            "file": str(f.relative_to(PROJECT_ROOT)),
            "url": f"/api/reading/{source_id}/test/{test_id}"
        })
    return tests if tests else None


def _run_azure_pronunciation(audio_path):
    """Try Azure Speech pronunciation assessment. Returns dict or None.
    Converts WebM/MP4 audio to WAV via afconvert (macOS) if needed.
    """
    pronounce_cli = STUDIO_DIR / "pronounce_cli.py"
    if not pronounce_cli.exists():
        return {"error": "pronounce_cli.py not found"}

    # Use .venv python if available (has azure-cognitiveservices-speech installed)
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python3"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    # Convert to WAV if not already WAV (browser produces WebM/MP4)
    audio_to_assess = str(audio_path)
    converted = None
    if not str(audio_path).lower().endswith('.wav'):
        converted = str(audio_path).replace('.webm', '.wav').replace('.mp4', '.wav')
        try:
            result = subprocess.run(
                ["afconvert", "-f", "WAVE", "-d", "LEI16@16000",
                 str(audio_path), converted],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                audio_to_assess = converted
            else:
                # Fall back to original — let Azure SDK try to decode it
                pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # afconvert not available — try original format

    try:
        result = subprocess.run(
            [python_exe, str(pronounce_cli), "--audio", audio_to_assess, "--json"],
            capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT)
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        else:
            err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return {"error": err[:200]}
    except subprocess.TimeoutExpired:
        return {"error": "Azure Speech timed out (30s)"}
    except Exception as e:
        return {"error": str(e)[:200]}
    finally:
        # Clean up converted file
        if converted and os.path.exists(converted):
            try:
                os.remove(converted)
            except OSError:
                pass


def _find_file_in_textbook(rel_path):
    """Find a file anywhere under textbook/ by relative path."""
    target = TEXTBOOK_DIR / rel_path
    if target.exists():
        return target
    # Try case-insensitive match
    parts = rel_path.split("/")
    for entry in TEXTBOOK_DIR.rglob("*"):
        if entry.is_file() and entry.name.lower() == Path(rel_path).name.lower():
            return entry
    return None


def _guess_content_type(filename):
    ext = Path(filename).suffix.lower()
    return {
        '.html': 'text/html; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.md': 'text/markdown; charset=utf-8',
        '.txt': 'text/plain; charset=utf-8',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.webm': 'audio/webm',
        '.ogg': 'audio/ogg',
        '.jpeg': 'image/jpeg',
        '.jpg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.pdf': 'application/pdf',
        '.ico': 'image/x-icon',
    }.get(ext, 'application/octet-stream')


# ── LLM semantic answer checking ──

def _load_env():
    """Load .env file from project root. Stdlib only (no python-dotenv)."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return {}
    env = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def _call_llm(prompt, system_prompt=None):
    """Call OpenAI-compatible LLM API. Returns response text or None."""
    env = _load_env()
    api_url = env.get("LLM_API_URL", "https://api.deepseek.com/chat/completions")
    api_key = env.get("LLM_API_KEY", "")
    model = env.get("LLM_MODEL", "deepseek-v4-flash")

    if not api_key:
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.0,
    }).encode()

    req = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[bridge] LLM error: {e}", file=sys.stderr)
        return None


def _normalize_answer(text):
    """Normalize an answer text for comparison.
    - Handles () brackets: (the) means 'the' is optional
    - Strips extra whitespace
    """
    if not text:
        return ""
    t = text.strip()
    # Remove parentheses and their content as optional markers, but keep if the word is still there
    # e.g., "(the) wealthy" → both "the wealthy" and "wealthy" should match
    # Strategy: create two variants — with and without bracketed content
    return t


def _check_text_answers_llm(answers):
    """Check a batch of text answers using LLM semantic comparison.

    answers: list of {questionNumber, userAnswer, correctAnswer, questionText}
    Returns: list of {questionNumber, correct}
    """
    # First pass: strict + bracket normalization
    results = []
    llm_batch = []

    for a in answers:
        qn = a["questionNumber"]
        ua = (a.get("userAnswer") or "").strip().lower()
        ca = (a.get("correctAnswer") or "").strip().lower()

        if not ua or not ca:
            results.append({"questionNumber": qn, "correct": False})
            continue

        # Normalize whitespace
        ua_norm = re.sub(r'\s+', ' ', ua).strip()
        ca_norm = re.sub(r'\s+', ' ', ca).strip()

        # Strict match first
        if ua_norm == ca_norm:
            results.append({"questionNumber": qn, "correct": True})
            continue

        # Bracket normalization: (word) means the word is optional
        # "(the) wealthy (members) (of) (society)" should match either:
        #   a) "the wealthy members of society" (brackets removed, content kept)
        #   b) "wealthy members of society"     (bracketed words removed entirely)
        if '(' in ca_norm:
            # Replace (word) → word (keep content, remove brackets)
            ca_unbracketed = re.sub(r'\(([^)]*)\)', r'\1', ca_norm)
            ca_unbracketed = re.sub(r'\s+', ' ', ca_unbracketed).strip()
            if ua_norm == ca_unbracketed:
                results.append({"questionNumber": qn, "correct": True})
                continue

            # Remove (word) entirely
            ca_stripped = re.sub(r'\([^)]*\)', '', ca_norm)
            ca_stripped = re.sub(r'\s+', ' ', ca_stripped).strip()
            if ua_norm == ca_stripped:
                results.append({"questionNumber": qn, "correct": True})
                continue

            # Word-set comparison: user's words should be a superset of the stripped version
            # (allows reordering and minor differences)
            ua_words = set(ua_norm.split())
            ca_stripped_words = set(ca_stripped.split())
            ca_unbracketed_words = set(ca_unbracketed.split())
            # User answer should contain at least the stripped (non-optional) words
            # and should be a subset of the unbracketed words (maybe missing some optional)
            if ca_stripped_words.issubset(ua_words) and ua_words.issubset(ca_unbracketed_words):
                results.append({"questionNumber": qn, "correct": True})
                continue

        # Not matched by rules — send to LLM for semantic check
        llm_batch.append(a)
        results.append({"questionNumber": qn, "correct": False, "_pending_llm": True})

    # Second pass: LLM check for remaining items
    if llm_batch:
        prompt_lines = []
        for a in llm_batch:
            prompt_lines.append(
                f"Q{a['questionNumber']}: "
                f"Student answer: \"{a.get('userAnswer', '')}\" | "
                f"Correct answer: \"{a.get('correctAnswer', '')}\""
            )

        system_prompt = (
            "You are an IELTS answer checker. For each question, determine if the student's answer "
            "is semantically equivalent to the correct answer. IELTS answers often accept synonyms, "
            "minor wording differences, and optional articles (e.g., 'the', 'a/an'). "
            "Respond with ONLY a JSON array: [{\"q\": N, \"correct\": true/false}]. "
            "Mark as correct if the student's answer captures the same essential information."
        )
        user_prompt = "Check these IELTS answers (text input only):\n" + "\n".join(prompt_lines)

        llm_response = _call_llm(user_prompt, system_prompt)

        if llm_response:
            try:
                # Extract JSON from response (handle markdown-wrapped JSON)
                json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
                if json_match:
                    llm_results = json.loads(json_match.group())
                    llm_map = {r["q"]: r["correct"] for r in llm_results}
                    for r in results:
                        if r.get("_pending_llm"):
                            r["correct"] = llm_map.get(r["questionNumber"], False)
                            del r["_pending_llm"]
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[bridge] LLM parse error: {e} — raw: {llm_response[:200]}", file=sys.stderr)
                # Fall through — pending items stay False
                pass

    # Clean up _pending_llm markers
    for r in results:
        r.pop("_pending_llm", None)

    return results


class BridgeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STUDIO_DIR), **kwargs)

    def log_message(self, format, *args):
        if args[1] != '200':
            print(f"[bridge] {args[0]}", file=sys.stderr)

    def _serve_file(self, path_obj, content_type=None):
        if not path_obj or not path_obj.exists():
            return False
        ct = content_type or _guess_content_type(str(path_obj))
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(path_obj.stat().st_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(path_obj, "rb") as f:
            shutil.copyfileobj(f, self.wfile)
        return True

    def _serve_json(self, data):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path.lstrip("/"))

        # ── /api/materials — manifest of all available study materials ──
        if path == "api/materials":
            self._serve_json(_materials_cache)
            return

        # ── /api/materials/refresh — re-scan textbook/ ──
        if path == "api/materials/refresh":
            _materials_cache.clear()
            _materials_cache.update(_build_materials())
            self._serve_json({"status": "refreshed", "totalSources": _materials_cache["totalSources"]})
            return

        # ── /api/{skill} — list available sources for a skill ──
        # ── /api/{skill}/<source> — serve skill JSON for a source ──
        for _sk in ["listening", "speaking", "writing"]:
            _api_prefix = f"api/{_sk}"
            if path == _api_prefix or path == _api_prefix + "/":
                _serve_skill_api(self, _sk)
                return
            if path.startswith(_api_prefix + "/"):
                _source_id = path[len(_api_prefix + "/"):].strip()
                _serve_skill_api(self, _sk, _source_id)
                return

        # ── /api/reading — list sources with reading JSON ──
        if path == "api/reading" or path == "api/reading/":
            self._serve_json({"sources": _build_reading_sources()})
            return

        # ── /api/reading/<source>/test/<N> — serve reading test JSON (BEFORE /api/reading/<source>) ──
        if path.startswith("api/reading/") and "/test/" in path:
            parts = path[len("api/reading/"):].split("/test/")
            if len(parts) == 2:
                src_id, test_id = parts
                if ".." in src_id or "/" in src_id or "\\" in src_id:
                    self.send_error(403, "Invalid source name"); return
                if ".." in test_id or "/" in test_id or "\\" in test_id:
                    self.send_error(403, "Invalid test id"); return
                json_path = SHARED_DIR / "reading" / src_id / f"test-{test_id}.json"
                if json_path.exists() and json_path.is_file():
                    self._serve_file(json_path, "application/json; charset=utf-8")
                else:
                    self.send_error(404, f"Reading test not found: {src_id}/test/{test_id}")
                return

        # ── /api/reading/<source> — list reading tests for a source ──
        if path.startswith("api/reading/"):
            source_id = path[len("api/reading/"):].strip()
            if ".." in source_id or "/" in source_id or "\\" in source_id:
                self.send_error(403, "Invalid source name"); return
            tests = _build_reading_tests(source_id)
            if tests is not None:
                self._serve_json({"source": source_id, "tests": tests})
            else:
                self.send_error(404, f"Reading source not found: {source_id}")
            return

        # ── /textbook/<anything> — serve any file from textbook/ ──
        if path.startswith("textbook/"):
            rel = path[len("textbook/"):]
            f = _find_file_in_textbook(rel)
            if f and self._serve_file(f): return
            self.send_error(404, f"Not found in textbook: {rel}"); return

        # ── /audio/<anything> — alias for /textbook/<source>/<audio-path>.mp3 ──
        if path.startswith("audio/"):
            rel = path[len("audio/"):]
            f = _find_file_in_textbook(rel)
            if f and self._serve_file(f): return
            # Try searching for just the filename
            filename = Path(rel).name
            for entry in TEXTBOOK_DIR.rglob("*.mp3"):
                if entry.name == filename:
                    if self._serve_file(entry): return
            self.send_error(404, f"Audio not found: {rel}"); return

        # ── /lessons/<filename> — serve lesson plan HTML files from .ielts/lesson-plans/ ──
        # ── /lessons/shared/<file> — serve shared template assets (CSS, JS) ──
        # ── /lessons/<filename> — also checks templates/ directory for built-in templates ──
        if path.startswith("lessons/"):
            filename = path[len("lessons/"):]
            # Shared template assets (base-test.css, base-test.js)
            if filename.startswith("shared/") and ".." not in filename:
                shared_file = STUDIO_DIR / "templates" / filename
                if shared_file.exists() and shared_file.is_file():
                    if self._serve_file(shared_file): return
                self.send_error(404, f"Shared asset not found: {filename}"); return
            # Built-in templates (listening-test.html, etc.) from templates/ directory
            if ".." not in filename and "/" not in filename:
                # Check templates/ directory first
                template_file = STUDIO_DIR / "templates" / filename
                if template_file.exists() and template_file.is_file():
                    if self._serve_file(template_file, "text/html; charset=utf-8"): return
                # Fall back to lesson-plans/
                lesson_file = IELTS_DIR / "lesson-plans" / filename
                if lesson_file.exists() and lesson_file.is_file():
                    if self._serve_file(lesson_file, "text/html; charset=utf-8"): return
            else:
                self.send_error(403, "Invalid path"); return
            self.send_error(404, f"Lesson not found: {filename}"); return

        # ── /test-html/<filename> — serve generated section HTML files ──
        if path.startswith("test-html/"):
            filename = path[len("test-html/"):]
            if ".." in filename or "/" in filename or "\\" in filename:
                self.send_error(403, "Invalid path"); return
            html_file = IELTS_DIR / "test-html" / filename
            if html_file.exists() and html_file.is_file():
                if self._serve_file(html_file, "text/html; charset=utf-8"): return
            self.send_error(404, f"Test HTML not found: {filename}"); return

        # ── /roadmap.json — serve student-profile.json (backward compat) ──
        # roadmap.json v1 was superseded by student-profile.json v2.
        # The HTML studio reads learner.targetBand, learner.examDate,
        # learner.activeSkills, and skills.{}.currentBand — all present
        # at the same paths in student-profile.json.
        if path == "roadmap.json":
            profile = IELTS_DIR / "student-profile.json"
            if profile.exists():
                if self._serve_file(profile, "application/json"): return
            self._serve_json({})
            return

        # ── /favicon.ico ──
        if path == "favicon.ico":
            self.send_response(204); self.end_headers(); return

        # ── Default: serve from studio directory ──
        if path == "" or path == "/":
            path = "ielts-studio.html"

        file_path = STUDIO_DIR / path
        if file_path.exists() and file_path.is_file():
            if self._serve_file(file_path): return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        # ── /check-text-answers — LLM-based semantic answer checking ──
        if parsed.path == "/check-text-answers":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_error(400, "Empty body"); return
            if content_length > 1024 * 1024:
                self.send_error(413, "Payload too large"); return
            try:
                body = self.rfile.read(content_length)
                data = json.loads(body.decode("utf-8"))
                answers = data.get("answers", [])
                results = _check_text_answers_llm(answers)
                self._serve_json({"results": results})
            except Exception as e:
                self.send_error(500, f"Check failed: {e}")
            return

        if parsed.path != "/save":
            self.send_error(404, "Endpoint not found"); return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_error(400, "Empty body"); return
        if content_length > 50 * 1024 * 1024:
            self.send_error(413, "Payload too large (max 50MB)"); return

        try:
            body = self.rfile.read(content_length)
            json_data = json.loads(body.decode("utf-8"))
            skill = json_data.get("skill", "unknown")
            dest = IELTS_DIR / skill / "latest.json"
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Save audio blob if present (speaking skill)
            audio_saved = False
            audio_base64 = json_data.pop("audioBase64", None)
            audio_mime = json_data.pop("audioMimeType", None)
            if audio_base64 and skill == "speaking":
                try:
                    audio_bytes = base64.b64decode(audio_base64)
                    audio_dest = IELTS_DIR / skill / "latest.webm"
                    with open(audio_dest, "wb") as af:
                        af.write(audio_bytes)
                    json_data["audioFile"] = str(audio_dest)
                    json_data["audioSize"] = len(audio_bytes)
                    audio_saved = True
                except Exception as e:
                    json_data["audioError"] = str(e)

            json_data["_savedAt"] = datetime.utcnow().isoformat() + "Z"
            with open(dest, "w") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            # Auto-run Azure Speech pronunciation assessment if audio saved
            azure_result = None
            if audio_saved and skill == "speaking":
                azure_result = _run_azure_pronunciation(audio_dest)

            response = {
                "status": "ok", "saved": [str(dest)],
                "message": f"Saved. Switch to Claude and say 'evaluate my {skill}'.",
                "audioSaved": audio_saved
            }
            if azure_result:
                if azure_result.get("error"):
                    response["azureError"] = azure_result["error"]
                else:
                    response["azureScores"] = {
                        "pronScore": azure_result.get("pronScore"),
                        "accuracy": azure_result.get("accuracy"),
                        "fluency": azure_result.get("fluency"),
                        "completeness": azure_result.get("completeness"),
                        "transcript": azure_result.get("transcript"),
                    }
            self._serve_json(response)
        except json.JSONDecodeError as e:
            self.send_error(400, f"Invalid JSON: {e}")
        except Exception as e:
            self.send_error(500, f"Save failed: {e}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    p = argparse.ArgumentParser(description="IELTS File Bridge Server")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()

    print(f"[bridge] http://localhost:{args.port}")
    print(f"[bridge] textbook: {TEXTBOOK_DIR} ({_materials_cache['totalSources']} sources)")
    for s in _materials_cache["sources"]:
        sz = s.get('size', 0)
        print(f"[bridge]   {s['name']}: {s.get('summary', f'{sz} bytes')}")
    print(f"[bridge] data: {IELTS_DIR}")

    server = HTTPServer(("127.0.0.1", args.port), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] Done")
        server.shutdown()

if __name__ == "__main__":
    main()
