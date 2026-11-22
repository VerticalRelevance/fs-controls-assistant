# Backlog

## Done
- M1-D01: model comparison, tool loop, architecture, backlog
- M1-D02: corpus, KB on S3 Vectors, Guardrail v1, retrieval with citations and abstention
- M1-D03: AgentCore Runtime, Gateway with 2 Lambda tools, Cognito users, Memory
- M1-D04: 30 frozen scenarios, baseline and final runs, traces, human review sheet
- M1-D05: README, runbook, cost worksheet, teardown script

## Open
- [ ] Human review: fill in `evidence/m1-d04/human-review-final.md` (me, not AI)
- [ ] Memory honesty: only claim a remembered preference if it is in retrieved memory. Move "keep answers short" out of user-facing wording.
- [ ] Judge: raise `maxTokens` from 300 to 600 so verdicts are never cut off (G09 run 2).
- [ ] Scenario checks for the next frozen set: accept "3 out of 25", wider abstain phrases, check memory disclosure by the stored preference text instead of the word "bullet".
- [ ] Do not pass the user token as a tool argument. Use a Gateway interceptor or a signed internal token so it never appears in tool logs.
- [ ] Ask the agent to call search_policies before abstaining (G08 abstained without searching).
- [ ] Final teardown after the review: `uv run python scripts/teardown.py --yes`

## Open questions for the mentor
- Is S3 Vectors fine as the approved KB store?
- Is passing the Cognito access token to the backend and validating it there acceptable as the "validated caller-context pattern"?
- Should I keep the deployment running until the final review?
