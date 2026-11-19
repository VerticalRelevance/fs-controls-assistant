import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field

import boto3
from botocore.config import Config

from controls_assistant.tools import TOOL_CONFIG, ToolError, run_tool

MAX_TOOL_CALLS = 3
TOOL_TIMEOUT_SECONDS = 5
MAX_TOKENS = 800

SYSTEM_PROMPT = """You are the Controls Assistant for a fictional financial-services platform team.
Answer questions about internal controls.
For the status of a specific control, call get_control_status. Do not guess a status.
If a tool returns an error, say what failed and that the answer is incomplete.
Keep answers short and factual."""


@dataclass
class LoopResult:
    answer: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    tool_calls: list = field(default_factory=list)
    stop_reason: str = ""


def make_client(profile, region):
    session = boto3.Session(profile_name=profile, region_name=region)
    config = Config(connect_timeout=10, read_timeout=60, retries={"max_attempts": 3, "mode": "standard"})
    return session.client("bedrock-runtime", config=config)


def call_tool_with_timeout(name, args):
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_tool, name, args)
        try:
            return {"json": future.result(timeout=TOOL_TIMEOUT_SECONDS)}, "success"
        except FutureTimeout:
            return {"text": f"Tool {name} timed out after {TOOL_TIMEOUT_SECONDS}s."}, "error"
        except ToolError as error:
            return {"text": str(error)}, "error"


def ask(client, model_id, question, use_tools=True, system_prompt=SYSTEM_PROMPT):
    messages = [{"role": "user", "content": [{"text": question}]}]
    result = LoopResult(answer="", model_id=model_id)
    start = time.perf_counter()

    while True:
        request = {
            "modelId": model_id,
            "system": [{"text": system_prompt}],
            "messages": messages,
            "inferenceConfig": {"maxTokens": MAX_TOKENS},
        }
        if use_tools:
            request["toolConfig"] = TOOL_CONFIG
        response = client.converse(**request)

        result.input_tokens += response["usage"]["inputTokens"]
        result.output_tokens += response["usage"]["outputTokens"]
        result.stop_reason = response["stopReason"]
        message = response["output"]["message"]
        messages.append(message)

        if response["stopReason"] != "tool_use":
            result.answer = "".join(block.get("text", "") for block in message["content"]).strip()
            break

        tool_results = []
        for block in message["content"]:
            if "toolUse" not in block:
                continue
            tool_use = block["toolUse"]
            if len(result.tool_calls) >= MAX_TOOL_CALLS:
                content, status = {"text": "Tool-call limit reached. Answer with what you have."}, "error"
            else:
                content, status = call_tool_with_timeout(tool_use["name"], tool_use["input"])
            result.tool_calls.append({"name": tool_use["name"], "input": tool_use["input"], "status": status})
            tool_results.append(
                {"toolResult": {"toolUseId": tool_use["toolUseId"], "content": [content], "status": status}}
            )
        messages.append({"role": "user", "content": tool_results})

        if len(result.tool_calls) > MAX_TOOL_CALLS:
            result.answer = "Stopped: the model kept asking for tools past the limit. The answer is incomplete."
            break

    result.latency_ms = (time.perf_counter() - start) * 1000
    return result
