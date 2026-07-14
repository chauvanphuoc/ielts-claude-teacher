#!/usr/bin/env python3
"""IELTS File Bridge Server — stdlib-only HTTP server for the HTML studio.

Serves: HTML studio, textbook materials (MP3s, images, markdown), roadmap.json.
Accepts: POST /save to persist studio results to .ielts/.

The /textbook directory is the single source of truth for all study materials.
Everything under it is auto-discovered — no hardcoded subdirectory names.

Usage:
  python3 server.py              # default port 8765
  python3 server.py --port 9000  # custom port
"""

import argparse, json, os, sys, shutil, subprocess
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

# Ensure shared/listening/ exists
(SHARED_DIR / "listening").mkdir(parents=True, exist_ok=True)


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


# ── Auto-discover listening sources ──

def _build_listening_sources():
    """Scan shared/listening/ for available listening JSON files."""
    sources = []
    listening_dir = SHARED_DIR / "listening"
    if not listening_dir.exists():
        return sources

    for entry in sorted(listening_dir.iterdir()):
        if entry.name.startswith('.') or entry.suffix != '.json':
            continue
        # Extract source name from filename: listening_{source}.json → source
        name = entry.stem  # e.g., "listening_cambridge-1"
        if name.startswith("listening_"):
            name = name[len("listening_"):]
        try:
            with open(entry, "r", encoding="utf-8") as f:
                data = json.load(f)
            sources.append({
                "id": name,
                "file": str(entry.relative_to(PROJECT_ROOT)),
                "testCount": len(data.get("tests", [])),
                "generatedAt": data.get("generatedAt", ""),
                "audioBasePath": data.get("audioBasePath", "")
            })
        except (json.JSONDecodeError, OSError):
            sources.append({
                "id": name,
                "file": str(entry.relative_to(PROJECT_ROOT)),
                "error": "Failed to parse JSON"
            })

    return sources

_listening_sources_cache = _build_listening_sources()


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

        # ── /api/listening — list available listening sources ──
        if path == "api/listening" or path == "api/listening/":
            self._serve_json({"sources": _listening_sources_cache})
            return

        # ── /api/listening/<source> — serve listening JSON for a source ──
        if path.startswith("api/listening/"):
            source_id = path[len("api/listening/"):].strip()
            # Security: prevent path traversal
            if ".." in source_id or "/" in source_id or "\\" in source_id:
                self.send_error(403, "Invalid source name"); return
            if not source_id:
                self._serve_json({"sources": _listening_sources_cache})
                return
            json_path = SHARED_DIR / "listening" / f"listening_{source_id}.json"
            if json_path.exists() and json_path.is_file():
                if self._serve_file(json_path, "application/json; charset=utf-8"): return
            self.send_error(404, f"Listening source not found: {source_id}"); return

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
        if path.startswith("lessons/"):
            filename = path[len("lessons/"):]
            # Shared template assets (base-test.css, base-test.js)
            if filename.startswith("shared/") and ".." not in filename:
                shared_file = STUDIO_DIR / "templates" / filename
                if shared_file.exists() and shared_file.is_file():
                    if self._serve_file(shared_file): return
                self.send_error(404, f"Shared asset not found: {filename}"); return
            # Lesson plan HTML files (no subdirectories allowed)
            if ".." in filename or "/" in filename:
                self.send_error(403, "Invalid path"); return
            lesson_file = IELTS_DIR / "lesson-plans" / filename
            if lesson_file.exists() and lesson_file.is_file():
                if self._serve_file(lesson_file, "text/html; charset=utf-8"): return
            self.send_error(404, f"Lesson not found: {filename}"); return

        # ── /roadmap.json — from .ielts/ ──
        if path == "roadmap.json":
            roadmap = IELTS_DIR / "roadmap.json"
            if roadmap.exists():
                if self._serve_file(roadmap, "application/json"): return
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
            json_data["_savedAt"] = datetime.utcnow().isoformat() + "Z"
            with open(dest, "w") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            self._serve_json({
                "status": "ok", "saved": [str(dest)],
                "message": f"Saved. Switch to Claude and say 'evaluate my {skill}'."
            })
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
