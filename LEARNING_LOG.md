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
