"""Canonify Agent+ web app — a zero-dependency upload UI + JSON API (stdlib http.server).

Run locally:
    PYTHONPATH=src python -m canonify.webapp
    # then open http://localhost:8000

Endpoints:
    GET  /                     -> the single-page UI (web/index.html)
    GET  /api/samples          -> list bundled sample files
    GET  /api/dict?tenant=...  -> learned dictionary for a tenant
    POST /api/canonicalize     -> {filename, content_base64, tenant} -> full pipeline result JSON

Uploads are sent as base64 JSON (works for both CSV and binary .xlsx) so we avoid multipart parsing
and keep the server dependency-free.
"""
from __future__ import annotations

import base64
import io
import json
import csv as csvmod
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .config import Config, DATA_DIR
from .pipeline import run_pipeline
from .rag.dictionary import get_dictionary

WEB_DIR = Path(__file__).resolve().parent / "web"
_ALLOWED_SUFFIXES = (".csv", ".tsv", ".txt", ".xlsx", ".xls")


def _canonical_csv(result) -> str:
    cols, seen = [], set()
    for m in result.mappings:
        if m.canonical_column != "UNMATCHED" and m.canonical_column not in seen:
            seen.add(m.canonical_column)
            cols.append(m.canonical_column)
    buf = io.StringIO()
    writer = csvmod.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for row in result.canonical_rows:
        writer.writerow({c: row.get(c, "") for c in cols})
    return buf.getvalue()


def _run(filename: str, content_b64: str, tenant: str) -> dict:
    suffix = Path(filename).suffix.lower() or ".csv"
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported file type '{suffix}'.")
    data = base64.b64decode(content_b64)
    config = Config.from_env(tenant_id=tenant or "global")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        result, _ = run_pipeline(Path(tmp.name), config=config, write=False)
    return {
        "summary": result.summary(),
        "preprocess": result.preprocess,
        "mappings": result.mapping_audit_report(),
        "decisions": result.judge_decision_log(),
        "canonical_rows": result.canonical_rows[:200],
        "canonical_csv": _canonical_csv(result),
        "review_queue": result.review_queue,
        "security_flags": result.security_flags,
        "promoted": result.promoted_entries,
        "columns": [m.canonical_column for m in result.mappings
                    if m.canonical_column != "UNMATCHED"],
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    def log_message(self, *args):  # quieter console
        pass

    def do_GET(self):
        route = urlparse(self.path)
        if route.path in ("/", "/index.html"):
            html = (WEB_DIR / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")
        if route.path == "/api/samples":
            samples_dir = DATA_DIR / "samples"
            files = sorted(p.name for p in samples_dir.iterdir()
                           if p.suffix.lower() in _ALLOWED_SUFFIXES)
            return self._json(200, {"samples": files})
        if route.path == "/api/sample":
            name = parse_qs(route.query).get("name", [""])[0]
            p = (DATA_DIR / "samples" / name).resolve()
            if p.parent != (DATA_DIR / "samples").resolve() or not p.exists():
                return self._json(404, {"error": "not found"})
            return self._json(200, {"filename": p.name,
                                    "content_base64": base64.b64encode(p.read_bytes()).decode()})
        if route.path == "/api/dict":
            tenant = parse_qs(route.query).get("tenant", ["global"])[0]
            entries = get_dictionary(Config.from_env(tenant_id=tenant)).all_entries(tenant)
            return self._json(200, {"tenant": tenant, "entries": entries})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        route = urlparse(self.path)
        if route.path != "/api/canonicalize":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = _run(payload.get("filename", "upload.csv"),
                          payload.get("content_base64", ""),
                          payload.get("tenant", "global"))
            return self._json(200, result)
        except Exception as exc:
            return self._json(400, {"error": str(exc)})


def main() -> None:
    import os
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Canonify Agent+ UI running at http://localhost:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
