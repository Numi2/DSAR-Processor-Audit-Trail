"""HTTP intake Lambda – creates a DSAR job and enqueues it for processing.

Expected request (API-Gateway HTTP API, JSON body):

POST /dsar
{
  "user_id": "abc123",
  "action": "export" | "delete"
}

Returns 202 Accepted with payload: { "jobId": "JOB#<uuid>" }
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Dict

import boto3

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

TABLE_NAME = os.environ["DSAR_TABLE"]
QUEUE_URL = os.environ.get("QUEUE_URL")  # injected via serverless.yml later

# Data stores we fan-out over – keep in sync with the Step-Functions definition
DATA_STORES = ["Audit", "Consent", "AppDB", "Logs"]


def _json(body: Dict, status_code: int = 200):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, context):  # type: ignore[override]
    try:
        payload = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return _json({"message": "Invalid JSON"}, 400)

    user_id = payload.get("user_id")
    action = (payload.get("action") or "").lower()

    if action not in {"export", "delete"} or not user_id:
        return _json({"message": "Missing/invalid parameters"}, 400)

    job_uuid = str(uuid.uuid4())
    job_id = f"JOB#{job_uuid}"

    # 1. Persist META record (partition key only)
    table = dynamodb.Table(TABLE_NAME)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    table.put_item(
        Item={
            "pk": job_id,
            "sk": "META",
            "user": user_id,
            "action": action,
            "status": "PENDING",
            "dataStores": DATA_STORES,
            "createdAt": now_iso,
        }
    )

    # 2. Enqueue message for dispatcher
    message_body = json.dumps({
        "jobId": job_id,
        "action": action,
        "dataStores": DATA_STORES,
    })

    if not QUEUE_URL:
        raise RuntimeError("QUEUE_URL env variable not set")

    sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=message_body)

    return _json({"jobId": job_id}, 202)
