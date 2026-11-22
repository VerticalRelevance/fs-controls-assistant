# Cost worksheet

Prices: AWS Pricing API, us-east-1, on-demand, checked 2026-11-22. These are training estimates, not quotes.

## Unit prices used

| Item | Price |
|---|---|
| Nova 2 Lite (agent model) | $0.33 / 1M input tokens, $2.75 / 1M output tokens |
| Claude Sonnet 5 (judge, fallback model) | $2.20 / 1M input, $11.00 / 1M output |
| Titan Embed Text v2 | $0.02 / 1M tokens |
| Guardrail content / topic policy | $0.15 / 1K text units |
| Guardrail PII (sensitive info) | $0.10 / 1K text units |
| Guardrail prompt-attack check | $0.08 / 1K text units |
| AgentCore Runtime | $0.0895 / vCPU-hour + $0.00945 / GB-hour, billed only while a request is active |
| AgentCore Gateway | $0.005 / 1K tool invocations |
| AgentCore Memory long-term | $0.75 / 1K records stored per month, $0.50 / 1K records retrieved |
| AgentCore Memory short-term | events free; $1.00 / GB ingest, $0.20 / GB read |
| Lambda, DynamoDB on-demand, Cognito (under 10K MAU), S3, S3 Vectors | pennies at this volume |

## Observed usage per request

From the evaluation runs (`evidence/m1-d04/*.json`, see `summary`):

- About 3,000 input and 150 output agent tokens per request. Nova cost is about **$0.0014 per request**.
- 1-2 Guardrail input/output checks plus 1 prompt-attack check per retrieved passage (up to 6).
- 0-3 Gateway tool calls.
- About 4-10 s Runtime active time per request.

Rough total per successful request (model + guardrail + runtime + memory): **about $0.003-0.006**.

## Evaluation cost

One full run is 30 scenarios (some multi-turn), plus about 9 Sonnet 5 judge calls.
Six runs (baseline + final) cost about **$0.30-0.60** in total, mostly from guardrail checks and the judge.

## Idle cost when left running

| Resource | Idle cost |
|---|---|
| AgentCore Runtime, Gateway, Memory | ~$0 (consumption based) |
| S3 Vectors index + docs bucket | < $0.01 / month |
| DynamoDB on-demand, Lambda, Cognito | ~$0 |
| CloudWatch logs and spans | small, grows with traffic |

No hourly-billed resources are used. OpenSearch Serverless was avoided for this reason (it costs ~$0.50-1.00/hour idle).
Still, run `scripts/teardown.py --yes` at the end. Budget alerts do not stop charges.
