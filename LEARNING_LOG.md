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
