"""Minimal HTTP server for Cloud Run (GCP mode), triggered by Eventarc on GCS uploads.

Uses only the stdlib http.server so the container stays tiny. Eventarc delivers a CloudEvent
(Storage object finalized) as an HTTP POST; we download the object, run the pipeline in GCP mode,
and return 200. Any error returns 500 so Eventarc retries.

Run locally:  python -m canonify.server   (PORT defaults to 8080)
"""
from __future__ import annotations

import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Config
from .pipeline import run_pipeline


def _handle_event(payload: dict) -> dict:  # pragma: no cover - requires GCP
    from google.cloud import storage
    bucket = payload["bucket"]
    name = payload["name"]
    if not name.lower().endswith((".csv",)):
        return {"skipped": name}

    # Tenant convention: gs://<raw-bucket>/<tenant_id>/<file>.csv
    tenant_id = name.split("/")[0] if "/" in name else "global"

    client = storage.Client()
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / Path(name).name
        client.bucket(bucket).blob(name).download_to_filename(str(local))
        config = Config.from_env(mode="gcp", tenant_id=tenant_id)
        result, paths = run_pipeline(local, config=config)
    return {"summary": result.summary(), "sinks": paths}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # health check
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):  # pragma: no cover - requires GCP event
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body or b"{}")
            result = _handle_event(payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as exc:  # let Eventarc retry
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode())


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
