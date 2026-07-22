"""Vertex AI Gemini client with a safe local fallback.

In LOCAL mode `enabled` is False and every method returns None, so callers transparently fall back
to the deterministic rule/fuzzy engine. In GCP mode this wraps Vertex AI Gemini with a low
temperature for reproducibility, and asks the model to return strict JSON.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from .model_armor import ModelArmorClient


class GeminiClient:
    def __init__(self, config):
        self.config = config
        self.enabled = config.mode == "gcp"
        self.armor = ModelArmorClient(config)
        self._model = None
        if self.enabled:
            self._init_model()

    def _init_model(self) -> None:  # pragma: no cover - requires GCP libs/creds
        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=self.config.gcp_project, location=self.config.gcp_location)
        self._model = GenerativeModel(self.config.gemini_model)

    def _json_call(self, prompt: str) -> Optional[Dict]:  # pragma: no cover - GCP path
        if not self.enabled or self._model is None:
            return None
        # Model Armor: screen the (untrusted-data-bearing) prompt BEFORE sending to Gemini.
        pre = self.armor.screen_prompt(prompt)
        if pre.blocked:
            return None  # fall back to the deterministic engine; incident is flagged upstream
        from vertexai.generative_models import GenerationConfig
        resp = self._model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=0.0, response_mime_type="application/json"
            ),
        )
        try:
            text = resp.text
        except AttributeError:
            return None
        # Model Armor: screen the model's response before trusting it.
        post = self.armor.screen_response(text)
        if post.blocked:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def propose_mapping(self, source_header: str, candidates: List[str],
                        sop_context: List[str]) -> Optional[Dict]:
        """Ask Gemini to pick the best canonical column for an ambiguous source header.

        Returns {"canonical_column": str, "confidence": float, "explanation": str} or None.
        """
        if not self.enabled:
            return None
        prompt = (
            "You canonicalize messy tabular headers. Given a source column header, choose the best "
            "matching canonical column from the candidates, or return an empty canonical_column if "
            "none fit. Respond as strict JSON with keys canonical_column, confidence (0-1), "
            "explanation.\n"
            f"SOP context:\n- " + "\n- ".join(sop_context) + "\n"
            f"Source header: {source_header!r}\n"
            f"Candidates: {candidates}\n"
        )
        return self._json_call(prompt)  # pragma: no cover - GCP path

    def review_transform(self, canonical_column: str, raw_value: str,
                         sop_context: List[str]) -> Optional[Dict]:
        """Ask Gemini to standardize an ambiguous cell value (used by the judge on edge cases)."""
        if not self.enabled:
            return None
        prompt = (
            "Standardize this cell value for the given canonical column per the SOP. Respond as "
            "strict JSON with keys value, confidence (0-1), explanation. If ambiguous or sensitive, "
            "lower the confidence so a human reviews it.\n"
            f"SOP context:\n- " + "\n- ".join(sop_context) + "\n"
            f"Canonical column: {canonical_column}\nRaw value: {raw_value!r}\n"
        )
        return self._json_call(prompt)  # pragma: no cover - GCP path
