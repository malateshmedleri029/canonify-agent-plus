"""Vertex AI Feature Store backend for the learned dictionary (GCP mode).

Requires the `gcp` extra (`pip install -e .[gcp]`) and application-default credentials.
Falls back conceptually to the same interface as LocalJsonDictionary.

NOTE: This module is only imported in GCP mode. It is intentionally thin — the MVP uses BigQuery as
the durable store for learned mappings (simplest reliable option) and can be upgraded to Vertex AI
Feature Store online serving without changing the interface.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .dictionary import normalize_header


class FeatureStoreDictionary:  # pragma: no cover - requires GCP libs/creds
    """BigQuery-backed learned dictionary (MVP implementation of the Feature Store contract).

    Table schema (dataset `{cfg.bq_dataset}`, table `learned_dictionary`):
        namespace STRING, source_header STRING, canonical_column STRING,
        confidence FLOAT64, votes INT64, updated_at TIMESTAMP
    """

    def __init__(self, config):
        from google.cloud import bigquery
        self.config = config
        self.client = bigquery.Client(project=config.gcp_project)
        self.table = f"{config.gcp_project}.{config.bq_dataset}.learned_dictionary"

    def lookup(self, source_header: str, tenant_id: str) -> Optional[Dict]:
        key = normalize_header(source_header)
        query = f"""
            SELECT namespace, source_header, canonical_column, confidence, votes
            FROM `{self.table}`
            WHERE source_header = @h AND namespace IN (@tenant, 'global')
            ORDER BY (namespace = @tenant) DESC, confidence DESC
            LIMIT 1
        """
        from google.cloud import bigquery
        job = self.client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("h", "STRING", key),
                bigquery.ScalarQueryParameter("tenant", "STRING", tenant_id),
            ]))
        for r in job.result():
            return dict(r)
        return None

    def promote(self, source_header: str, canonical_column: str, tenant_id: str,
                confidence: float) -> Dict:
        key = normalize_header(source_header)
        merge = f"""
            MERGE `{self.table}` T
            USING (SELECT @ns AS namespace, @h AS source_header, @c AS canonical_column,
                          @conf AS confidence) S
            ON T.namespace = S.namespace AND T.source_header = S.source_header
               AND T.canonical_column = S.canonical_column
            WHEN MATCHED THEN UPDATE SET votes = T.votes + 1,
                 confidence = LEAST(1.0, (T.confidence + S.confidence)/2 + 0.05),
                 updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (namespace, source_header, canonical_column, confidence,
                 votes, updated_at)
                 VALUES (S.namespace, S.source_header, S.canonical_column, S.confidence, 1,
                 CURRENT_TIMESTAMP())
        """
        from google.cloud import bigquery
        self.client.query(merge, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ns", "STRING", tenant_id),
                bigquery.ScalarQueryParameter("h", "STRING", key),
                bigquery.ScalarQueryParameter("c", "STRING", canonical_column),
                bigquery.ScalarQueryParameter("conf", "FLOAT64", confidence),
            ])).result()
        return {"namespace": tenant_id, "source_header": key,
                "canonical_column": canonical_column, "confidence": confidence, "votes": 1}

    def all_entries(self, tenant_id: str) -> List[Dict]:
        query = f"""
            SELECT * FROM `{self.table}` WHERE namespace IN (@tenant, 'global')
        """
        from google.cloud import bigquery
        job = self.client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("tenant", "STRING", tenant_id)]))
        return [dict(r) for r in job.result()]
