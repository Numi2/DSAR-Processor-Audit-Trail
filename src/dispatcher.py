"""SQS consumer that starts the Step Functions execution for each DSAR job."""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List

import boto3


sfn = boto3.client("stepfunctions")

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]


def _start_execution(body: Dict):
    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=body["jobId"].replace("JOB#", ""),
        input=json.dumps(body),
    )


def handler(event, context):  # type: ignore[override]
    records: List[Dict] = event.get("Records", [])
    for record in records:
        body = json.loads(record["body"])
        try:
            _start_execution(body)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to start execution: {exc}")
            # Raising ensures failed SQS item returns to queue / DLQ
            raise

    # Success – let Lambda delete messages via SQS integration implicitly
    return {
        "batchItemFailures": []
    }
