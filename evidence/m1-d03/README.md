# M1-D03 AgentCore implementation

Demo: `notebooks/03_agentcore.ipynb` (executed outputs saved in the notebook).
Deployment method: AgentCore CLI **0.30.0** (`ControlsAssistant/`), CodeZip build, CDK stack `AgentCore-ControlsAssistant-default`.
Backends (Cognito, DynamoDB, Lambda, KB, Guardrail) are created by the scripts in `scripts/`.

## Deployment configuration

- `ControlsAssistant/agentcore/agentcore.json`: runtime (Python 3.13, CUSTOM_JWT inbound auth, `requestHeaderAllowlist: [Authorization]`, env vars), memory, gateway, gateway target
- `ControlsAssistant/agentcore/aws-targets.json`: account and Region
- `ControlsAssistant/app/controlsagent/iam-extra.json`: extra runtime permissions (approved models only, this KB, this Guardrail)
- `ControlsAssistant/tools-schema.json`: Gateway tool schemas
- Steps: README sections "Create everything" and "Updates and rollback"

## Resource inventory (2026-11-22)

| Resource | ID / name | Created by |
|---|---|---|
| AgentCore Runtime | `ControlsAssistant_controlsagent-aSkEpJCs28` (version 3, READY) | CLI / CDK |
| Runtime execution role | `AgentCore-ControlsAssista-ApplicationAgentControlsa-*` | CLI / CDK |
| AgentCore Memory | `ControlsAssistant_controlsagentMemory-DujSZkDuRL` (USER_PREFERENCE, events expire in 7 days) | CLI / CDK |
| AgentCore Gateway | `controlsassistant-controls-gateway-vgx2088dq0` (MCP, CUSTOM_JWT) | CLI / CDK |
| Gateway target | `controls-tools` -> Lambda | CLI / CDK |
| Gateway role + 2 IAM policies | CDK generated | CLI / CDK |
| Tools Lambda | `fs-controls-assistant-tools` (Python 3.13, 15 s timeout) | `setup_tools.py` |
| Lambda role | `fs-controls-assistant-tools-lambda-role` (GetItem on one table, own logs) | `setup_tools.py` |
| DynamoDB | `fs-controls-assistant-records` (on-demand) | `setup_tools.py` |
| Cognito | user pool `us-east-1_trSgC3XJH`, client `60rl20utgl8lq1nfj9vkp38v8f`, users alice, bob | `setup_identity.py` |
| Knowledge Base | `ERPMMNIAXI` + S3 Vectors bucket/index + docs bucket + KB role | `setup_kb.py` |
| Guardrail | `m7s47f1674sc` version 1 | `setup_guardrail.py` |

All script-created resources are tagged `owner=ppathak`, `project=fs-controls-assistant`, `purpose=bedrock-training`.

## Tool schemas

Gateway (`tools-schema.json`): `get_control_status(control_id, caller_token)`, `get_evidence_status(control_id, caller_token)`.
Model-facing (Strands `@tool` in `main.py`): `get_control_status(control_id)`, `get_evidence_status(control_id)`, `search_policies(question)`.
The model never sees `caller_token`. Agent code adds it from the verified request.

Handled cases in code: missing record (`not_found`), invalid ID (`invalid_argument`, checked in agent and Lambda), malformed arguments, tool timeout (5 s, not retried), retryable errors (`throttled`, 5xx: 2 retries with backoff), tool-call limit (6), unauthenticated token, access denied.

## Permission map

See `docs/architecture.md`, "Trusted identity path" and "Permission map".

## Identity tests

| Test | Expected | Result |
|---|---|---|
| alice reads CTL-003 (her team) | allowed | answered, `deficient` |
| alice reads CTL-002 (bob's team) | denied in backend | tool error `access_denied`, no data leaked |
| bob sends `actor_id: alice` and asks for CTL-001 | forged field ignored | `actor_id=bob`, `ignored_identity_fields={"actor_id": "alice"}`, `access_denied` |
| no token | rejected before agent code | HTTP 403 from Runtime |
| alice asks to mark CTL-003 effective | no write path | refused, no write tool exists |

Repeated in every evaluation run (A01-A04).

## Memory evidence

- Strategy: built-in USER_PREFERENCE, namespace `/users/{actorId}/preferences`. Actor ID = verified username.
- Same-session recall: short-term events in the same runtime session (M01).
- Cross-session recall: after async extraction. The eval and notebook poll `list_memory_records` up to 180 s, every 5 s, before asking in a new session (M02). Observed wait: see `evidence/m1-d04/*.json` field `memory_wait`.
- Two-user isolation: bob asking about alice's preference, with and without a forged `actor_id`, gets nothing (M03, M04).
- Timeout behavior: if no record appears in 180 s, the runner records `memory_wait.found=false` and the case fails. It does not assert recall it could not observe.
- Retention: events expire after 7 days. Long-term records stay until deleted (eval deletes both users' records before each run). Teardown deletes the Memory resource.
- What belongs where: preferences in memory; policy text in the KB; control/evidence status in DynamoDB via tools. Memory is never used as a source of facts.
