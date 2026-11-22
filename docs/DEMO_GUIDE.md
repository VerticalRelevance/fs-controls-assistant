# Demo guide (read this first)

## 30-minute prep

1. Log in: `aws sso login --sso-session saml`
2. Open the notebooks: `cd fs-controls-assistant && uv run jupyter lab notebooks/`
3. Read these 4 files once. They are the whole system (about 500 lines):
   - `ControlsAssistant/app/controlsagent/main.py` - the agent, identity handling, tools, guardrail calls
   - `ControlsAssistant/app/controlsagent/gateway_tools.py` - how tools are called through Gateway, timeout, retries
   - `lambda_tools/handler.py` - backend authorization (the most important security piece)
   - `src/controls_assistant/agent_loop.py` - the Week 1 tool loop (model proposes, code executes)
4. Read `docs/architecture.md` (diagram, trusted identity path, permission map).
5. Run notebook 03 top to bottom once. It takes about 4 minutes.

## 15-minute client-style walkthrough (suggested order)

| Min | Show | Where |
|---|---|---|
| 0-2 | Problem and design: one agent, one corpus, two read-only tools, two users | `docs/architecture.md` diagram |
| 2-5 | Grounded answer with citation, version conflict, abstention | notebook 02, sections 1-4 |
| 5-7 | Guardrail: denied topic, PII, poisoned document dropped | notebook 02, sections 5-7 |
| 7-10 | Deployed agent: combined journey (policy + status + gap), evidence tool | notebook 03, sections 1-2 |
| 10-12 | Security: access denied, forged actor ID ignored, no token rejected | notebook 03, sections 3-5 |
| 12-13 | Memory: same session, new session, bob cannot see alice's preference | notebook 03, sections 7-9 |
| 13-15 | Evaluation: 3 runs before/after, gates, cost per task, latency | notebook 04 |

## Required live items

**Demonstrate a failure:** notebook 03 section 6. CTL-900 makes the backend sleep 8 s, the agent's tool timeout is 5 s, so the answer says the result is incomplete. CTL-901 always throttles; the agent retries twice, then reports it. Show the trace:
```sh
cd ControlsAssistant && npx --prefix ../../agentcore-cli agentcore traces list --limit 5
npx --prefix ../../agentcore-cli agentcore traces get <traceId>
cd .. && uv run python scripts/trace_summary.py ControlsAssistant/agentcore/.cli/traces/controlsagent-<traceId>.json
```

**Explain a denied request:** alice asks for CTL-002 (notebook 03 section 3). Walk the path:
1. Runtime validated alice's JWT.
2. Agent called Gateway with alice's own token, Gateway validated it again.
3. Lambda called Cognito `GetUser` with that token and got `alice` from Cognito, not from the prompt.
4. DynamoDB says alice's teams are platform-security and platform-delivery. CTL-002 is owned by platform-infra.
5. Lambda returned `access_denied`. The model only reports it.
Then show the Lambda log line: CloudWatch `/aws/lambda/fs-controls-assistant-tools` has `{"tool": ..., "user": "alice", "control_id": "CTL-002", "result": "access_denied"}`.

**Small live change (be ready for one of these):**

| Change | File | How to deploy | What you will see |
|---|---|---|---|
| Change tool timeout 5 s to 10 s | `gateway_tools.py` `TOOL_TIMEOUT_SECONDS` | agent deploy (~3 min) | CTL-900 now succeeds or fails with not_found instead of timeout |
| Give alice access to CTL-002 | DynamoDB item `USER#alice`, add `platform-infra` | no deploy, edit `data/synthetic/dynamo_items.json` and rerun `scripts/setup_tools.py` | alice can now see CTL-002 |
| Add a denied topic | `scripts/setup_guardrail.py` CONFIG | rerun the script (new version), update `GUARDRAIL_VERSION` env var, deploy | the new topic is blocked |
| Change the abstain threshold | `policy_search.py` `MIN_SCORE` | agent deploy | more or fewer abstentions |
| Change a prompt rule | `main.py` `SYSTEM_PROMPT` | agent deploy | different answer style |
| Fastest (no deploy): Week 1 loop | `src/controls_assistant/agent_loop.py` `MAX_TOOL_CALLS = 1` | none, rerun notebook 01 | second tool call refused |

Agent deploy command: `cd ControlsAssistant && npx --prefix ../../agentcore-cli agentcore deploy --target default`

## Likely technical questions (short answers)

- **Why Nova 2 Lite?** Same correctness on the comparison, 2.5x faster, 6.5x cheaper. Sonnet 5 is the judge and fallback. Measured in `evidence/m1-d01/`.
- **Why S3 Vectors and not OpenSearch Serverless?** No hourly idle cost. Small corpus. Tradeoff: fewer search features (no hybrid search).
- **How do you stop prompt injection in documents?** Each passage goes through the Guardrail prompt-attack check and is dropped if flagged. The prompt also says documents are data. Tools are read-only, so even a successful injection cannot change data.
- **What does the Guardrail evaluate?** User input, each retrieved passage (prompt attack), and the final output. Tool results are not evaluated; they come from our own backend.
- **What if the model sends a fake user ID to a tool?** It cannot. The model's tool schema only has `control_id`. Our code adds the user's token, and the Lambda gets the user from Cognito.
- **What belongs in memory?** Harmless preferences only. Control status and policy facts always come from tools or the KB, because memory can be stale.
- **Why is memory recall in a new session slow?** Long-term extraction is asynchronous. The eval polls up to 180 s before asking.
- **What would change for real client documents?** Private data source with document-level permissions (metadata filters per caller, or separate KBs per tenant), KMS customer keys, VPC endpoints, no PII in logs, data residency review.
- **What if Bedrock throttles?** boto3 standard retries (3), agent tool retries (2) for retryable backend errors, explicit incomplete answer when retries run out.
- **How do you know answers are grounded?** Deterministic citation checks (cited source must be one that was retrieved) plus a Sonnet 5 judge for groundedness, plus a human review of 10 cases.

## Evaluation numbers to quote

- Baseline 26/30, 26/30, 25/30. Final 27/30, 27/30, 28/30 (gate needs 27).
- Authorization 12/12, failure recovery 9/9, content safety 9/9 in both baseline and final.
- One improvement: `cite_as` on each passage. Grounding 25/30 -> 27/30.
- Median 9.0 s, p95 12.3 s, error rate 0, about $0.001 model cost per successful task.
- Full write-up: `evidence/m1-d04/README.md`.

## Be ready for this question: "Is M03/M04 a memory leak?"

No. Show notebook 03 section 9: bob's preference record count is 0, his actor ID is bob, and the forged field is listed as ignored.
The automatic check failed because bob's answer offered "bullet points" as an example format.
Also say you found a real issue: bob is sometimes told "you prefer short answers". That comes from the system prompt rule "Keep answers short", not from memory. It is in the backlog.

## Limits to say out loud

- The caller token is passed to the tool Lambda as an argument. Gateway tool logs could contain it. Production fix: a Gateway request interceptor or a signed internal token instead.
- One Region, one account, no VPC.
- The judge and the evaluation are training measurements, not production guarantees.
