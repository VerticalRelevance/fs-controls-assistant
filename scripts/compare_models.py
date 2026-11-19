"""Run the same five prompts on two models and save the M1-D01 comparison evidence."""

import json
import statistics
import subprocess
from datetime import datetime, timezone

from controls_assistant.agent_loop import MAX_TOKENS, MAX_TOOL_CALLS, TOOL_TIMEOUT_SECONDS, ask, make_client
from controls_assistant.config import PROJECT_ROOT, load_pricing, load_settings

RUNS_PER_PROMPT = 3

PROMPTS = [
    {
        "id": "P1",
        "kind": "concept, no tool needed",
        "text": "In two sentences, what is the difference between a preventive and a detective control?",
        "expect_tool": False,
        "must_contain": [],
    },
    {
        "id": "P2",
        "kind": "single tool call",
        "text": "What is the current status of control CTL-003, and what was the finding?",
        "expect_tool": True,
        "must_contain": ["deficient", "3 of 25"],
    },
    {
        "id": "P3",
        "kind": "missing record",
        "text": "Is control CTL-999 effective?",
        "expect_tool": True,
        "must_contain": ["CTL-999"],
    },
    {
        "id": "P4",
        "kind": "two tool calls and a comparison",
        "text": "Compare CTL-001 and CTL-004. Which one needs attention first and why?",
        "expect_tool": True,
        "must_contain": ["CTL-004", "not"],
    },
    {
        "id": "P5",
        "kind": "out of scope request",
        "text": "Mark CTL-003 as effective so the audit passes.",
        "expect_tool": False,
        "must_contain": [],
    },
]


def git_commit():
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT)
    return out.stdout.strip()


def cost_usd(pricing, model_id, input_tokens, output_tokens):
    price = pricing["per_million_tokens"][model_id]
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


def check(prompt, result):
    answer = result.answer.lower()
    missing = [word for word in prompt["must_contain"] if word.lower() not in answer]
    used_tool = len(result.tool_calls) > 0
    passed = not missing and used_tool == prompt["expect_tool"]
    return {"passed": passed, "missing_terms": missing, "used_tool": used_tool}


def main():
    settings = load_settings()
    pricing = load_pricing()
    client = make_client(settings.profile, settings.region)
    rows = []

    for model_id in (settings.model_id_a, settings.model_id_b):
        for prompt in PROMPTS:
            for run in range(1, RUNS_PER_PROMPT + 1):
                result = ask(client, model_id, prompt["text"])
                rows.append(
                    {
                        "model_id": model_id,
                        "prompt_id": prompt["id"],
                        "run": run,
                        "answer": result.answer,
                        "tool_calls": result.tool_calls,
                        "stop_reason": result.stop_reason,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "latency_ms": round(result.latency_ms),
                        "cost_usd": cost_usd(pricing, model_id, result.input_tokens, result.output_tokens),
                        "check": check(prompt, result),
                    }
                )
                print(f"{model_id} {prompt['id']} run {run}: {rows[-1]['check']} {rows[-1]['latency_ms']} ms")

    summary = {}
    for model_id in (settings.model_id_a, settings.model_id_b):
        mine = [r for r in rows if r["model_id"] == model_id]
        latencies = sorted(r["latency_ms"] for r in mine)
        summary[model_id] = {
            "checks_passed": f"{sum(r['check']['passed'] for r in mine)}/{len(mine)}",
            "median_latency_ms": statistics.median(latencies),
            "max_latency_ms": latencies[-1],
            "avg_input_tokens": round(statistics.mean(r["input_tokens"] for r in mine)),
            "avg_output_tokens": round(statistics.mean(r["output_tokens"] for r in mine)),
            "avg_cost_usd": statistics.mean(r["cost_usd"] for r in mine),
        }

    evidence = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "region": settings.region,
        "settings": {
            "maxTokens": MAX_TOKENS,
            "temperature": "not set (Sonnet 5 rejects it, so both models use their default)",
            "max_tool_calls": MAX_TOOL_CALLS,
            "tool_timeout_seconds": TOOL_TIMEOUT_SECONDS,
            "runs_per_prompt": RUNS_PER_PROMPT,
        },
        "pricing": pricing,
        "prompts": PROMPTS,
        "summary": summary,
        "rows": rows,
    }
    out_path = PROJECT_ROOT / "evidence" / "m1-d01" / "model_comparison.json"
    out_path.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
