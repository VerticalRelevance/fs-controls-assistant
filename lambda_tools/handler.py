"""Gateway tool backend: get_control_status and get_evidence_status.

The caller is identified only from the Cognito access token, which this function validates itself.
Any user or actor ID in the arguments is ignored.
"""

import json
import os
import re
import time

import boto3

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
COGNITO = boto3.client("cognito-idp")
CONTROL_ID = re.compile(r"^CTL-\d{3}$")
SLOW_CONTROL = "CTL-900"
THROTTLED_CONTROL = "CTL-901"


def error(code, message, retryable=False):
    return {"ok": False, "error": code, "message": message, "retryable": retryable}


def verified_username(token):
    if not isinstance(token, str) or not token:
        return None
    try:
        user = COGNITO.get_user(AccessToken=token)
    except COGNITO.exceptions.NotAuthorizedException:
        return None
    return user["Username"]


def tool_name_from(context):
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    full_name = custom.get("bedrockAgentCoreToolName", "")
    return full_name.split("___")[-1]


def handler(event, context):
    tool = tool_name_from(context)
    username = verified_username(event.get("caller_token"))
    log = {"tool": tool, "user": username, "control_id": event.get("control_id")}

    if username is None:
        result = error("unauthenticated", "Caller token is missing or invalid.")
    else:
        result = run(tool, username, event)

    log["result"] = result.get("error", "ok")
    print(json.dumps(log))
    return result


def run(tool, username, event):
    if tool not in ("get_control_status", "get_evidence_status"):
        return error("unknown_tool", f"Unknown tool {tool!r}.")

    control_id = event.get("control_id")
    if not isinstance(control_id, str) or not CONTROL_ID.match(control_id):
        return error("invalid_argument", f"Invalid control_id {control_id!r}. Expected a value like CTL-001.")

    if control_id == SLOW_CONTROL:
        time.sleep(8)
    if control_id == THROTTLED_CONTROL:
        return error("throttled", "Backend is busy. Try again.", retryable=True)

    scope = TABLE.get_item(Key={"pk": f"USER#{username}"}).get("Item")
    teams = set(scope["teams"]) if scope else set()

    control = TABLE.get_item(Key={"pk": f"CTL#{control_id}"}).get("Item")
    if control is None:
        return error("not_found", f"No control found with ID {control_id}.")
    if control["owner"] not in teams:
        return error("access_denied", f"User {username} is not allowed to view {control_id}.")

    if tool == "get_control_status":
        data = {k: control[k] for k in ("control_id", "name", "owner", "status", "last_tested", "next_test_due", "finding")
                if k in control}
    else:
        data = {"control_id": control_id, "evidence": control.get("evidence", [])}
    return {"ok": True, "data": data}
