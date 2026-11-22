"""Delete every billable resource this project created, then check nothing is left.

Usage: uv run python scripts/teardown.py --yes
"""

import argparse
import time

import boto3
from botocore.exceptions import ClientError

from controls_assistant.config import load_settings
from controls_assistant.state import TAGS, load_state, save_state


def quiet(label, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        print("deleted:", label)
    except ClientError as error:
        code = error.response["Error"]["Code"]
        print(f"skip: {label} ({code})")


def empty_versioned_bucket(s3, bucket):
    paginator = s3.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket):
        objects = [{"Key": v["Key"], "VersionId": v["VersionId"]} for v in page.get("Versions", []) + page.get("DeleteMarkers", [])]
        if objects:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Required. Confirms you want to delete everything.")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("Add --yes to delete all project resources.")

    settings = load_settings()
    session = boto3.Session(profile_name=settings.profile, region_name=settings.region)
    state = load_state()

    if state.get("agentcore_stack"):
        cfn = session.client("cloudformation")
        quiet("AgentCore stack " + state["agentcore_stack"], cfn.delete_stack, StackName=state["agentcore_stack"])
        print("waiting for AgentCore stack delete (Runtime, Memory, Gateway, roles)...")
        cfn.get_waiter("stack_delete_complete").wait(StackName=state["agentcore_stack"], WaiterConfig={"Delay": 15, "MaxAttempts": 80})

    lam, iam, logs = session.client("lambda"), session.client("iam"), session.client("logs")
    if state.get("tools_function_arn"):
        quiet("tools Lambda", lam.delete_function, FunctionName=state["tools_function_arn"])
        quiet("tools Lambda log group", logs.delete_log_group, logGroupName="/aws/lambda/fs-controls-assistant-tools")
    for role_key in ("tools_role_name", "kb_role_name"):
        role = state.get(role_key)
        if role:
            for name in iam.list_role_policies(RoleName=role).get("PolicyNames", []) if _exists(iam, role) else []:
                iam.delete_role_policy(RoleName=role, PolicyName=name)
            quiet(f"IAM role {role}", iam.delete_role, RoleName=role)

    if state.get("table_name"):
        quiet("DynamoDB table", session.client("dynamodb").delete_table, TableName=state["table_name"])
    if state.get("user_pool_id"):
        quiet("Cognito user pool", session.client("cognito-idp").delete_user_pool, UserPoolId=state["user_pool_id"])

    agent = session.client("bedrock-agent")
    if state.get("kb_id"):
        if state.get("data_source_id"):
            quiet("KB data source", agent.delete_data_source, knowledgeBaseId=state["kb_id"], dataSourceId=state["data_source_id"])
            time.sleep(10)
        quiet("Knowledge Base", agent.delete_knowledge_base, knowledgeBaseId=state["kb_id"])
        time.sleep(10)
    if state.get("guardrail_id"):
        quiet("Guardrail", session.client("bedrock").delete_guardrail, guardrailIdentifier=state["guardrail_id"])

    s3v = session.client("s3vectors")
    if state.get("vector_bucket"):
        quiet("vector index", s3v.delete_index, vectorBucketName=state["vector_bucket"], indexName="policies")
        quiet("vector bucket", s3v.delete_vector_bucket, vectorBucketName=state["vector_bucket"])
    if state.get("docs_bucket"):
        s3 = session.client("s3")
        try:
            empty_versioned_bucket(s3, state["docs_bucket"])
        except ClientError:
            pass
        quiet("docs bucket", s3.delete_bucket, Bucket=state["docs_bucket"])

    for group in logs.describe_log_groups(logGroupNamePrefix="/aws/bedrock-agentcore/runtimes/ControlsAssistant").get("logGroups", []):
        quiet("log group " + group["logGroupName"], logs.delete_log_group, logGroupName=group["logGroupName"])

    time.sleep(5)
    leftovers = session.client("resourcegroupstaggingapi").get_resources(
        TagFilters=[{"Key": "project", "Values": [TAGS["project"]]}])["ResourceTagMappingList"]
    print("\nTagged resources still listed:", [r["ResourceARN"] for r in leftovers] or "none")
    print("(The tagging API can lag a few minutes after deletes.)")
    save_state({"torn_down_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "previous": state})


def _exists(iam, role):
    try:
        iam.get_role(RoleName=role)
        return True
    except ClientError:
        return False


if __name__ == "__main__":
    main()
