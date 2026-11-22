"""Create the S3 docs bucket, S3 Vectors index, IAM role, Knowledge Base, and run ingestion.

Safe to rerun: it skips anything already saved in .state/resources.json.
"""

import json
import time

import boto3
from botocore.exceptions import ClientError

from controls_assistant.config import PROJECT_ROOT, load_settings
from controls_assistant.state import TAGS, load_state, save_state, tag_list

EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
NAME = "fs-controls-assistant"


def main():
    settings = load_settings()
    session = boto3.Session(profile_name=settings.profile, region_name=settings.region)
    account = session.client("sts").get_caller_identity()["Account"]
    region = settings.region
    s3 = session.client("s3")
    s3v = session.client("s3vectors")
    iam = session.client("iam")
    agent = session.client("bedrock-agent")
    state = load_state()

    bucket = state.get("docs_bucket") or f"{NAME}-docs-{account}-{region}"
    if "docs_bucket" not in state:
        s3.create_bucket(Bucket=bucket)
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={k: True for k in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")},
        )
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": tag_list()})
        state["docs_bucket"] = bucket
        save_state(state)
        print("Created bucket", bucket)

    corpus = PROJECT_ROOT / "data" / "corpus"
    for path in sorted(corpus.iterdir()):
        s3.upload_file(str(path), bucket, f"corpus/{path.name}")
    print("Uploaded", len(list(corpus.iterdir())), "files")

    vector_bucket = f"{NAME}-vectors-{account}"
    index_name = "policies"
    if "vector_index_arn" not in state:
        s3v.create_vector_bucket(vectorBucketName=vector_bucket, tags=TAGS)
        s3v.create_index(
            vectorBucketName=vector_bucket,
            indexName=index_name,
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine",
            metadataConfiguration={"nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]},
        )
        index = s3v.get_index(vectorBucketName=vector_bucket, indexName=index_name)["index"]
        state["vector_bucket"] = vector_bucket
        state["vector_bucket_arn"] = f"arn:aws:s3vectors:{region}:{account}:bucket/{vector_bucket}"
        state["vector_index_arn"] = index["indexArn"]
        save_state(state)
        print("Created vector index", index["indexArn"])

    role_name = f"{NAME}-kb-role"
    if "kb_role_arn" not in state:
        trust = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"aws:SourceAccount": account}},
            }],
        }
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": "bedrock:InvokeModel",
                 "Resource": f"arn:aws:bedrock:{region}::foundation-model/{EMBEDDING_MODEL_ID}"},
                {"Effect": "Allow", "Action": ["s3:GetObject", "s3:ListBucket"],
                 "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]},
                {"Effect": "Allow",
                 "Action": ["s3vectors:PutVectors", "s3vectors:GetVectors", "s3vectors:DeleteVectors",
                            "s3vectors:QueryVectors", "s3vectors:GetIndex"],
                 "Resource": state["vector_index_arn"]},
            ],
        }
        role = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust), Tags=tag_list())
        iam.put_role_policy(RoleName=role_name, PolicyName="kb-access", PolicyDocument=json.dumps(policy))
        state["kb_role_name"] = role_name
        state["kb_role_arn"] = role["Role"]["Arn"]
        save_state(state)
        print("Created role", role_name, "- waiting 15s for IAM")
        time.sleep(15)

    if "kb_id" not in state:
        for attempt in range(5):
            try:
                kb = agent.create_knowledge_base(
                    name=NAME,
                    description="Synthetic policy and control documents for the training project",
                    roleArn=state["kb_role_arn"],
                    knowledgeBaseConfiguration={
                        "type": "VECTOR",
                        "vectorKnowledgeBaseConfiguration": {
                            "embeddingModelArn": f"arn:aws:bedrock:{region}::foundation-model/{EMBEDDING_MODEL_ID}",
                            "embeddingModelConfiguration": {"bedrockEmbeddingModelConfiguration": {"dimensions": 1024}},
                        },
                    },
                    storageConfiguration={
                        "type": "S3_VECTORS",
                        "s3VectorsConfiguration": {"indexArn": state["vector_index_arn"]},
                    },
                    tags=TAGS,
                )["knowledgeBase"]
                break
            except ClientError as error:
                if "role" not in str(error).lower() or attempt == 4:
                    raise
                print("IAM role not ready yet, retrying in 10s")
                time.sleep(10)
        state["kb_id"] = kb["knowledgeBaseId"]
        save_state(state)
        print("Created KB", state["kb_id"])
        while agent.get_knowledge_base(knowledgeBaseId=state["kb_id"])["knowledgeBase"]["status"] != "ACTIVE":
            time.sleep(3)

    if "data_source_id" not in state:
        ds = agent.create_data_source(
            knowledgeBaseId=state["kb_id"],
            name="policy-corpus",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {"bucketArn": f"arn:aws:s3:::{bucket}", "inclusionPrefixes": ["corpus/"]},
            },
            vectorIngestionConfiguration={
                "chunkingConfiguration": {
                    "chunkingStrategy": "FIXED_SIZE",
                    "fixedSizeChunkingConfiguration": {"maxTokens": 300, "overlapPercentage": 10},
                }
            },
            dataDeletionPolicy="DELETE",
        )["dataSource"]
        state["data_source_id"] = ds["dataSourceId"]
        save_state(state)
        print("Created data source", state["data_source_id"])

    job = agent.start_ingestion_job(knowledgeBaseId=state["kb_id"], dataSourceId=state["data_source_id"])["ingestionJob"]
    print("Ingestion started", job["ingestionJobId"])
    while True:
        job = agent.get_ingestion_job(
            knowledgeBaseId=state["kb_id"], dataSourceId=state["data_source_id"], ingestionJobId=job["ingestionJobId"]
        )["ingestionJob"]
        if job["status"] in ("COMPLETE", "FAILED", "STOPPED"):
            break
        time.sleep(5)
    print("Ingestion", job["status"], json.dumps(job["statistics"]))
    if job.get("failureReasons"):
        print("Failures:", job["failureReasons"])
    print(f"\nAdd to .env:\nKNOWLEDGE_BASE_ID={state['kb_id']}")


if __name__ == "__main__":
    main()
