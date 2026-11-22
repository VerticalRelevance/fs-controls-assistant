"""Call the Gateway MCP tools with the caller's own verified token."""

import json
import os
import socket
import time
import urllib.error
import urllib.request

GATEWAY_URL = os.environ["GATEWAY_URL"]
TARGET_NAME = "controls-tools"
TOOL_TIMEOUT_SECONDS = 5
MAX_RETRIES = 2


def call_mcp_tool(tool_name, control_id, user_token):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": f"{TARGET_NAME}___{tool_name}",
            "arguments": {"control_id": control_id, "caller_token": user_token},
        },
    }
    request = urllib.request.Request(
        GATEWAY_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TOOL_TIMEOUT_SECONDS) as response:
        reply = json.loads(response.read())
    if "error" in reply:
        return {"ok": False, "error": "gateway_error", "message": reply["error"].get("message", "")}
    text = reply["result"]["content"][0]["text"]
    return json.loads(text)


def call_with_retries(tool_name, control_id, user_token):
    """Bounded retries for retryable errors. Timeouts are not retried."""
    attempts = 0
    while True:
        attempts += 1
        try:
            result = call_mcp_tool(tool_name, control_id, user_token)
        except (TimeoutError, socket.timeout):
            return {"ok": False, "error": "timeout", "message": f"Tool timed out after {TOOL_TIMEOUT_SECONDS}s."}, attempts
        except urllib.error.HTTPError as error:
            if error.code == 401:
                return {"ok": False, "error": "unauthenticated", "message": "Gateway rejected the caller token."}, attempts
            result = {"ok": False, "error": "gateway_http_error", "message": str(error.code), "retryable": error.code >= 500}
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                return {"ok": False, "error": "timeout", "message": f"Tool timed out after {TOOL_TIMEOUT_SECONDS}s."}, attempts
            raise
        if result.get("ok") or not result.get("retryable") or attempts > MAX_RETRIES:
            return result, attempts
        time.sleep(0.5 * attempts)
