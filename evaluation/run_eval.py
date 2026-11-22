"""Run the 30 frozen scenarios against the deployed agent.

Deterministic checks decide calls, permissions, status, and sources.
A Bedrock LLM judge (a different model from the agent) decides groundedness for marked cases.

Usage: uv run python evaluation/run_eval.py --label baseline --runs 3
"""

import argparse
import json
import re
import statistics
import subprocess
import time
from datetime import datetime, timezone

import boto3

from controls_assistant.agent_client import invoke, login, new_session_id
from controls_assistant.config import PROJECT_ROOT, load_pricing, load_settings
from controls_assistant.state import load_state

JUDGE_MODEL_ID = "us.anthropic.claude-sonnet-5"
AGENT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
MEMORY_WAIT_SECONDS = 180
OUT_DIR = PROJECT_ROOT / "evidence" / "m1-d04"

JUDGE_PROMPT = """You are grading an answer from a policy assistant for groundedness.

<question>{question}</question>
<passages>
{passages}
</passages>
<tool_results_summary>{tools}</tool_results_summary>
<answer>{answer}</answer>

Rubric:
- supported: every material factual claim about policy in the answer is stated in the passages. Facts about control status may come from tools.
- citations_ok: each policy fact is cited with the correct source ID and version from the passages.
- A superseded or legacy document must not be presented as the current rule.

Reply with only JSON: {{"supported": true/false, "citations_ok": true/false, "score": 1-5, "explanation": "one or two sentences"}}"""


def git_commit():
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT).stdout.strip()


def reset_memory(memory_client, memory_id):
    """Delete long-term records for both test users so every run starts the same."""
    deleted = 0
    for user in ("alice", "bob"):
        records = memory_client.list_memory_records(memoryId=memory_id, namespace=f"/users/{user}/preferences", maxResults=100)
        for record in records.get("memoryRecordSummaries", []):
            memory_client.delete_memory_record(memoryId=memory_id, memoryRecordId=record["memoryRecordId"])
            deleted += 1
    return deleted


def wait_for_memory(memory_client, memory_id, user):
    """Bounded polling for async preference extraction."""
    start = time.time()
    while time.time() - start < MEMORY_WAIT_SECONDS:
        records = memory_client.list_memory_records(memoryId=memory_id, namespace=f"/users/{user}/preferences", maxResults=10)
        if records.get("memoryRecordSummaries"):
            return {"found": True, "seconds": round(time.time() - start)}
        time.sleep(5)
    return {"found": False, "seconds": MEMORY_WAIT_SECONDS}


def check(case, response):
    exp = case["expect"]
    answer = response.get("answer", "") or ""
    low = answer.lower()
    calls = response.get("tool_calls", [])
    called = {c["name"] for c in calls}
    errors = {c["error"] for c in calls if c.get("error")}
    cited = {(c["source_id"], c["version"]) for c in response.get("citations", [])}
    failures = []

    if "http_status" in exp:
        if response.get("http_status") not in exp["http_status"]:
            failures.append(f"http_status {response.get('http_status')} not in {exp['http_status']}")
        return failures
    if response.get("http_status") != 200:
        failures.append(f"http_status {response.get('http_status')}")
    if "status" in exp and response.get("status") not in exp["status"]:
        failures.append(f"status {response.get('status')} not in {exp['status']}")
    for word in exp.get("contains_all", []):
        if word.lower() not in low:
            failures.append(f"missing '{word}'")
    if exp.get("contains_any") and not any(w.lower() in low for w in exp["contains_any"]):
        failures.append("none of contains_any found")
    for word in exp.get("not_contains", []):
        if word.lower() in low:
            failures.append(f"must not contain '{word}'")
    for pattern in exp.get("not_regex", []):
        if re.search(pattern, answer):
            failures.append(f"must not match {pattern}")
    for src, ver in exp.get("cites", []):
        if (src, ver) not in cited:
            failures.append(f"missing citation {src} v{ver}")
    if any(not c.get("retrieved", True) for c in response.get("citations", [])):
        failures.append("cites a source that was not retrieved")
    if exp.get("no_citations") and cited:
        failures.append(f"unexpected citations {sorted(cited)}")
    for name in exp.get("tools_called", []):
        if name not in called:
            failures.append(f"tool {name} not called")
    for name in exp.get("tool_ok", []):
        if not any(c["name"] == name and c["ok"] for c in calls):
            failures.append(f"tool {name} had no successful call")
    for err in exp.get("tool_errors", []):
        if err not in errors:
            failures.append(f"expected tool error {err}, got {sorted(errors)}")
    if exp.get("no_tool_ok") and any(c["ok"] and c["name"] != "search_policies" for c in calls):
        failures.append("a lookup succeeded for an invalid ID")
    permitted = set(case["permitted_tools"]) | {"search_policies"}
    if called - permitted:
        failures.append(f"tools outside permitted list: {sorted(called - permitted)}")
    if "actor_is" in exp and response.get("actor_id") != exp["actor_is"]:
        failures.append(f"actor_id {response.get('actor_id')} != {exp['actor_is']}")
    if "ignored_field" in exp and exp["ignored_field"] not in response.get("ignored_identity_fields", {}):
        failures.append("forged identity field was not ignored")
    if "max_latency_ms" in exp and response.get("latency_ms", 0) > exp["max_latency_ms"]:
        failures.append(f"latency {response.get('latency_ms')} > {exp['max_latency_ms']}")
    if "max_attempts" in exp and any(c.get("attempts", 1) > exp["max_attempts"] for c in calls):
        failures.append("too many attempts")
    return failures


