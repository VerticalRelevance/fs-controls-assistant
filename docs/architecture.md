# Architecture

```
CLI test client (src/controls_assistant/agent_client.py)
  | Cognito USER_PASSWORD_AUTH -> access token for alice or bob
  v
AgentCore Runtime  (inbound auth: CUSTOM_JWT, Cognito discovery URL, allowed client ID)
  | passes the Authorization header to the agent (requestHeaderAllowlist)
  v
Strands agent (ControlsAssistant/app/controlsagent/main.py), model us.amazon.nova-2-lite-v1:0
  |- Guardrail ApplyGuardrail on user input  -> blocked = stop
  |- search_policies  -> Bedrock KB Retrieve (S3 Vectors, Titan Embed v2)
  |                      -> each passage: ApplyGuardrail prompt-attack check, drop if flagged
  |- get_control_status / get_evidence_status
  |      -> AgentCore Gateway (MCP, inbound CUSTOM_JWT with the SAME user token)
  |         -> Lambda fs-controls-assistant-tools
  |              - validates the token itself with Cognito GetUser -> username
  |              - reads team scope USER#<username> from DynamoDB
  |              - denies records owned by other teams
  |- AgentCore Memory: actor ID = verified username, session ID = runtime session
  |      short-term events + long-term USER_PREFERENCE strategy (/users/{actorId}/preferences)
  |- Guardrail ApplyGuardrail on final output
  v
CloudWatch logs + OpenTelemetry spans (AgentCore Observability, Transaction Search)
```

## Trusted identity path

1. Client logs in to Cognito and gets a signed access token. Nothing else identifies the user.
2. AgentCore Runtime validates the token signature, issuer, and client ID before the agent code runs. No token -> HTTP 401/403.
3. The agent reads the username from the already validated token. `actor_id`, `user_id`, or `username` in the payload are ignored and logged as `ignored_payload_identity`.
4. The agent calls Gateway with the same user token. Gateway validates it again.
5. The agent code (not the model) adds the token as `caller_token` to the tool arguments. The model's tool schema has only `control_id`.
6. The Lambda validates the token again with Cognito and gets the username from Cognito, not from the arguments. It then checks team scope.

So the backend decision never depends on prompt text or model output. Execution roles and memory IDs alone do not grant user access.

## Permission map

| Question | Enforced by | Where |
|---|---|---|
| Is the caller a real user? | AgentCore Runtime CUSTOM_JWT authorizer | `agentcore.json` runtime `authorizerConfiguration` |
| Which user is this? | Verified token `username` claim | `main.py` `invoke()` |
| Can the agent reach the tools? | Gateway CUSTOM_JWT (same Cognito pool and client) | `agentcore.json` gateway |
| Which tools exist? | Gateway target tool schema (2 read-only tools) + agent tool list | `tools-schema.json`, `main.py TOOLS` |
| Are tool arguments valid? | Agent code regex, then Lambda regex | `main.py gateway_tool()`, `lambda_tools/handler.py` |
| Can this user see this record? | Lambda: Cognito-verified username -> DynamoDB team scope -> record owner | `lambda_tools/handler.py run()` |
| Can the agent call models, KB, Guardrail? | Runtime execution role (CDK) + `iam-extra.json` (only approved models, this KB, this Guardrail) | `app/controlsagent/iam-extra.json` |
| Can the Lambda read data? | Lambda role: `dynamodb:GetItem` on one table, own log group | `scripts/setup_tools.py` |
| Can the KB read docs? | KB role: one bucket, one vector index, Titan Embed only | `scripts/setup_kb.py` |
| Whose memory is read or written? | Actor ID set from verified username in code | `main.py get_agent()`, `memory/session.py` |
| Is content safe? | Guardrail v1 on input, retrieved passages, output | `policy_search.py` |

## Stores

| Store | Holds | Not for |
|---|---|---|
| S3 docs bucket + KB (S3 Vectors) | Policy, standard, runbook, catalog documents with version metadata | Live status, user data |
| DynamoDB `fs-controls-assistant-records` | Authoritative control and evidence status, user team scope | Policy text |
| AgentCore Memory | Harmless user preferences (answer format, name to use) and this session's turns | Facts about controls or policy. Those always come from tools or the KB. |
| `.state/resources.json` (local) | Resource IDs and test passwords | Never committed |

## Why an agent and not a fixed workflow

The combined journey (policy requirement + live status + gap) needs both retrieval and tools, in an order that depends on the question.
A fixed workflow would work for one journey but not for the mix of questions users ask. The agent is kept bounded: 3 tools, all read-only, max 6 tool calls, 5 s tool timeout, 2 retries only for retryable errors.

## Why a code-defined Strands agent and not the managed Harness

Owning the agent loop lets us put identity, argument checks, Guardrail screening of passages, and fault handling in code we can test and explain. The Harness would hide those points.
