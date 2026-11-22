# Attribution and AI disclosure

## Workshop code used

| File in this repo | Source | Commit | Changes made |
|---|---|---|---|
| None. Workshop notebooks were run in the separate workshop clone, not copied here. | aws-samples/amazon-bedrock-workshop | 0d7c6fb | |
| `ControlsAssistant/` scaffold (CDK app, memory session module, project layout) | `agentcore create` from @aws/agentcore 0.30.0 | CLI 0.30.0 | Agent code rewritten. Removed example MCP client, model loader, skills. Memory module reduced to one preference namespace. |

## AI assistance

| Date | Tool | What it helped with | Reviewed by me |
|---|---|---|---|
| 2026-11-19 | Claude Code | Project skeleton, `scripts/check_access.py`, account and model access checks | Yes |
| 2026-11-19 | Claude Code | M1-D01: tool loop, mock tool, tests, comparison script, evidence and docs drafts | Review in progress |
| 2026-11-22 | Claude Code | M1-D02 to D05: corpus, setup and teardown scripts, agent code, Lambda, eval runner, scenarios, notebooks, docs drafts | Review in progress |
