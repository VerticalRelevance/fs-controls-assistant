# Financial Services Controls Assistant

Training project for the VR "Amazon Bedrock and AgentCore" module (M1). Synthetic data only.

A policy question returns cited facts with the policy version. Unsupported questions abstain.
Status questions use live tool results. A combined question retrieves the requirement, checks the record, and explains the gap.
Two Cognito users (alice, bob) see only their own team's records and their own memories.

Architecture and permission map: [docs/architecture.md](docs/architecture.md).
Runbook: [docs/runbook.md](docs/runbook.md). Costs: [docs/cost-worksheet.md](docs/cost-worksheet.md).

## Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/), AWS CLI v2, Node 20+
- AgentCore CLI **0.30.0** pinned in `../agentcore-cli`:
  `mkdir ../agentcore-cli && cd ../agentcore-cli && npm install --save-exact @aws/agentcore@0.30.0`
- AWS profile `vr-training` (VR Labs account, us-east-1). Log in: `aws sso login --sso-session saml`
- CDK bootstrapped in the account and Region (already done in Labs)

```sh
uv sync
cp .env.example .env        # AWS_PROFILE=vr-training, AWS_REGION=us-east-1, model IDs
uv run python scripts/check_access.py
```

All scripts refuse to run unless `AWS_PROFILE` starts with `vr-`.

## Create everything (about 15 minutes)

Each script saves IDs in `.state/resources.json` (not committed) and is safe to rerun.

```sh
uv run python scripts/setup_kb.py          # S3 docs bucket, S3 Vectors index, KB role, Knowledge Base, ingestion
uv run python scripts/setup_guardrail.py   # Guardrail + numbered version
uv run python scripts/setup_identity.py    # Cognito pool, app client, users alice and bob
uv run python scripts/setup_tools.py       # DynamoDB records, tools Lambda
```

Copy `KNOWLEDGE_BASE_ID`, `GUARDRAIL_ID`, `GUARDRAIL_VERSION` printed above into `.env`.

Then deploy the agent. In a fresh account, update the IDs in `ControlsAssistant/agentcore/agentcore.json`
(Cognito discovery URL and client ID for the runtime and gateway, env vars, Lambda ARN), `aws-targets.json` (account),
and `app/controlsagent/iam-extra.json` (KB and Guardrail ARNs). Then:

```sh
cd ControlsAssistant
npx --prefix ../../agentcore-cli agentcore validate
npx --prefix ../../agentcore-cli agentcore deploy --target default
```

The deploy prints the Gateway URL. Put it in the runtime env var `GATEWAY_URL` in `agentcore.json` and deploy again.
Save the outputs (runtime ARN, memory ID, gateway URL and ID, stack name) into `.state/resources.json`
(keys `runtime_arn`, `memory_id`, `gateway_url`, `gateway_id`, `agentcore_stack`).

Resources the deploy creates (CloudFormation stack `AgentCore-ControlsAssistant-default`):
AgentCore Runtime + execution role, Memory (user preference strategy), Gateway + target + gateway role, Transaction Search setup.

## Ingest or update documents

Edit or add files in `data/corpus/` (each `.md` with a `.md.metadata.json` holding `source_id`, `version`, `effective_date`, `status`).
Then rerun `uv run python scripts/setup_kb.py`. It uploads and starts an ingestion job, and prints the statistics.

## Use

```sh
# Deployed agent, as a test user (new session each time unless --session is given)
uv run python -m controls_assistant.agent_client --user alice "Does CTL-003 meet the deploy approval policy?"
uv run python -m controls_assistant.agent_client --user bob --extra '{"actor_id": "alice"}' "What is the status of CTL-001?"
uv run python -m controls_assistant.agent_client --user none "Hello"      # unauthenticated, rejected

# Local Week 1 pieces
uv run python -m controls_assistant.cli --verbose "What is the status of CTL-003?"
uv run pytest -q
```

Demo notebooks: `uv run jupyter lab notebooks/` (01 foundations, 02 RAG and Guardrails, 03 AgentCore, 04 evaluation).

## Evaluate

```sh
uv run python evaluation/run_eval.py --label baseline --runs 3
uv run python evaluation/run_eval.py --label final --runs 3
uv run python evaluation/run_eval.py --label check --runs 1 --only G01,A02,M03
```

Scenarios: `evaluation/scenarios.json` (30, frozen). Results: `evidence/m1-d04/`. Write-up: `evidence/m1-d04/README.md`.

## Updates and rollback

- Agent: change code under `ControlsAssistant/app/controlsagent/`, deploy. Roll back with `git checkout <commit> -- ControlsAssistant/` and deploy.
- Guardrail: change `scripts/setup_guardrail.py`, rerun (new version). Roll back by pointing `GUARDRAIL_VERSION` to the old version and deploying.
- Documents: the docs bucket is versioned. Revert the file in git and rerun `setup_kb.py`.

## Teardown

```sh
uv run python scripts/teardown.py --yes
```

Deletes the AgentCore stack, Lambda, roles, DynamoDB table, Cognito pool, Knowledge Base, Guardrail, S3 Vectors, docs bucket, and log groups.
It prints any resource still tagged `project=fs-controls-assistant`. The tagging API can lag a few minutes.

## Layout

| Path | What |
|---|---|
| `ControlsAssistant/` | AgentCore CLI project: `agentcore/agentcore.json` (config), `app/controlsagent/` (agent code) |
| `lambda_tools/handler.py` | Gateway tool backend with backend authorization |
| `src/controls_assistant/` | Week 1 tool loop, RAG module, test client, config |
| `scripts/` | Setup, teardown, model comparison, trace summary |
| `data/corpus/`, `data/synthetic/` | Synthetic documents and records |
| `evaluation/` | Frozen scenarios and eval runner |
| `evidence/` | Evidence per deliverable |
| `notebooks/` | Demo notebooks |
| `docs/` | Architecture, runbook, costs, backlog, review notes |

## Account notes

Profile `vr-training` = VR Labs account `899456967600`, Region `us-east-1`.
A VR org SCP blocks many models, including all `global.*` inference profiles. Use `us.*` IDs. See `.env.example`.
Sonnet 5 does not accept `temperature`.
