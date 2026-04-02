import json
import os
import boto3

WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "pum-trade-dune")

lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    # Parse POST body
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }

    dune_api_key = body.get("dune_api_key")
    if not dune_api_key:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing required field: dune_api_key"})
        }

    # Invoke worker Lambda asynchronously (fire and forget)
    lambda_client.invoke(
        FunctionName=WORKER_FUNCTION_NAME,
        InvocationType="Event",  # async — does not wait for result
        Payload=json.dumps({"body": json.dumps({"dune_api_key": dune_api_key})})
    )

    return {
        "statusCode": 202,
        "body": json.dumps({
            "status": "accepted",
            "message": "Job started. Check the Google Sheet in a few minutes."
        })
    }
