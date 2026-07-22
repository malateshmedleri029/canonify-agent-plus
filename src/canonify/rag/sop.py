"""SOP retrieval for grounding the agents.

LOCAL mode: lightweight keyword retrieval over the SOP markdown (zero deps).
GCP mode: swap this for Vertex AI Vector Search over chunked SOP docs (same interface).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List


class SopRetriever:
    def __init__(self, sop_dir: Path, schema_name: str):
        self.sop_dir = Path(sop_dir)
        self.schema_name = schema_name
        self._chunks: List[str] = self._load()

    def _load(self) -> List[str]:
        chunks: List[str] = []
        candidate = self.sop_dir / f"{self.schema_name}_sop.md"
        files = [candidate] if candidate.exists() else sorted(self.sop_dir.glob("*.md"))
        for f in files:
            text = f.read_text()
            # Chunk by bullet/line so retrieval is granular.
            for line in text.splitlines():
                line = line.strip("- ").strip()
                if len(line) > 15:
                    chunks.append(line)
        return chunks

    def retrieve(self, query: str, k: int = 3) -> List[str]:
        """Return up to k SOP lines most relevant to the query (keyword overlap)."""
        q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        scored = []
        for chunk in self._chunks:
            c_tokens = set(re.findall(r"[a-z0-9]+", chunk.lower()))
            overlap = len(q_tokens & c_tokens)
            if overlap:
                scored.append((overlap, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]
