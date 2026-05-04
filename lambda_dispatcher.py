import json
import os
import boto3
import dune_result
from logger import get_logger

log = get_logger(__name__)

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

    # Load Google credentials from env
    google_creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if not google_creds_json:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "GOOGLE_CREDS_JSON not set in Lambda environment"})
        }
    try:
        google_creds_dict = json.loads(google_creds_json)
    except json.JSONDecodeError:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "GOOGLE_CREDS_JSON is not valid JSON"})
        }

    # Write the wallets + CA to the input sheet here in the dispatcher.
    # This avoids the 256KB Lambda async-invoke payload limit when the
    # wallets list is large — the worker re-reads the sheet instead of
    # receiving the wallets via its event payload.
    log.info(f"Dispatching job: ca={ca} wallets_count={len(wallets)} worker={WORKER_FUNCTION_NAME}")
    try:
        client = dune_result.get_gsheet_client(google_creds_dict)
        dune_result.write_parameters(client, wallets, ca)
    except Exception as e:
        log.error(f"Failed to write parameters to sheet: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to write parameters to sheet: {e}"})
        }

    # Invoke worker Lambda asynchronously with an empty payload (worker
    # reads its inputs from the sheet we just populated).
    lambda_client.invoke(
        FunctionName=WORKER_FUNCTION_NAME,
        InvocationType="Event",  # async — does not wait for result
        Payload=json.dumps({"body": json.dumps({})})
    )

    log.info("Worker invoked successfully")
    return {
        "statusCode": 202,
        "body": json.dumps({
            "status": "accepted",
            "wallets_count": len(wallets),
            "message": "Job started. Check the Google Sheet in a few minutes."
        })
    }
