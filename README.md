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
#
# ## Quick-start (dev)
#
# ```bash
# # 1. Install tooling
# npm i -g serverless serverless-step-functions
#
# # 2. Deploy to a sandbox stage
# sls deploy --stage dev
#
# # 3. Create a DSAR job (replace API-ID / region / JWT)
# curl -X POST \
#   https://<api-id>.execute-api.<region>.amazonaws.com/dsar \
#   -H "Authorization: Bearer <cognito-jwt>" \
#   -d '{"user_id":"test@corp","action":"export"}'
#
# # 4. Poll status
# curl https://<api-id>.execute-api.<region>.amazonaws.com/dsar/JOB#xxxx \
#      -H "Authorization: Bearer <cognito-jwt>"
# ```
#
# ⚠️  The Cognito issuer/audience placeholders in `serverless.yml` must be replaced with your pool before step 3 works.
#
# ## Next steps for development
#
# 1. **Replace the stubs**
#    * `src/dsar_worker.py` – real SELECT/DELETE against Audit, Consent, AppDB, Logs.
#    * `src/export_bundler.py` – stream & zip partial exports, not empty file.
#    * `src/status.py` – implement `/events` via QLDB Session API.
#
# 2. **IAM hardening**
#    * Move from wildcard resources to least-privilege ARNs per Lambda.
#    * Add `sqs:ReceiveMessage` only to dispatcher, etc.
#
# 3. **Observability & alerts**
#    * CloudWatch alarms on DLQ > 0, Step-Functions `Failed`, Lambda errors.
#    * Structured logging already JSON; add Insights queries or OTEL exporter.
#
# 4. **Security**
#    * Use customer-managed KMS keys for S3, DynamoDB, SQS.
#    * Enable API Gateway WAF, rate limits, threat IP lists.
#    * Tweak presigned URL lifetime in bundler (defaults 24 h).
#
# 5. **Performance & cost**
#    * Set `MaxConcurrency` in the Map state if dozens of stores.
#    * Adjust Lambda memory (scales CPU) for `export_bundler` if >100 MB export.
#    * Create S3 lifecycle rule to expire `/dsar/*` after X days.
#
# 6. **Compliance / audits**
#    * Schedule QLDB `GetDigest` proof export for auditors.
#    * Tag resources (GDPR, owner, cost-centre) via CloudFormation metadata.
#
# 7. **CI/CD**
#    * Add GitHub Actions: lint → unit test (moto) → `sls deploy --stage prod`.
#    * Optionally run canary Step-Functions execution post-deploy.
#
# 8. **Integration tests**
#    * Use `pytest` + `moto` to mock AWS and assert:
#      – Dynamo row written
#      – SQS message sent
#      – SFN execution started
#      – Export file uploaded
#
# ## License
#
# Proprietary — internal use only (or add your preferred OSS license here).
