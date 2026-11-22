"""Knowledge Base retrieval with prompt-attack screening of each passage."""

import os

import boto3

MIN_SCORE = 0.65
NUM_RESULTS = 6

REGION = os.getenv("AWS_REGION", "us-east-1")
KB_ID = os.getenv("KNOWLEDGE_BASE_ID")
GUARDRAIL_ID = os.getenv("GUARDRAIL_ID")
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION")

agent_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)
runtime = boto3.client("bedrock-runtime", region_name=REGION)


def search(question):
    response = agent_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": NUM_RESULTS}},
    )
    kept, dropped = [], []
    for item in response["retrievalResults"]:
        if item["score"] < MIN_SCORE:
            continue
        meta = item.get("metadata", {})
        passage = {
            "source_id": meta.get("source_id"),
            "version": meta.get("version"),
            "status": meta.get("status"),
            "effective_date": meta.get("effective_date"),
            "score": round(item["score"], 3),
            "text": item["content"]["text"],
        }
        check = runtime.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID, guardrailVersion=GUARDRAIL_VERSION,
            source="INPUT", content=[{"text": {"text": passage["text"]}}],
        )
        if check["action"] == "GUARDRAIL_INTERVENED":
            dropped.append({"source_id": passage["source_id"], "version": passage["version"]})
        else:
            kept.append(passage)
    return kept, dropped


def check_text(text, source):
    """Run the Guardrail on user input or final output. Returns (blocked, text_to_use, reasons)."""
    result = runtime.apply_guardrail(
        guardrailIdentifier=GUARDRAIL_ID, guardrailVersion=GUARDRAIL_VERSION,
        source=source, content=[{"text": {"text": text}}],
    )
    if result["action"] != "GUARDRAIL_INTERVENED":
        return False, text, []
    reasons = []
    for a in result.get("assessments", []):
        reasons += [f"content:{f['type']}" for f in a.get("contentPolicy", {}).get("filters", [])]
        reasons += [f"topic:{t['name']}" for t in a.get("topicPolicy", {}).get("topics", [])]
        reasons += [f"pii:{p['type']}:{p['action']}" for p in a.get("sensitiveInformationPolicy", {}).get("piiEntities", [])]
        reasons += [f"regex:{r['name']}:{r['action']}" for r in a.get("sensitiveInformationPolicy", {}).get("regexes", [])]
    output_text = "".join(o.get("text", "") for o in result.get("outputs", []))
    fully_blocked = any(":BLOCKED" in r for r in reasons) or any(r.startswith(("content:", "topic:")) for r in reasons)
    return fully_blocked, output_text, reasons
