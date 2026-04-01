import json
import os
import dune_result

CREDS_FILE = os.path.join(os.path.dirname(__file__), "gsheet_credentials.json")


def lambda_handler(event, context):
    # Parse POST body
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON in request body"})
        }

    # Extract dune_api_key from POST body
    dune_api_key = body.get("dune_api_key")
    if not dune_api_key:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing required field: dune_api_key"})
        }

    # Load Google credentials from bundled JSON file
    try:
        with open(CREDS_FILE) as f:
            google_creds_dict = json.load(f)
    except FileNotFoundError:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "gsheet_credentials.json not found in deployment package"})
        }

    # Run the pipeline
    try:
        dune_result.main(dune_api_key, google_creds_dict)
    except TimeoutError as e:
        return {
            "statusCode": 504,
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "success",
            "message": "Dune query completed and Google Sheet updated",
            "sheet": dune_result.GOOGLE_SHEET_NAME,
            "output_tab": dune_result.OUTPUT_SHEET_NAME
        })
    }
