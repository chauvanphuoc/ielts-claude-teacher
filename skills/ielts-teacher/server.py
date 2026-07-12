#!/usr/bin/env python3
"""IELTS File Bridge Server — stdlib-only HTTP server for the HTML studio."""

import argparse, json, os, sys, shutil
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

IELTS_DIR = Path.home() / ".ielts"
STUDIO_DIR = Path(__file__).resolve().parent
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
CAMBRIDGE_MP3_DIR = DOCS_DIR / "Cambridge-IELTS-1"
IELTS_45_AUDIO = DOCS_DIR / "IELTS-4-5" / "Audio"

for d in [IELTS_DIR, IELTS_DIR/"speaking", IELTS_DIR/"listening", IELTS_DIR/"writing"]:
    d.mkdir(parents=True, exist_ok=True)


class BridgeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STUDIO_DIR), **kwargs)

    def log_message(self, format, *args):
        if args[1] != '200':
            print(f"[bridge] {args[0]}", file=sys.stderr)

    def _serve_file(self, path_obj, content_type):
        if not path_obj.exists():
            return False
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path_obj.stat().st_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(path_obj, "rb") as f:
            shutil.copyfileobj(f, self.wfile)
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.lstrip("/")

        if path.startswith("audio/cambridge-1/"):
            mp3 = CAMBRIDGE_MP3_DIR / path.replace("audio/cambridge-1/", "")
            if self._serve_file(mp3, "audio/mpeg"): return
            self.send_error(404, f"MP3 not found: {mp3.name}"); return

        if path.startswith("audio/ielts-4-5/"):
            mp3 = IELTS_45_AUDIO / path.replace("audio/ielts-4-5/", "")
            if self._serve_file(mp3, "audio/mpeg"): return
            self.send_error(404, f"MP3 not found: {mp3.name}"); return

        # Serve roadmap.json from ~/.ielts/
        if path == "roadmap.json":
            roadmap = IELTS_DIR / "roadmap.json"
            if roadmap.exists():
                if self._serve_file(roadmap, "application/json"): return
            # Return empty JSON instead of 404 — prevents console noise
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
            return

        # Favicon — return 204 (no content) to prevent 404 noise
        if path == "favicon.ico":
            self.send_response(204); self.end_headers(); return

        if path == "" or path == "/":
            path = "ielts-studio.html"

        file_path = STUDIO_DIR / path
        if file_path.exists() and file_path.is_file():
            ct = "text/html"
            if path.endswith(".js"): ct = "application/javascript"
            elif path.endswith(".css"): ct = "text/css"
            elif path.endswith(".json"): ct = "application/json"
            elif path.endswith(".webm"): ct = "audio/webm"
            if self._serve_file(file_path, ct): return

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

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok", "saved": [str(dest)],
                "message": f"Saved. Switch to Claude and say 'evaluate my {skill}'."
            }).encode())
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
    server = HTTPServer(("127.0.0.1", args.port), BridgeHandler)
    print(f"[bridge] http://localhost:{args.port}")
    print(f"[bridge] Serving: {STUDIO_DIR}")
    print(f"[bridge] MP3s: {CAMBRIDGE_MP3_DIR}")
    print(f"[bridge] Data: {IELTS_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] Done")
        server.shutdown()

if __name__ == "__main__":
    main()
