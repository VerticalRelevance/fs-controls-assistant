# Backlog

## M1-D02 (Days 3-5)
- [ ] Write 10-15 synthetic policy/control docs with source ID, title, version date. Include 2 conflicting or obsolete statements and 1 doc with a prompt injection.
- [ ] Create KB (S3 Vectors store, Titan Embed v2) with a script, plus a teardown script.
- [ ] Retrieval code that returns source IDs and versions, and an explicit "insufficient evidence" answer.
- [ ] Guardrail: denied topic, synthetic PII filter, prompt attack filter. Version it. Wire it to input and output.
- [ ] Freeze the 30 scenarios (JSON) before tuning. Baseline the retrieval and safety cases.
- [ ] Run the scenarios on both models to confirm the default model choice.

## M1-D03 (Days 6-7)
- [ ] AgentCore workshop Labs 1-3 with CLI 0.30.0.
- [ ] Strands agent on AgentCore Runtime, reusing the retrieval code.
- [ ] Two Lambda tools behind Gateway: get_control_status, get_evidence_status. DynamoDB records with owners.
- [ ] Two Cognito test users. Backend checks scope from the verified token.
- [ ] Long-term memory preference strategy. Same-session, cross-session, and two-user isolation tests.

## M1-D04 / D05 (Days 8-10)
- [ ] AgentCore workshop Labs 4-5.
- [ ] Observability: trace one retrieval + tool request and one injected tool timeout.
- [ ] Eval runner: 30 scenarios x 3 runs, before and after one improvement. LLM judge + deterministic checks.
- [ ] Human-label 10 cases.
- [ ] Retries, timeouts, structured errors, health check.
- [ ] Cost worksheet, runbook, README sections (ingest, invoke, update, rollback, teardown).
- [ ] Full teardown and check.

## Open questions for the mentor
- Is S3 Vectors fine as the KB store, or is OpenSearch Serverless required?
- What is the "validated caller-context pattern" for backend authorization?
- Two test identities: should I create my own Cognito users?
- Cohort budget and tagging rule.
