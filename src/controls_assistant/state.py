"""Resource IDs created by the setup scripts, kept in .state/resources.json (not committed)."""

import json

from controls_assistant.config import PROJECT_ROOT

STATE_FILE = PROJECT_ROOT / ".state" / "resources.json"

TAGS = {"owner": "ppathak", "project": "fs-controls-assistant", "purpose": "bedrock-training"}


def load_state():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def tag_list(key_name="Key", value_name="Value"):
    return [{key_name: k, value_name: v} for k, v in TAGS.items()]
