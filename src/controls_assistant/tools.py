"""Mock read-only tools. The model only proposes a call; this code decides whether to run it."""

import json
import re

from controls_assistant.config import PROJECT_ROOT

CONTROL_ID_PATTERN = re.compile(r"^CTL-\d{3}$")

GET_CONTROL_STATUS_SPEC = {
    "toolSpec": {
        "name": "get_control_status",
        "description": (
            "Get the current test status of one control by its ID. "
            "Use this for questions about whether a control is effective, deficient, or not tested. "
            "Control IDs look like CTL-001."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "control_id": {
                        "type": "string",
                        "description": "Control ID in the form CTL-NNN, for example CTL-003.",
                    }
                },
                "required": ["control_id"],
                "additionalProperties": False,
            }
        },
    }
}

TOOL_CONFIG = {"tools": [GET_CONTROL_STATUS_SPEC]}


class ToolError(Exception):
    pass


def load_controls():
    with open(PROJECT_ROOT / "data" / "synthetic" / "control_records.json") as f:
        return json.load(f)["controls"]


def get_control_status(args):
    if not isinstance(args, dict) or set(args) != {"control_id"}:
        raise ToolError("Expected exactly one argument: control_id.")
    control_id = args["control_id"]
    if not isinstance(control_id, str) or not CONTROL_ID_PATTERN.match(control_id):
        raise ToolError(f"Invalid control_id {control_id!r}. Expected a value like CTL-001.")

    record = load_controls().get(control_id)
    if record is None:
        raise ToolError(f"No control found with ID {control_id}.")
    return {"control_id": control_id, **record}


TOOLS = {"get_control_status": get_control_status}


def run_tool(name, args):
    if name not in TOOLS:
        raise ToolError(f"Unknown tool {name!r}.")
    return TOOLS[name](args)
