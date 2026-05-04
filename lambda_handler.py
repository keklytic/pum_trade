import json
import os
import dune_result
from logger import get_logger

log = get_logger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Content-Type": "application/json"
}


def lambda_handler(event, context):
    # Parse event body (forwarded by dispatcher)
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }

    ca = body.get("ca")
    wallets = body.get("wallets")

    if not ca or not wallets:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing required fields: ca, wallets"})
        }

    # Load env vars
    dune_api_key = os.environ.get("DUNE_API_KEY")
    if not dune_api_key:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "DUNE_API_KEY not set in Lambda environment"})
        }

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

    # Run the pipeline
    log.info(f"Worker started: ca={ca} wallets_count={len(wallets)}")
    try:
        client = dune_result.get_gsheet_client(google_creds_dict)
        dune_result.write_parameters(client, wallets, ca)
        dune_result.main(google_creds_dict, dune_api_key)
    except TimeoutError as e:
        log.error(f"Dune query timed out: {e}")
        return {
            "statusCode": 504,
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        log.error(f"Worker pipeline failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

    log.info("Worker pipeline completed successfully")
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps({
            "status": "success",
            "message": "Dune query completed and Google Sheet updated",
            "sheet": dune_result.GOOGLE_SHEET_NAME,
            "output_tab": dune_result.OUTPUT_SHEET_NAME
        })
    }
