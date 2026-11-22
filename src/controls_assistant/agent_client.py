"""Test client: log in as a Cognito test user and call the deployed agent on AgentCore Runtime."""

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid

import boto3

from controls_assistant.config import load_settings
from controls_assistant.state import load_state


def login(username, state, region):
    """Return a Cognito access token for a test user, or None for the unauthenticated case."""
    if username is None:
        return None
    cognito = boto3.client("cognito-idp", region_name=region)
    result = cognito.initiate_auth(
        ClientId=state["app_client_id"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": state["test_passwords"][username]},
    )
    return result["AuthenticationResult"]["AccessToken"]


def new_session_id():
    return f"session-{uuid.uuid4().hex}"


def invoke(token, payload, session_id, state, region, timeout=120):
    arn = urllib.parse.quote(state["runtime_arn"], safe="")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{arn}/invocations?qualifier=DEFAULT"
    headers = {
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"http_status": response.status, **json.loads(response.read())}
    except urllib.error.HTTPError as error:
        return {"http_status": error.code, "status": "rejected", "error": error.read().decode()[:300]}


def main():
    parser = argparse.ArgumentParser(description="Call the deployed Controls Assistant as a test user.")
    parser.add_argument("prompt")
    parser.add_argument("--user", default="alice", choices=["alice", "bob", "none"])
    parser.add_argument("--session", help="Reuse a session ID. Default is a new session.")
    parser.add_argument("--extra", default="{}", help='Extra payload JSON, e.g. \'{"actor_id": "bob"}\'')
    args = parser.parse_args()

    settings = load_settings()
    state = load_state()
    token = login(None if args.user == "none" else args.user, state, settings.region)
    session_id = args.session or new_session_id()
    payload = {"prompt": args.prompt, **json.loads(args.extra)}
    result = invoke(token, payload, session_id, state, settings.region)
    print(json.dumps(result, indent=2))
    print(f"\nsession: {session_id}")


if __name__ == "__main__":
    main()
