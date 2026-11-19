# M1-D01 review notes (10 minutes)

## Fixed workflow vs retrieval assistant vs agent

Journey: "Does control X meet policy, and if not, what is the gap?"

| Option | How it works | Good | Bad |
|---|---|---|---|
| Fixed workflow | Code always does: look up policy -> look up status -> ask model to write the gap | Predictable, easy to test, cheapest | Breaks when the question does not fit the fixed steps |
| Retrieval assistant | Retrieve policy passages, model answers with citations, no tools | Good for "what does the policy say" | Cannot see live status, so it cannot explain the gap |
| Agent | Model picks which tools to call and in what order, inside limits | Handles varied questions, combines policy and status | Less predictable, more tokens, needs limits and tests |

My choice: an agent with tight limits (2 read-only tools, max tool calls, timeouts), because the combined journey needs both the policy and the live status.
The steps are simple enough that a fixed workflow would also work. The agent is chosen because the module asks for it and because users will ask varied questions.

## Walkthrough

1. **One API request:** `uv run python -m controls_assistant.cli --verbose "What is the status of CTL-003?"`
   Show `agent_loop.ask()`: system prompt, messages, toolConfig, `converse()`, usage tokens.
2. **One tool call:** the response has `stopReason: tool_use`. Code checks the tool name and args in `tools.py`, runs it, and sends back a `toolResult`. The model then writes the answer.
3. **One error:** `uv run python -m controls_assistant.cli --verbose "Is CTL-999 effective?"`
   The tool raises `ToolError`, the loop sends `status: error`, and the model says the control was not found.

## Model proposes, code executes

- The model only returns JSON that asks for a tool.
- `tools.run_tool()` decides: unknown tool -> error, bad args -> error, missing record -> error.
- Limits live in code: `MAX_TOOL_CALLS = 3`, `TOOL_TIMEOUT_SECONDS = 5`.
- IAM: the caller needs `bedrock:InvokeModel` on the inference profile and on the underlying foundation models in each Region it can route to.

## Live change ideas

- Change the tool description to remove "Control IDs look like CTL-001", then ask "status of control 3". Watch the model send a bad ID and get a validation error.
- Set `MAX_TOOL_CALLS = 1` and ask the P4 comparison. Watch the second call get refused.
- Remove "Do not guess a status" from the system prompt and run with `--no-tools`.