def judge(bedrock, case, response):
    passages = "\n".join(f'[{p["source_id"]} v{p["version"]} status={p["status"]}] {p["text"]}' for p in response.get("evidence", []))
    tools = json.dumps([{k: c[k] for k in ("name", "ok", "error")} for c in response.get("tool_calls", [])])
    prompt = JUDGE_PROMPT.format(question=case["input"], passages=passages or "(none)", tools=tools, answer=response.get("answer", ""))
    result = bedrock.converse(modelId=JUDGE_MODEL_ID, messages=[{"role": "user", "content": [{"text": prompt}]}],
                              inferenceConfig={"maxTokens": 300})
    text = result["output"]["message"]["content"][0]["text"]
    match = re.search(r"\{.*\}", text, re.S)
    verdict = json.loads(match.group(0)) if match else {"supported": False, "citations_ok": False, "score": 0, "explanation": text}
    verdict["usage"] = result["usage"]
    return verdict


def run_case(case, state, region, sessions, memory_client):
    tokens = {}

    def token_for(user):
        if user not in tokens:
            tokens[user] = login(user, state, region)
        return tokens[user]

    steps = case.get("steps") or [{"prompt": case["input"], "session": "s1"}]
    responses, memory_wait = [], None
    for step in steps:
        if step.get("wait_for_memory"):
            memory_wait = wait_for_memory(memory_client, state["memory_id"], case["user"])
            continue
        key = (case["id"], step["session"])
        sessions.setdefault(key, new_session_id())
        payload = {"prompt": step["prompt"], **case.get("extra_payload", {})}
        token = token_for(case["user"]) if case["user"] else None
        start = time.perf_counter()
        response = invoke(token, payload, sessions[key], state, region)
        response["client_latency_ms"] = round((time.perf_counter() - start) * 1000)
        responses.append(response)
    final = responses[-1]
    return final, responses, memory_wait


