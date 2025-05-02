"""DSAR Worker Lambda

Per-store executor that either exports or deletes user data as part of a DSAR
job. The function is invoked in parallel by Step Functions’ `Map` state.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import boto3


# --- AWS clients (re-used across invocations) --------------------------------
s3 = boto3.client("s3")

# Environment variables provided through `serverless.yml` ----------------------
BUCKET = os.environ["DSAR_BUCKET"]


# -----------------------------------------------------------------------------
# Helpers (replace with real store-specific logic)
# -----------------------------------------------------------------------------


def _mock_export_from_store(store: str) -> Dict[str, Any]:
    """Return dummy JSON for the requested store (demo only)."""

    return {
        "store": store,
        "records": [
            {
                "id": 1,
                "payload": f"demo data from {store}",
            }
        ],
        "exportedAt": int(time.time()),
    }


def _mock_delete_from_store(store: str) -> None:
    """Pretend to delete or TTL-flag data (demo only)."""

    print(f"[MOCK] delete called for store={store}")


def _write_export_to_s3(job_id: str, store: str, payload: Dict[str, Any]) -> None:
    key = f"dsar/{job_id}/{store}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(payload).encode(),
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
    )


# -----------------------------------------------------------------------------
# Lambda entry-point
# -----------------------------------------------------------------------------


def handler(event: dict, context):  # type: ignore[override]
    """Step-Functions task entrypoint."""

    job_id: str = event["jobId"]
    store: str = event["store"]
    action: str = event["action"].lower()

    if action == "export":
        payload: Dict[str, Any] = _mock_export_from_store(store)
        _write_export_to_s3(job_id, store, payload)
    elif action == "delete":
        _mock_delete_from_store(store)
    else:
        raise ValueError(f"Unsupported action: {action}")

    return {
        "jobId": job_id,
        "store": store,
        "status": "COMPLETED",
    }
