"""Print a short span tree for a trace downloaded with `agentcore traces get`.

Usage: uv run python scripts/trace_summary.py <trace.json> [--out evidence/m1-d04/trace-x.md]
Only span names, timings, status, and a few safe attributes are kept. No prompts, answers, or tokens.
"""

import argparse
import json

SAFE_ATTRIBUTES = ("gen_ai.request.model", "gen_ai.tool.name", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
                   "rpc.method", "http.status_code", "session.id", "error.type")


def load_spans(path):
    rows = json.load(open(path))
    spans = []
    for row in rows:
        m = row["@message"] if isinstance(row.get("@message"), dict) else row
        attrs = m.get("attributes", {})
        spans.append({
            "id": m["spanId"], "parent": m.get("parentSpanId"), "name": m["name"],
            "start": int(m["startTimeUnixNano"]), "end": int(m["endTimeUnixNano"]),
            "status": m.get("status", {}).get("code", "UNSET"),
            "attrs": {k: attrs[k] for k in SAFE_ATTRIBUTES if k in attrs},
        })
    return spans


def render(spans):
    by_parent = {}
    ids = {s["id"] for s in spans}
    for s in spans:
        parent = s["parent"] if s["parent"] in ids else None
        by_parent.setdefault(parent, []).append(s)
    t0 = min(s["start"] for s in spans)
    lines = []

    def walk(parent, depth):
        for s in sorted(by_parent.get(parent, []), key=lambda x: x["start"]):
            ms = (s["end"] - s["start"]) / 1e6
            offset = (s["start"] - t0) / 1e6
            flag = "  ERROR" if s["status"] == "ERROR" else ""
            extra = f"  {s['attrs']}" if s["attrs"] else ""
            lines.append(f"{'  ' * depth}- {s['name']}  +{offset:.0f} ms, {ms:.0f} ms{flag}{extra}")
            walk(s["id"], depth + 1)

    walk(None, 0)
    total = (max(s["end"] for s in spans) - t0) / 1e6
    return f"Spans: {len(spans)}, total {total:.0f} ms\n\n" + "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace")
    parser.add_argument("--out")
    args = parser.parse_args()
    text = render(load_spans(args.trace))
    print(text)
    if args.out:
        open(args.out, "w").write(text + "\n")


if __name__ == "__main__":
    main()
