"""Create the DynamoDB table, load synthetic records, and deploy the tools Lambda."""

import io
import json
import time
import zipfile

import boto3

from controls_assistant.config import PROJECT_ROOT, load_settings
from controls_assistant.state import TAGS, load_state, save_state, tag_list

NAME = "fs-controls-assistant"
TABLE_NAME = f"{NAME}-records"
FUNCTION_NAME = f"{NAME}-tools"
ROLE_NAME = f"{NAME}-tools-lambda-role"


def build_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.write(PROJECT_ROOT / "lambda_tools" / "handler.py", "handler.py")
    return buffer.getvalue()


def main():
    settings = load_settings()
    session = boto3.Session(profile_name=settings.profile, region_name=settings.region)
    account = session.client("sts").get_caller_identity()["Account"]
    dynamodb = session.client("dynamodb")
    iam = session.client("iam")
    lam = session.client("lambda")
    state = load_state()

    if "table_name" not in state:
        dynamodb.create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=tag_list(),
        )
        dynamodb.get_waiter("table_exists").wait(TableName=TABLE_NAME)
        state["table_name"] = TABLE_NAME
        save_state(state)
        print("Created table", TABLE_NAME)

    table = session.resource("dynamodb").Table(TABLE_NAME)
    items = json.loads((PROJECT_ROOT / "data" / "synthetic" / "dynamo_items.json").read_text())["items"]
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    print("Loaded", len(items), "items")

    if "tools_role_arn" not in state:
        trust = {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
        policy = {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": "dynamodb:GetItem",
             "Resource": f"arn:aws:dynamodb:{settings.region}:{account}:table/{TABLE_NAME}"},
            {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
             "Resource": f"arn:aws:logs:{settings.region}:{account}:log-group:/aws/lambda/{FUNCTION_NAME}:*"},
        ]}
        role = iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust), Tags=tag_list())
        iam.put_role_policy(RoleName=ROLE_NAME, PolicyName="tools-access", PolicyDocument=json.dumps(policy))
        state["tools_role_name"] = ROLE_NAME
        state["tools_role_arn"] = role["Role"]["Arn"]
        save_state(state)
        print("Created role", ROLE_NAME, "- waiting 15s for IAM")
        time.sleep(15)

    code = build_zip()
    if "tools_function_arn" not in state:
        fn = lam.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.13",
            Role=state["tools_role_arn"],
            Handler="handler.handler",
            Code={"ZipFile": code},
            Timeout=15,
            MemorySize=256,
            Environment={"Variables": {"TABLE_NAME": TABLE_NAME}},
            Tags=TAGS,
        )
        state["tools_function_arn"] = fn["FunctionArn"]
        save_state(state)
        print("Created function", fn["FunctionArn"])
    else:
        lam.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=code)
        print("Updated function code")
    lam.get_waiter("function_active_v2").wait(FunctionName=FUNCTION_NAME)
    print("Tools Lambda ready:", state["tools_function_arn"])


if __name__ == "__main__":
    main()
