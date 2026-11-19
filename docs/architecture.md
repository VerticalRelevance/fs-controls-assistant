# Architecture

## Now (M1-D01)

```
CLI (controls_assistant.cli)
  -> agent_loop.ask()          our own loop, max 3 tool calls
     -> Bedrock Converse        model proposes a tool call
     -> tools.run_tool()        our code validates args and runs it (5 s timeout)
        -> data/synthetic/control_records.json
```

The model never runs anything. It only returns a `toolUse` block with a name and arguments.
Our code checks the tool name against an allow list, checks the arguments, runs the tool, and sends the result back.
Bad arguments, unknown tools, missing records, and timeouts come back to the model as `status: error`, and the model is told to say the answer is incomplete.

## Target (M1-D05)

```
CLI test client (Cognito user A or B, gets a JWT)
  -> AgentCore Runtime (one Python Strands agent, inbound JWT auth)
       - Bedrock Converse (default model from config)
       - Bedrock Guardrail on input and output
       - Bedrock Knowledge Base retrieve (synthetic policy docs in S3, S3 Vectors store)
       - AgentCore Memory (long-term user preferences, actor ID = verified user ID)
       -> AgentCore Gateway (MCP, inbound JWT auth)
            -> Lambda get_control_status   (read-only, checks caller scope)
            -> Lambda get_evidence_status  (read-only, checks caller scope)
                 -> DynamoDB synthetic records
  -> CloudWatch / AgentCore Observability traces
```

## Where each permission is enforced (planned)

| Question | Enforced by |
|---|---|
| Is the caller a real user? | Cognito JWT, checked by AgentCore Runtime inbound auth |
| Which user is this? | Verified `sub` claim from the token, never from prompt text |
| Can the agent call this tool? | Gateway tool list + our tool allow list |
| Can this user see this record? | Lambda backend checks the verified user's scope against the record owner |
| Can the agent read models, KB, memory? | Runtime execution role (IAM), least privilege |
| Whose memories are read? | Actor ID set from the verified user ID in code |
| Is the content safe? | Bedrock Guardrail on input and output |

## Stores

| Store | Holds | Not for |
|---|---|---|
| S3 + Knowledge Base | Policy and control documents (versioned) | Live status, user data |
| DynamoDB (via Lambda tools) | Authoritative control and evidence status | Policy text |
| AgentCore Memory | Harmless user preferences (for example answer format) | Facts about controls, anything authoritative |
