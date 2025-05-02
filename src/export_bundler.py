"""Aggregate per-store exports into a single encrypted archive.

The real-world implementation would:
    1. list_objects_v2 under the job prefix (dsar/<jobId>/)
    2. stream each object into a zipfile
    3. upload the zipped artefact back to S3 with SSE-KMS
    4. generate a presigned download URL

We keep the example minimal and focus on steps 3 + 4 only so the snippet can be
deployed without third-party dependencies (i.e. no `zipfile` usage). Replace
the mock-ups as necessary.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict

import boto3

s3 = boto3.client("s3")

BUCKET = os.environ["DSAR_BUCKET"]


def _create_empty_placeholder(job_id: str) -> str:
    """Upload an empty placeholder ZIP so the flow remains functional."""

    key = f"dsar/{job_id}/bundle.zip"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=b"",  # empty file
        ContentType="application/zip",
        ServerSideEncryption="aws:kms",
    )
    return key


def _generate_presigned_url(key: str, expiry_seconds: int = 86_400) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expiry_seconds,
    )


def handler(event: Dict, context):  # type: ignore[override]
    job_id: str = event["jobId"]

    # Create placeholder artefact (real impl would zip partial exports)
    key = _create_empty_placeholder(job_id)

    url = _generate_presigned_url(key)

    return {
        "jobId": job_id,
        "bundleKey": key,
        "downloadUrl": url,
        "generatedAt": int(time.time()),
    }
