"""Check that the training account, Region, and model access work before Day 1."""

import os
import sys
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

FORBIDDEN_PROFILES = {"default", "fanduel", "awsadmin"}


def check_identity(session):
    identity = session.client("sts").get_caller_identity()
    print(f"Account: {identity['Account']}")
    print(f"Caller:  {identity['Arn']}")


def check_model(session, model_id):
    client = session.client("bedrock-runtime")
    start = time.perf_counter()
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": "Reply with the word OK."}]}],
        inferenceConfig={"maxTokens": 20},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    print(
        f"{model_id}: '{text.strip()}' "
        f"in={usage['inputTokens']} out={usage['outputTokens']} {elapsed_ms:.0f} ms"
    )


def main():
    load_dotenv()
    profile = os.getenv("AWS_PROFILE")
    region = os.getenv("AWS_REGION")
    if not profile or not region:
        sys.exit("Set AWS_PROFILE and AWS_REGION in .env first.")
    if profile in FORBIDDEN_PROFILES or not profile.startswith("vr-"):
        sys.exit(f"Profile '{profile}' does not look like the VR training profile. Stopping.")

    session = boto3.Session(profile_name=profile, region_name=region)
    print(f"Profile: {profile}  Region: {region}")

    try:
        check_identity(session)
    except (BotoCoreError, ClientError) as error:
        sys.exit(f"Login check failed: {error}. Try: aws sso login --profile {profile}")

    model_ids = [m for m in (os.getenv("MODEL_ID_A"), os.getenv("MODEL_ID_B")) if m]
    if not model_ids:
        sys.exit("Set MODEL_ID_A and MODEL_ID_B in .env to test model access.")

    failed = False
    for model_id in model_ids:
        try:
            check_model(session, model_id)
        except (BotoCoreError, ClientError) as error:
            print(f"{model_id}: FAILED - {error}")
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
