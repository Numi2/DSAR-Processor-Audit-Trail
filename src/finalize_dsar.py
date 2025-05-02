"""Finalize a DSAR job – update status & notify subscribers."""

from __future__ import annotations

import os
import time
from typing import Dict

import boto3


dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

JOBS_TABLE_NAME = os.environ["DSAR_TABLE"]
TOPIC_ARN = os.environ.get("TOPIC_ARN")  # injected via env in serverless.yml


def _update_job_status(job_id: str, status: str) -> None:
    table = dynamodb.Table(JOBS_TABLE_NAME)
    table.update_item(
        Key={"pk": job_id, "sk": "META"},
        UpdateExpression="SET #s = :s, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status, ":u": int(time.time())},
    )


def _publish_notification(job_id: str, status: str) -> None:
    if not TOPIC_ARN:
        return

    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject=f"DSAR job {job_id} {status}",
        Message=f"The DSAR job '{job_id}' finished with status {status}.",
    )


def handler(event: Dict, context):  # type: ignore[override]
    job_id: str = event.get("jobId")
    status: str = event.get("status", "COMPLETED")

    _update_job_status(job_id, status)
    _publish_notification(job_id, status)

    return {"jobId": job_id, "status": status}
