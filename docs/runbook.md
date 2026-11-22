# Runbook

All commands run from the repo root with `AWS_PROFILE=vr-training`. Log in first: `aws sso login --sso-session saml`.

## Where to look

| What | Where |
|---|---|
| Agent logs | CloudWatch log group `/aws/bedrock-agentcore/runtimes/ControlsAssistant_controlsagent-*-DEFAULT` |
| Agent traces | `cd ControlsAssistant && npx --prefix ../../agentcore-cli agentcore traces list`, or the CloudWatch GenAI Observability console |
| Tool backend logs | `/aws/lambda/fs-controls-assistant-tools` (one JSON line per call: tool, user, control_id, result) |
| Resource IDs | `.state/resources.json` (not committed) |

Each agent log line has `actor`, `session`, `status`, and tool errors. Search by session ID to follow one request.
Logs do not contain tokens or passwords. Prompts and answers stay in traces only.

## Symptoms and fixes

| Symptom | Likely cause | What to do |
|---|---|---|
| Answer says "timed out", status `incomplete` | Tool backend slower than 5 s | Check Lambda duration in its log group. The agent does not retry timeouts on purpose. |
| Status `incomplete`, error `throttled` | Backend or Bedrock throttling | Agent already retried 2 times with backoff. Wait and retry. Check Bedrock quotas if it is the model. |
| `ThrottlingException` from Bedrock | Model quota | boto3 standard retry mode retries 3 times. Lower eval concurrency or ask for a quota increase. |
| Answer says not enough evidence for a question that should be covered | Document missing or not ingested | Check `data/corpus/`, rerun `scripts/setup_kb.py` (it re-uploads and starts ingestion). Check ingestion stats for failures. |
| Ingestion job `FAILED` | KB role lacks S3/S3 Vectors/embedding permission, or bad metadata JSON | Read `failureReasons` printed by `setup_kb.py`. Fix and rerun. |
| `access_denied` tool error | User's team does not own the control | Expected. Scope is in DynamoDB items `USER#<name>`. |
| HTTP 401/403 from Runtime | Missing or expired token (60 min) | Log in again. The client gets a fresh token each run. |
| `unauthenticated` from the tool Lambda | Token rejected by Cognito `GetUser` | Token expired or revoked. Log in again. |
| Memory recall fails in a new session | Long-term extraction is asynchronous | Wait (usually 30-90 s). The eval polls up to 180 s. Check records with `list_memory_records` for `/users/<name>/preferences`. |
| SSO token expired during a script | SSO session ended | `aws sso login --sso-session saml`, then rerun. Setup scripts are safe to rerun. |

## Retention and deletion

- Short-term memory events expire after **7 days** (`eventExpiryDuration` in `ControlsAssistant/agentcore/agentcore.json`).
- Long-term preference records stay until deleted. Delete one user's records:
  `list_memory_records(memoryId, namespace="/users/<name>/preferences")` then `delete_memory_record` for each (see `reset_memory` in `evaluation/run_eval.py`).
- Deleting the Memory resource (teardown) deletes all events and records.
- KB documents: delete from S3 and run a sync (ingestion job). `dataDeletionPolicy=DELETE` removes their vectors.
- CloudWatch logs: default retention unless changed. Teardown deletes the runtime and Lambda log groups.

## Update and rollback

- Agent code or config: edit `ControlsAssistant/app/controlsagent/` or `agentcore.json`, then deploy (see README). Rollback: `git checkout <good commit> -- ControlsAssistant/` and deploy again.
- Guardrail: edit `scripts/setup_guardrail.py` and rerun. It publishes a new numbered version. Rollback: set `GUARDRAIL_VERSION` in `agentcore.json` env vars back to the old number and deploy. Old versions stay available.
- Documents: edit `data/corpus/`, rerun `scripts/setup_kb.py`. Rollback: the docs bucket has versioning on; restore the old object version and re-sync, or revert the file in git and rerun.

## Cleanup

`uv run python scripts/teardown.py --yes`, then check the output says no tagged resources remain.
Check again after a few minutes: `aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=fs-controls-assistant`.
