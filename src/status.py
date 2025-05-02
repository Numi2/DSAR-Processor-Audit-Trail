"""Provide job status, QLDB events stream OR presigned download URL."""

from __future__ import annotations

import json
import os
from typing import Dict

import boto3

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

TABLE_NAME = os.environ["DSAR_TABLE"]
BUCKET_NAME = os.environ["DSAR_BUCKET"]


def _json(body: Dict, status_code: int = 200):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _get_job_meta(job_id: str) -> Dict | None:
    table = dynamodb.Table(TABLE_NAME)
    response = table.get_item(Key={"pk": job_id, "sk": "META"})
    return response.get("Item")


def _generate_download_redirect(job_id: str):
    key = f"dsar/{job_id}/bundle.zip"
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=86_400,  # 24h
    )
    return {
        "statusCode": 302,
        "headers": {"Location": url},
        "body": "",
    }


# Lambda Function entrypoint

def handler(event, context):  # type: ignore[override]
    path_params: Dict = event.get("pathParameters", {})
    # httpApi proxies param names without curly braces; adapt if necessary
    job_id: str = path_params.get("jobId")

    if not job_id:
        return _json({"message": "jobId missing in path"}, 400)

    # Distinguish /download subpath quick & dirty
    raw_path: str = event.get("rawPath", "")
    if raw_path.endswith("/download"):
        return _generate_download_redirect(job_id)

    # /events not implemented – could call QLDB Session API; placeholder
    if raw_path.endswith("/events"):
        return _json({"message": "Not implemented – integrate QLDB"}, 501)

    # /dsar/{jobId}
    meta = _get_job_meta(job_id)
    if not meta:
        return _json({"message": "Job not found"}, 404)

    return _json(meta)
