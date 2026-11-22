"""Make a human review sheet (markdown) for at least 10 cases from a results file.

Usage: uv run python evaluation/make_review_sheet.py final
Picks every failed case from run 1, then grounding and judged cases, up to 12.
Fill in the "Human decision" and "Notes" lines by hand.
"""

import json
import sys

from controls_assistant.config import PROJECT_ROOT

LIMIT = 12


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "final"
    data = json.loads((PROJECT_ROOT / "evidence" / "m1-d04" / f"{label}.json").read_text())
    scenarios = {c["id"]: c for c in json.loads((PROJECT_ROOT / "evaluation" / "scenarios.json").read_text())["cases"]}
    rows = data["runs"][0]["rows"]

    picked = [r for r in rows if not r["passed"]]
    picked += [r for r in rows if r["judge"] and r not in picked]
    picked += [r for r in rows if r["category"] in ("grounding", "memory", "safety") and r not in picked]
    picked = picked[:LIMIT]

    lines = [
        f"# Human review: {label} run 1",
        "",
        f"Commit `{data['commit']}`, agent `{data['agent_model_id']}`, judge `{data['judge_model_id']}`.",
        "For each case: read the answer, decide pass or fail yourself, and note if you disagree with the automatic result.",
        "Deterministic checks and this human review decide critical security failures.",
        "",
    ]
    for r in picked:
        case = scenarios[r["id"]]
        judge = r["judge"] or {}
        lines += [
            f"## {r['id']} ({r['category']}, {r['severity']})",
            "",
            f"**Input** ({r['user']}): {case['input'] or ' / '.join(s.get('prompt', '[wait for memory]') for s in case.get('steps', []))}",
            "",
            f"**Expected**: `{json.dumps(case['expect'])}`" + (f"  \nNote: {case['note']}" if case.get("note") else ""),
            "",
            "**Answer**:",
            "",
            "> " + (r["answer"] or "").replace("\n", "\n> "),
            "",
            f"**Tools**: {[(c['name'], c.get('error')) for c in r['tool_calls']]}  ",
            f"**Citations**: {[(c['source_id'], c['version']) for c in r['citations']]}  ",
            f"**Automatic result**: {'PASS' if r['passed'] else 'FAIL'} {('- ' + '; '.join(r['failures'])) if r['failures'] else ''}  ",
            f"**Judge**: {('supported=' + str(judge.get('supported')) + ', citations_ok=' + str(judge.get('citations_ok')) + ', score=' + str(judge.get('score')) + ' - ' + str(judge.get('explanation'))) if judge else 'not judged'}",
            "",
            "**Human decision**: PASS / FAIL  ",
            "**Agree with automatic result?** yes / no  ",
            "**Notes**: ",
            "",
        ]
    out = PROJECT_ROOT / "evidence" / "m1-d04" / f"human-review-{label}.md"
    out.write_text("\n".join(lines))
    print("Wrote", out, "with", len(picked), "cases")


if __name__ == "__main__":
    main()
