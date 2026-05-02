import json
import os
import dune_result


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

    # Load Google credentials from Lambda environment variable
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
