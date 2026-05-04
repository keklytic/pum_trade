# pum_trade

Python data pipeline deployed on AWS Lambda. Accepts a token contract address (CA) and a list of wallet addresses via API, queries Dune Analytics, and writes results to Google Sheets.

## Architecture

Two Lambda functions behind one API Gateway POST endpoint:

```
API Gateway POST /prod/pum-trade-dune
    └── pum-trade-dune-dispatcher  (lambda_dispatcher.py)
            │  validates ca + wallets, writes wallets+CA to Internal_wallet sheet
            │  invokes worker async with empty payload, returns 202 immediately
            └── pum-trade-dune  (lambda_handler.py)
                    reads wallets + CA from Internal_wallet sheet
                    runs Dune query → polls for CSV result
                    writes results → Data sheet
```

The dispatcher writes input params to the sheet before invoking the worker — this avoids the 256KB async-invoke payload limit for large wallet lists.

## Files

| File | Purpose |
|---|---|
| `dune_result.py` | Core logic — gsheet client, read/write params, run Dune query, poll CSV, write results |
| `lambda_handler.py` | Worker Lambda entry point |
| `lambda_dispatcher.py` | Dispatcher Lambda entry point |
| `logger.py` | Structured JSON logger with optional Loki push |
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
- Input tab: `Internal_wallet` — written by dispatcher (`write_parameters`)
- Output tab: `Data` — written by worker after Dune query completes
- Service account: `pump-pnl@verdant-bruin-435313-h7.iam.gserviceaccount.com` (must have Editor access)

## Lambda Configuration

### pum-trade-dune (worker)
- Handler: `lambda_handler.lambda_handler`
- Runtime: Python 3.11
- Timeout: 900s (15 min)
- Memory: 256 MB
- Env vars: `DUNE_API_KEY`, `GOOGLE_CREDS_JSON`, `LOKI_URL`, `LOKI_USERNAME`, `LOKI_PASSWORD`, `LOG_LEVEL`, `ENV`

### pum-trade-dune-dispatcher
- Handler: `lambda_dispatcher.lambda_handler`
- Runtime: Python 3.11
- Timeout: 30s
- Memory: 128 MB
- Env vars: `WORKER_FUNCTION_NAME` (default: `pum-trade-dune`), `GOOGLE_CREDS_JSON`, `LOKI_URL`, `LOKI_USERNAME`, `LOKI_PASSWORD`, `LOG_LEVEL`, `ENV`
- IAM: needs `lambda:InvokeFunction` on the worker ARN

## Logging

Logs are emitted as structured JSON. Set `LOKI_URL` + `LOKI_USERNAME` + `LOKI_PASSWORD` to push directly to Grafana Loki.

| Env var | Example |
|---|---|
| `LOKI_URL` | `https://logs-prod-us-central1.grafana.net/loki/api/v1/push` |
| `LOKI_USERNAME` | Grafana Cloud tenant ID (numeric) |
| `LOKI_PASSWORD` | Grafana Cloud API key with `logs:write` scope |
| `LOG_LEVEL` | `INFO` (default) |
| `ENV` | `prod` (default) |

Query in Grafana: `{service="pum-trade", env="prod"}`

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

cp dune_result.py lambda_handler.py logger.py lambda_package/
cd lambda_package && zip -r ../lambda_deployment.zip . && cd ..
```

Upload `lambda_deployment.zip` to the `pum-trade-dune` Lambda.

### Dispatcher (pum-trade-dune-dispatcher)
Now requires `python-logging-loki` — must also be built on Linux via Docker:

```bash
rm -rf dispatcher_package dispatcher.zip

docker run --rm \
  --platform linux/x86_64 \
  --entrypoint bash \
  -v "$(pwd):/var/task" \
  -w /var/task \
  public.ecr.aws/lambda/python:3.11 \
  -c "pip install -r /var/task/requirements.txt -t /var/task/dispatcher_package/"

cp lambda_dispatcher.py dune_result.py logger.py dispatcher_package/
cd dispatcher_package && zip -r ../dispatcher.zip . && cd ..
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
export LOKI_URL='https://...'        # optional
export LOKI_USERNAME='...'           # optional
export LOKI_PASSWORD='...'           # optional
```

To generate `GOOGLE_CREDS_JSON` from the credentials file:
```bash
python3 -c "import json; print(json.dumps(json.load(open('gsheet_credentials.json'))))"
```

## Security Notes

- `gsheet_credentials.json` must stay in `.gitignore` — never commit it
- `DUNE_API_KEY` and `GOOGLE_CREDS_JSON` are Lambda environment variables (encrypted at rest by AWS KMS)
- The API Gateway endpoint is public — consider adding an API key (`x-api-key` header) via a usage plan
