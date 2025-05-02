# DSAR-Processor (Lean Edition)
#
# This project implements a privacy **D**ata **S**ubject **A**ccess **R**equest (DSAR) workflow with only seven AWS managed services and three Lambda functions — small enough to reason about, powerful enough to ship.
#
# ## Architecture
#
# ```
#           ┌────────────┐          (1) POST /dsar
#           │  Client    │ ─────────────────────────────┐
#           └────────────┘                              │
#                                                      ▼
#                      ┌───────────────────────────────┐
#                      │  Amazon API Gateway (HTTP API)│
#                      └────────────┬──────────────────┘
#                                   │  Cognito JWT auth
#                       ┌───────────▼───────────┐
#                       │  intake Lambda        │
#            DynamoDB ◄─┤  (create job)         │─► SQS
#                       └───────────┬───────────┘
#                                   │  (SQS event)
#                       ┌───────────▼───────────┐
#                       │  dispatcher Lambda    │
#                       └───────────┬───────────┘
#                                   │  StartExecution
#                    ┌──────────────▼───────────────┐
#                    │  Step Functions State Machine │
#                    └─┬──────────┬───────────────┬──┘
#                      │          │               │
#              (Map) dsar-worker Lambdas …        │
#                      │          │               │
#                    QLDB ledger inserts          │
#                                                ▼
#                                     export-bundler Lambda
#                                                ▼
#                                       finalize-dsar Lambda
#                                                ▼
#                                             SNS (notify)
# ```
#
# Main artefacts live in:
#
# * **serverless.yml**    — infrastructure as code (functions, queues, tables, IAM, SFN)
# * **src/**              — Lambda source code (Python 3.11)
## DSAR Processor
    #
    #Welcome to the **DSAR Processor** — an educational, end-to-end example
    showing how to build a robust
    #Data Subject Access Request (DSAR) workflow on AWS using fully managed
    services and minimal custom code.
    #
    #This tutorial-style repository walks you through:
    #- Understanding DSAR requirements under GDPR/CCPA
    #- Designing a scalable, secure architecture with AWS
    #- Implementing a single HTTP API endpoint for intake
    #- Orchestrating parallel data operations with Step Functions
    #- Capturing an immutable audit trail in QLDB
    #- Bundling and encrypting exports in S3 with SSE-KMS
    #- Notifying stakeholders and exposing status endpoints
    #
    #Whether you’re new to serverless architectures or looking for a reference
    implementation,
    #this project will serve as both a practical guide and a template to adapt
    in your environment.
    #
    #---
    #
    ### Table of Contents
    #1. [Background: What is a DSAR?](#background-what-is-a-dsar)
    #2. [Architecture Overview](#architecture-overview)
    #   - [AWS Services at a Glance](#aws-services-at-a-glance)
    #3. [Detailed Workflow](#detailed-workflow)
    #   1. [API & Intake](#1-api--intake)
    #   2. [Orchestration](#2-orchestration)
    #   3. [Packaging & Delivery](#3-packaging--delivery)
    #   4. [Finalization & Notification](#4-finalization--notification)
    #   5. [Status & Retrieval](#5-status--retrieval)
    #4. [Project Structure & Code
    Walkthrough](#project-structure--code-walkthrough)
    #5. [Getting Started](#getting-started)
    #6. [Local Development & Testing](#local-development--testing)
    #7. [Extending the Workflow](#extending-the-workflow)
    #8. [Security & Compliance](#security--compliance)
    #9. [Observability & Monitoring](#observability--monitoring)
    #10. [Troubleshooting](#troubleshooting)
    #11. [Cleanup](#cleanup)
    #12. [Contributing](#contributing)
    #
    #---
    #
    ### Background: What is a DSAR?
    #
    #A Data Subject Access Request (DSAR) is a formal request by an individual
    to access or delete
    #their personal data held by an organization. Under regulations such as GDPR
     (EU) and CCPA (California),
    #organizations are legally obligated to:
    #
    #1. Provide a copy of all personal data related to the individual.
    #2. Delete or anonymize personal data upon request, unless retention is
    required for legal or operational reasons.
    #
    #Key challenges in implementing a DSAR solution:
    #- Securely authenticating and validating requests
    #- Tracking request state and metadata reliably
    #- Searching multiple, heterogeneous data stores
    #- Maintaining a verifiable audit log of every action
    #- Bundling, encrypting, and delivering potentially large datasets
    #- Handling failures, retries, and error notifications
    #
    #This project addresses these challenges using AWS’s serverless building
    blocks.
    #
    ### Architecture Overview
    #
    #Below is a simplified depiction of the DSAR Processor architecture:
    #
    #```text
    #Client → API Gateway → createDSAR (Lambda)
    #              ↓           ↙ DynamoDB (metadata)
    #              ↓           ↘ SQS (message queue)
    #              ↓
    #       sqsStarter (Lambda) → Step Functions state machine
    #              ↓                   ↓ (Map → dsarWorker # QLDB)
    #              ↓                   ↓ (Choice → exportBundler)
    #              ↓                   ↓ finalizeDSAR (Lambda)
    #              ↓                   ↓ DynamoDB update # SNS notify
    #
    #Additional HTTP GET Endpoints:
    #  • /dsar/{jobId}        → createDSAR metadata from DynamoDB
    #  • /dsar/{jobId}/events → audit log from QLDB
    #  • /dsar/{jobId}/download → 302 redirect to S3 presigned URL
    #```
    #
    #### AWS Services at a Glance
    #
    #| Purpose               | AWS Service                          |
    #|-----------------------|--------------------------------------|
    #| API # Auth            | API Gateway (HTTP API # JWT/OAuth)   |
    #| Metadata Store        | DynamoDB                             |
    #| Queueing              | SQS                                  |
    #| Orchestration         | Step Functions                       |
    #| Compute               | Lambda (intake, worker, bundler, finalize,
    status) |
    #| Audit Trail           | QLDB                                 |
    #| Artifact Storage      | S3 (SSE-KMS encryption)              |
    #| Notifications         | SNS                                  |
    #
    ### Detailed Workflow
    #
    #### 1. API & Intake
    #
    #1. **Client** issues `POST /dsar` with JSON payload:
    #   ```json
    #   {
    #     "user_id": "12345",
    #     "action": "export"    // or "delete"
    #   }
    #   ```
    #2. **`createDSAR` Lambda**:
    #   - Parses and validates the request body.
    #   - Generates a unique `jobId` (UUID).
    #   - Writes job metadata to DynamoDB (`status="PENDING"`).
    #   - Enqueues an SQS message containing `{ jobId, action }`.
    #3. Responds with **200 OK** and `{ "jobId": "<uuid>" }`.
    #
    #### 2. Orchestration
    #
    #1. **`sqsStarter` Lambda** (triggered by SQS):
    #   - Receives message `{ jobId, action }`.
    #   - Starts an execution of the Step Functions state machine,
    #     passing in `jobId`, `action`, and the list of data stores.
    #2. **Step Functions** state machine:
    #   - **Map** state iterates over `dataStores` (e.g.,
    ["Audit","Consent","AppDB","Logs"]):
    #     a. Invokes **`dsarWorker` Lambda** with `{ jobId, action, store }`.
    #     b. Inserts a document into QLDB (`INSERT INTO Events VALUE {...}`).
    #   - **Choice** state: if `action == "export"`, call **`exportBundler`
    Lambda**.
    #   - **Finalize** state: call **`finalizeDSAR` Lambda**.
    #
    #### 3. Packaging & Delivery
    #
    #**`dsarWorker` Lambda** behavior:
    #- **Export**: fetch data from the specified store, write JSON to S3 at
    `dsar/<jobId>/<store>.json`.
    #- **Delete**: perform deletion or TTL-flag operations in the target store.
    #
    #**`exportBundler` Lambda**:
    #- Lists all partial JSON files under `dsar/<jobId>/` in S3.
    #- Streams them into an in-memory ZIP archive.
    #- Uploads `dsar/<jobId>.zip` to S3 with SSE-KMS encryption.
    #- Generates a presigned download URL (e.g., valid for 1 hour).
    #
    #### 4. Finalization & Notification
    #
    #**`finalizeDSAR` Lambda**:
    #- Updates the DynamoDB job record: sets `status = "COMPLETED"`, adds
    `completedAt` timestamp,
    #  and stores `downloadUrl` if exists.
    #- Publishes a notification to SNS with job details and link.
    #
    #### 5. Status & Retrieval
    #
    #API Gateway # Lambda provides:
    #- `GET /dsar/{jobId}` → returns job metadata from DynamoDB.
    #- `GET /dsar/{jobId}/events` → queries QLDB for audit log entries.
    #- `GET /dsar/{jobId}/download` → 302 redirect to the presigned S3 URL.
    #
    ### Project Structure & Code Walkthrough
    #
    #```text
    #├── serverless.yml        # Infrastructure-as-code for Serverless Framework
    #├── lambdas
    #│   ├── create_dsar       # intake: DynamoDB # SQS
    #│   ├── sqs_starter       # SQS → Step Functions starter
    #│   ├── dsar_worker       # per-store export/delete logic
    #│   ├── export_bundler    # zip # encrypt exports
    #│   ├── finalize_dsar     # update status # SNS
    #│   ├── get_status        # GET /dsar/{jobId}
    #│   ├── get_events        # GET /dsar/{jobId}/events
    #│   └── get_download      # GET /dsar/{jobId}/download
    #└── docs
    #    └── architecture.png  # optional architecture diagram
    #```
    #
    #Each Lambda has its own folder with:
    #- `app.py`   — handler code
    #- `requirements.txt` (if dependencies are needed)
    #- `tests/`   — unit tests (recommended)
    #
    ### Getting Started
    #
    ### Prerequisites
    #
    #- **AWS CLI** configured with an account that can create IAM, Lambda, SFN,
    DynamoDB, SQS, QLDB, S3, SNS.
    #- **Node.js** (for Serverless CLI) and **npm** (≥ 14).
    #- **Python 3.9** and **pip** (for Lambda packages).
    #
    ### Deploy to AWS
    #
    ```bash
    # Install Serverless Framework & plugin
    tnpm install -g serverless serverless-step-functions

    # (Optional) setup a Python virtual environment
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

    # Deploy all resources
    serverless deploy
    ```
    #
    > After deployment, note the HTTP API endpoint printed by `serverless
    deploy`.
    #
    ### Local Development & Testing
    #
    #1. **serverless-offline** (simulate API Gateway locally):
    #   ```bash
    #   npm install --save-dev serverless-offline
    #   serverless offline
    #   ```
    #2. **Invoke Lambdas Locally**:
    #   ```bash
    #   serverless invoke local --function createDSAR --path
    test/events/create_dsar.json
    #   ```
    #3. **Unit Tests**:
    #   - Use `pytest` in each Lambda folder.
    #   - Mock AWS calls with [`moto`](https://github.com/spulec/moto).
    #
    ### Extending the Workflow
    #
    > The default `dsar_worker` uses placeholder logic. Customize the following:
    #
    #- **dsar_worker/app.py**: implement real SELECT or DELETE for each data
    store (RDS, DynamoDB,
    #  Elasticsearch, external APIs, etc.).
    #- **get_events/app.py**: write PartiQL queries against QLDB to retrieve the
     audit log.
    #- **Error Handling**: add DLQs, Step Functions `Retry` and `Catch` blocks,
    and Lambda timeouts.
    #
    ### Security & Compliance
    #
    #- Use API Gateway JWT authorizers or OAuth scopes for fine-grained access
    control.
    #- Principle of Least Privilege: review generated IAM roles and restrict
    permissions.
    #- Encrypt data at rest with SSE-KMS on S3, and enable encrypted DynamoDB
    and QLDB.
    #- Monitor access logs (API Gateway, CloudTrail) for auditing.
    #
    ### Observability & Monitoring
    #
    #- Enable CloudWatch Logs for all Lambdas and Step Functions.
    #- Use CloudWatch Metrics and Alarms to detect failures or throttling.
    #- Optionally, integrate AWS X-Ray for distributed tracing.
    #
    ### Troubleshooting
    #
    > **Missing permissions**: If deployment fails with `AccessDenied`, ensure
    your IAM user/role has
    > full rights for the resources (or pre-create QLDB ledger manually).
    #
    > **Lambda timeouts**: Increase the `timeout` and memory settings in
    `serverless.yml`.
    #
    > **Step Functions errors**: Review the visual workflow in the AWS Console;
    check input/output
    > in each state for mismatches.
    #
    ### Cleanup
    #
    #To tear down all deployed resources:
    #```bash
    #serverless remove
    #```
    #
    ### Contributing
    #
    #Contributions are welcome! Please:
    #1. Fork this repository.
    #2. Create a descriptive branch (e.g., `feature/add-elasticsearch-store`).
    #3. Add or update tests as appropriate.
    #4. Submit a pull request.
    #
    #---
    #
    #*Built with ❤ by the DevOps community.*