import json
import os
import boto3

WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "pum-trade-dune")

lambda_client = boto3.client("lambda")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Content-Type": "application/json"
}


def lambda_handler(event, context):
    # Parse POST body
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }

    ca = body.get("ca")
    wallets = body.get("wallets")

    if not ca:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing required field: ca"})
        }
    if not wallets or not isinstance(wallets, list):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing or invalid required field: wallets (must be a list)"})
        }

    # Forward ca + wallets to the worker and return immediately
    lambda_client.invoke(
        FunctionName=WORKER_FUNCTION_NAME,
        InvocationType="Event",  # async — does not wait for result
        Payload=json.dumps({"body": json.dumps({"ca": ca, "wallets": wallets})})
    )

    return {
        "statusCode": 202,
        "headers": CORS_HEADERS,
        "body": json.dumps({
            "status": "accepted",
            "wallets_count": len(wallets),
            "message": "Job started. Check the Google Sheet in a few minutes."
        })
    }
