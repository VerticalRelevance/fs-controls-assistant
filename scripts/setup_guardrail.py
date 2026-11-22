"""Create the Guardrail (or update its draft) and publish a new numbered version."""

import boto3

from controls_assistant.config import load_settings
from controls_assistant.state import load_state, save_state, tag_list

NAME = "fs-controls-assistant"

BLOCKED_INPUT = "Sorry, I can't help with that request. I can answer questions about platform policies and controls."
BLOCKED_OUTPUT = "Sorry, I can't share that response. Please rephrase your question about platform policies and controls."

CONFIG = {
    "description": "Input/output safety for the Controls Assistant",
    "topicPolicyConfig": {
        "topicsConfig": [
            {
                "name": "InvestmentAdvice",
                "definition": "Recommendations or opinions about buying, selling, or holding stocks, funds, crypto, or other investments.",
                "examples": [
                    "Should I buy Harbor Point stock?",
                    "Which ETF should I put my bonus into?",
                    "Is now a good time to sell my shares?",
                ],
                "type": "DENY",
            }
        ]
    },
    "contentPolicyConfig": {
        "filtersConfig": [
            {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
            {"type": "MISCONDUCT", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
        ]
    },
    "sensitiveInformationPolicyConfig": {
        "piiEntitiesConfig": [
            {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "BLOCK"},
            {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "BLOCK"},
            {"type": "EMAIL", "action": "ANONYMIZE"},
            {"type": "PHONE", "action": "ANONYMIZE"},
        ],
        "regexesConfig": [
            {
                "name": "SyntheticCustomerAccount",
                "description": "Synthetic customer account numbers like ACCT-12345678",
                "pattern": r"ACCT-\d{8}",
                "action": "ANONYMIZE",
            }
        ],
    },
    "blockedInputMessaging": BLOCKED_INPUT,
    "blockedOutputsMessaging": BLOCKED_OUTPUT,
}


def main():
    settings = load_settings()
    bedrock = boto3.Session(profile_name=settings.profile, region_name=settings.region).client("bedrock")
    state = load_state()

    if "guardrail_id" not in state:
        created = bedrock.create_guardrail(name=NAME, tags=tag_list("key", "value"), **CONFIG)
        state["guardrail_id"] = created["guardrailId"]
        state["guardrail_arn"] = created["guardrailArn"]
        print("Created guardrail", state["guardrail_id"])
    else:
        bedrock.update_guardrail(guardrailIdentifier=state["guardrail_id"], name=NAME, **CONFIG)
        print("Updated guardrail draft", state["guardrail_id"])

    version = bedrock.create_guardrail_version(
        guardrailIdentifier=state["guardrail_id"], description="Published by scripts/setup_guardrail.py"
    )["version"]
    state["guardrail_version"] = version
    save_state(state)
    print(f"Published version {version}\n\nAdd to .env:\nGUARDRAIL_ID={state['guardrail_id']}\nGUARDRAIL_VERSION={version}")


if __name__ == "__main__":
    main()
