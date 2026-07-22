"""GCP sink for the Persister: write canonical rows + audit artifacts to BigQuery (GCP mode).

Requires the `gcp` extra and credentials. Tables (dataset `{cfg.bq_dataset}`):
    canonical_<schema>     : the mapped tabular data
    mapping_audit_report   : per-column mapping audit
    judge_decision_log     : governance verdicts
    review_queue           : items awaiting human review
"""
from __future__ import annotations

from typing import Dict

from ..config import Config
from ..models import PipelineResult


def write_to_gcp(result: PipelineResult, config: Config) -> Dict[str, str]:  # pragma: no cover
    from google.cloud import bigquery
    client = bigquery.Client(project=config.gcp_project)
    ds = f"{config.gcp_project}.{config.bq_dataset}"

    def _load(table: str, rows):
        if not rows:
            return
        job = client.load_table_from_json(
            rows, f"{ds}.{table}",
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                autodetect=True,
            ),
        )
        job.result()

    canonical_table = f"canonical_{result.schema_name}"
    tagged_rows = [{**r, "_tenant_id": result.tenant_id} for r in result.canonical_rows]
    _load(canonical_table, tagged_rows)
    _load("mapping_audit_report", [{**m, "_tenant_id": result.tenant_id}
                                   for m in result.mapping_audit_report()])
    _load("judge_decision_log", [{**d, "_tenant_id": result.tenant_id}
                                 for d in result.judge_decision_log()])
    _load("review_queue", [{**q, "_tenant_id": result.tenant_id} for q in result.review_queue])

    return {
        "canonical_table": f"{ds}.{canonical_table}",
        "mapping_audit_report": f"{ds}.mapping_audit_report",
        "judge_decision_log": f"{ds}.judge_decision_log",
        "review_queue": f"{ds}.review_queue",
    }
