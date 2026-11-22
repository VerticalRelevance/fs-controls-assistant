"""Create a Cognito user pool, an app client, and two test users (alice, bob)."""

import secrets

import boto3

from controls_assistant.config import load_settings
from controls_assistant.state import TAGS, load_state, save_state

NAME = "fs-controls-assistant"
USERS = ["alice", "bob"]


def main():
    settings = load_settings()
    cognito = boto3.Session(profile_name=settings.profile, region_name=settings.region).client("cognito-idp")
    state = load_state()

    if "user_pool_id" not in state:
        pool = cognito.create_user_pool(
            PoolName=NAME,
            Policies={"PasswordPolicy": {"MinimumLength": 12, "RequireUppercase": True, "RequireLowercase": True,
                                         "RequireNumbers": True, "RequireSymbols": False}},
            AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
            UserPoolTags=TAGS,
        )["UserPool"]
        state["user_pool_id"] = pool["Id"]
        save_state(state)
        print("Created user pool", pool["Id"])

    if "app_client_id" not in state:
        client = cognito.create_user_pool_client(
            UserPoolId=state["user_pool_id"],
            ClientName=f"{NAME}-cli",
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
            AccessTokenValidity=60,
            TokenValidityUnits={"AccessToken": "minutes"},
        )["UserPoolClient"]
        state["app_client_id"] = client["ClientId"]
        save_state(state)
        print("Created app client", client["ClientId"])

    passwords = state.get("test_passwords", {})
    for user in USERS:
        if user in passwords:
            continue
        password = "Tr" + secrets.token_urlsafe(12) + "9"
        cognito.admin_create_user(UserPoolId=state["user_pool_id"], Username=user, MessageAction="SUPPRESS")
        cognito.admin_set_user_password(UserPoolId=state["user_pool_id"], Username=user, Password=password, Permanent=True)
        passwords[user] = password
        print("Created user", user)
    state["test_passwords"] = passwords

    state["discovery_url"] = (
        f"https://cognito-idp.{settings.region}.amazonaws.com/{state['user_pool_id']}/.well-known/openid-configuration"
    )
    save_state(state)
    print("Discovery URL:", state["discovery_url"])
    print("Passwords are stored in .state/resources.json (not committed).")


if __name__ == "__main__":
    main()
