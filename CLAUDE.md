# pum_trade

Python data pipeline deployed on AWS Lambda. Accepts a token contract address (CA) and a list of wallet addresses via API, queries Dune Analytics, and writes results to Google Sheets.

## Architecture

Two Lambda functions behind one API Gateway POST endpoint:

```
API Gateway POST /prod/pum-trade-dune
    └── pum-trade-dune-dispatcher  (lambda_dispatcher.py)
            │  validates ca + wallets, forwards payload to worker async
            │  returns 202 immediately
            └── pum-trade-dune  (lambda_handler.py)
                    writes wallets + CA → Internal_wallet sheet
                    runs Dune query → polls for CSV result
                    writes results → Data sheet
```

The dispatcher does no data processing — it only validates input and fires the worker async. All `dune_result` calls live in the worker.

## Files

| File | Purpose |
|---|---|
| `dune_result.py` | Core logic — gsheet client, read/write params, run Dune query, poll CSV, write results |
| `lambda_handler.py` | Worker Lambda entry point |
| `lambda_dispatcher.py` | Dispatcher Lambda entry point |
| `requirements.txt` | Pip dependencies for the worker deployment package |

## API

**POST** `https://s7islgip54.execute-api.eu-west-2.amazonaws.com/prod/pum-trade-dune`

```json
{
  "ca": "token_contract_address",
  "wallets": ["0xabc...", "0xdef..."]
}
```

Returns `202 Accepted` immediately. Check the "Data" tab in the "Pump Pnl" Google Sheet for results.

## Google Sheets

- Spreadsheet: **Pump Pnl**
- Input tab: `Internal_wallet` — written by worker (`write_parameters`)
- Output tab: `Data` — written by worker after Dune query completes
- Service account: `pump-pnl@verdant-bruin-435313-h7.iam.gserviceaccount.com` (must have Editor access)

## Lambda Configuration

### pum-trade-dune (worker)
- Handler: `lambda_handler.lambda_handler`
- Runtime: Python 3.11
- Timeout: 900s (15 min)
- Memory: 256 MB
- Env vars: `DUNE_API_KEY`, `GOOGLE_CREDS_JSON`

### pum-trade-dune-dispatcher
- Handler: `lambda_dispatcher.lambda_handler`
- Runtime: Python 3.11
- Timeout: 30s
- Memory: 128 MB
- Env vars: `WORKER_FUNCTION_NAME` (default: `pum-trade-dune`)
- IAM: needs `lambda:InvokeFunction` on the worker ARN

## Deployment

### Worker (pum-trade-dune)
Must be built on Linux — use Docker to avoid `.so` binary incompatibility on macOS:

```bash
rm -rf lambda_package lambda_deployment.zip

docker run --rm \
  --platform linux/x86_64 \
  --entrypoint bash \
  -v "$(pwd):/var/task" \
  -w /var/task \
  public.ecr.aws/lambda/python:3.11 \
  -c "pip install -r requirements.txt -t /var/task/lambda_package/"

cp dune_result.py lambda_handler.py lambda_package/
cd lambda_package && zip -r ../lambda_deployment.zip . && cd ..
```

Upload `lambda_deployment.zip` to the `pum-trade-dune` Lambda.

### Dispatcher (pum-trade-dune-dispatcher)
No pip packages needed (`boto3` is built into Lambda):

```bash
zip dispatcher.zip lambda_dispatcher.py
```

Upload `dispatcher.zip` to the `pum-trade-dune-dispatcher` Lambda.

## Local Testing

```bash
pip install -r requirements.txt

python3 -c "
import json, lambda_dispatcher

fake_event = {
    'httpMethod': 'POST',
    'body': json.dumps({
        'ca': 'your_token_address',
        'wallets': ['0xabc...', '0xdef...']
    })
}
result = lambda_dispatcher.lambda_handler(fake_event, None)
print(json.dumps(result, indent=2))
"
```

Set env vars for local runs:
```bash
export GOOGLE_CREDS_JSON='paste single-line JSON here'
export DUNE_API_KEY='your_key'
```

To generate `GOOGLE_CREDS_JSON` from the credentials file:
```bash
python3 -c "import json; print(json.dumps(json.load(open('gsheet_credentials.json'))))"
```

## Security Notes

- `gsheet_credentials.json` must stay in `.gitignore` — never commit it
- `DUNE_API_KEY` and `GOOGLE_CREDS_JSON` are Lambda environment variables (encrypted at rest by AWS KMS)
- The API Gateway endpoint is public — consider adding an API key (`x-api-key` header) via a usage plan
