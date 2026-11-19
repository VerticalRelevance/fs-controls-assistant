# Financial Services Controls Assistant

Training project for the VR "Amazon Bedrock and AgentCore" two-week module.
Uses synthetic data only.

## Setup

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), and AWS CLI v2.

```sh
uv sync
cp .env.example .env    # then fill in profile, Region, and model IDs
aws sso login --sso-session saml
uv run python scripts/check_access.py
```

`check_access.py` checks who you are logged in as and calls each model in `.env` once.
It refuses to run with a profile that does not start with `vr-`, so client accounts are never used by mistake.

## Account

Profile `vr-training` = VR Labs account `899456967600`, role `AWSAdministratorAccess`, Region `us-east-1`.
A VR org SCP blocks some models. See `.env.example` for the allowed list.
Sonnet 5 does not accept `temperature`, so do not send it to that model.

## Still to write

- Ingestion, invocation, updates, rollback, and teardown steps
- Architecture and permission map