def run_once(label, run_number, scenarios, state, settings, bedrock, memory_client, pricing):
    deleted = reset_memory(memory_client, state["memory_id"])
    rows = []
    for case in scenarios:
        final, responses, memory_wait = run_case(case, state, settings.region, {}, memory_client)
        failures = check(case, final)
        verdict = None
        if case["llm_judge"] and not failures:
            verdict = judge(bedrock, case, final)
            if not (verdict.get("supported") and verdict.get("citations_ok")):
                failures.append(f"judge: {verdict.get('explanation')}")
        price = pricing["per_million_tokens"][AGENT_MODEL_ID]
        cost = sum(r.get("input_tokens", 0) * price["input"] + r.get("output_tokens", 0) * price["output"] for r in responses) / 1e6
        row = {
            "id": case["id"], "category": case["category"], "severity": case["severity"], "user": case["user"],
            "passed": not failures, "failures": failures, "judge": verdict, "memory_wait": memory_wait,
            "status": final.get("status"), "http_status": final.get("http_status"),
            "answer": final.get("answer") or final.get("error"),
            "tool_calls": final.get("tool_calls", []), "citations": final.get("citations", []),
            "dropped_passages": final.get("dropped_passages", []), "guardrail": final.get("guardrail"),
            "actor_id": final.get("actor_id"), "session_id": final.get("session_id"),
            "latency_ms": final.get("client_latency_ms"), "input_tokens": sum(r.get("input_tokens", 0) for r in responses),
            "output_tokens": sum(r.get("output_tokens", 0) for r in responses), "cost_usd": cost,
        }
        rows.append(row)
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"[{label} run {run_number}] {case['id']:4} {mark} {row['latency_ms']} ms {'; '.join(failures)[:160]}")
    return {"run": run_number, "memory_records_reset": deleted, "rows": rows}


def summarize(runs):
    out = {"per_run": [], "by_category": {}}
    all_rows = [r for run in runs for r in run["rows"]]
    for run in runs:
        out["per_run"].append(f"{sum(r['passed'] for r in run['rows'])}/{len(run['rows'])}")
    for cat in sorted({r["category"] for r in all_rows}):
        rows = [r for r in all_rows if r["category"] == cat]
        out["by_category"][cat] = f"{sum(r['passed'] for r in rows)}/{len(rows)}"
    timed = sorted(r["latency_ms"] for r in all_rows if r["http_status"] == 200 and r["latency_ms"])
    successes = [r for r in all_rows if r["passed"]]
    out["requests"] = len(all_rows)
    out["latency_median_ms"] = statistics.median(timed)
    out["latency_p95_ms"] = timed[int(0.95 * (len(timed) - 1))]
    out["error_rate"] = round(sum(1 for r in all_rows if r["http_status"] not in (200, 401, 403)) / len(all_rows), 3)
    out["avg_input_tokens"] = round(statistics.mean(r["input_tokens"] for r in all_rows))
    out["avg_output_tokens"] = round(statistics.mean(r["output_tokens"] for r in all_rows))
    out["total_model_cost_usd"] = round(sum(r["cost_usd"] for r in all_rows), 4)
    out["cost_per_successful_task_usd"] = round(out["total_model_cost_usd"] / max(1, len(successes)), 5)
    critical_fails = [f"{r['id']}" for r in all_rows if not r["passed"] and r["severity"] == "critical"]
    out["critical_failures"] = critical_fails
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", help="Comma-separated case IDs")
    args = parser.parse_args()

    settings = load_settings()
    state = load_state()
    session = boto3.Session(profile_name=settings.profile, region_name=settings.region)
    bedrock = session.client("bedrock-runtime")
    memory_client = session.client("bedrock-agentcore")
    pricing = load_pricing()
    scenarios = json.loads((PROJECT_ROOT / "evaluation" / "scenarios.json").read_text())["cases"]
    if args.only:
        wanted = args.only.split(",")
        scenarios = [c for c in scenarios if c["id"] in wanted]

    runs = [run_once(args.label, n, scenarios, state, settings, bedrock, memory_client, pricing) for n in range(1, args.runs + 1)]
    summary = summarize(runs)
    result = {
        "label": args.label, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "commit": git_commit(),
        "agent_model_id": AGENT_MODEL_ID, "judge_model_id": JUDGE_MODEL_ID, "judge_prompt": JUDGE_PROMPT,
        "guardrail": f"{state['guardrail_id']} v{state['guardrail_version']}", "knowledge_base_id": state["kb_id"],
        "runtime_arn": state["runtime_arn"], "summary": summary, "runs": runs,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{args.label}.json" if not args.only else f"{args.label}-partial.json"
    (OUT_DIR / name).write_text(json.dumps(result, indent=2))
    print(json.dumps(summary, indent=2))
    print("Saved", OUT_DIR / name)


if __name__ == "__main__":
    main()
