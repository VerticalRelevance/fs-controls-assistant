# Learning log

## 2026-11-19

- Set up the workshop repo (commit 0d7c6fb) and this project.
- Got access: VR SSO, Labs account 899456967600, profile `vr-training`, us-east-1.
- `check_access.py` passed for Sonnet 5 and Nova 2 Lite.
- Found that a VR SCP blocks many models, including all `global.*` profiles. Tested which ones work.
- Sonnet 5 rejects the `temperature` parameter. Removed it from the access check.
- Workshop notebook used `global.anthropic.*` IDs. Changed them to `us.anthropic.*` locally.
- Checked list access to Bedrock KB, Guardrails, OpenSearch Serverless, S3 Vectors, AgentCore, Cognito, DynamoDB, IAM. All OK.
- CDK is already bootstrapped in us-east-1.
- Day 1: ran the workshop notebook `01_Inference_APIs`. 11 of 13 code cells passed.
  The GPT (OpenAI) and Stability image cells fail because the VR SCP blocks those models.
  Kimi is also blocked, so I used Nova 2 Lite for the service tier cell (flex worked).
  Claude Sonnet 4.6 and Haiku 4.5 do not support flex or priority tiers in this account.
- Day 3 lab: ran `02_Knowledge_Bases_and_RAG` notebooks 1-4 (2026-11-19, about 15:48-16:05 UTC).
  Created an S3 bucket, OpenSearch Serverless collection, IAM role, and KB `GLEZTALS0E` with Titan Embed v2.
  Ingested 4 public Amazon shareholder letters, 0 failed. Chunking was fixed size, 512 tokens, 20% overlap.
  RetrieveAndGenerate with Haiku 4.5 returned an answer with citations.
  Retrieve + Converse (custom prompt) also worked.
  Tagged all resources (owner, project, purpose), then ran clean-up.
  Checked with the CLI that KB, collection, policies, bucket, IAM role, and IAM policies are all gone.
  The collection took about 5 minutes to finish deleting.
- M1-D01: built a Converse tool-use loop with a mock get_control_status tool.
  Compared Sonnet 5 and Nova 2 Lite on 5 prompts x 3 runs. Nova: 15/15, 1.3 s median, $0.0008 per request.
  Sonnet: 12/15 by the automatic check, but the 3 misses were safe (read status, then refused to change it). 3.2 s, $0.005.
  Chose Nova 2 Lite as default for now; will recheck on the 30 scenarios.
  Lesson: write checks for behavior that matters (did it refuse?), not for one exact path (no tool call).

## 2026-11-22

- Built D02-D05 in one push: KB on S3 Vectors, Guardrail, AgentCore agent with Gateway tools, Cognito, Memory, eval runner.
- S3 Vectors scores: relevant ~0.85+, unrelated ~0.60. Used 0.65 as the abstain cut-off.
- Guardrail prompt-attack check on each retrieved passage drops the poisoned vendor FAQ. Cost: the harmless part of that doc is lost too.
- The AgentCore CLI passes no user identity to tools by default. Allowed the Authorization header, passed the user's token to Gateway, and validated it again in Lambda.
- Baseline 26/26/25. Most failures were citation format. Added cite_as to passages: final 27/27/28.
- Lesson: phrase-based checks give false failures (the word "bullet" as an example). Check against the stored data, not words.
- Lesson: the model can present a system rule ("keep answers short") as a remembered preference. Needs an explicit rule.
- Long-term preference extraction took about 60 s.
