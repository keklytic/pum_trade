import json
import os
import dune_result
from logger import get_logger

log = get_logger(__name__)


def lambda_handler(event, context):
    # Worker reads inputs (wallets + CA) from the Internal_wallet sheet,
    # which the dispatcher populated before invoking us. This avoids the
    # 256KB async-invoke payload limit when the wallets list is large.

    # Validate required env vars
    if not os.environ.get("DUNE_API_KEY"):
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
    log.info("Worker started")
    try:
        dune_result.main(google_creds_dict)
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
        "body": json.dumps({
            "status": "success",
            "message": "Dune query completed and Google Sheet updated",
            "sheet": dune_result.GOOGLE_SHEET_NAME,
            "output_tab": dune_result.OUTPUT_SHEET_NAME
        })
    }
