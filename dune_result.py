import os
import requests
import time
import csv
import gspread
from google.oauth2.service_account import Credentials
from io import StringIO
import json

# === CONFIG ===
QUERY_ID = "6666216"

GOOGLE_SHEET_NAME = "Pump Pnl"
INPUT_SHEET_NAME = "Internal_wallet"
OUTPUT_SHEET_NAME = "Data"


# === 1. CONNECT TO GOOGLE SHEETS ===
def get_gsheet_client(google_creds_dict):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(google_creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

# === 2a. WRITE PARAMETERS TO GSHEET (called by dispatcher) ===
def write_parameters(client, wallets, token_address):
    spreadsheet = client.open(GOOGLE_SHEET_NAME)

    try:
        sheet = spreadsheet.worksheet(INPUT_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        print(f"Sheet '{INPUT_SHEET_NAME}' not found. Creating it...")
        rows_needed = max(1000, len(wallets) + 10)
        sheet = spreadsheet.add_worksheet(title=INPUT_SHEET_NAME, rows=str(rows_needed), cols="2")

    sheet.clear()

    rows = [["wallet", "token_address"]]
    for i, wallet in enumerate(wallets):
        rows.append([wallet, token_address if i == 0 else ""])

    # Batch write to avoid large payload errors when wallets list is huge
    BATCH_SIZE = 1000
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        range_name = f"A{i+1}"
        sheet.update(range_name, batch)
        time.sleep(1)  # avoid rate limit

    print(f"✅ Wrote {len(wallets)} wallets and CA to '{INPUT_SHEET_NAME}'")

# === 2b. READ PARAMETERS FROM GSHEET (called by worker) ===
def read_parameters(client):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(INPUT_SHEET_NAME)
    data = sheet.get_all_values()

    wallets = []
    for row in data[1:]:  # skip header
        if row and row[0].strip():
            wallets.extend(row[0].split())

    token_address = data[1][1] if len(data) > 1 and len(data[1]) > 1 else ""

    print(f"Wallets count: {len(wallets)}")
    print(f"Token Address: {token_address}")

    return wallets, token_address

# === 3. EXECUTE DUNE QUERY ===
def run_dune_query(wallets, token_address, dune_api_key):
    headers = {
        "X-DUNE-API-KEY": dune_api_key,
        "Content-Type": "application/json"
    }

    wallets_str = ",".join(f"'{w.strip()}'" for w in wallets if w.strip())
    token_address = token_address.strip()

    print(f"--- Dune Params Debug ---")
    print(f"token_address: {token_address}")
    print(f"wallets_str:   {wallets_str}")
    print(f"-------------------------")

    payload = {
        "query_parameters": {        # ← correct Dune v1 key
            "wallets": wallets_str,
            "token_address": token_address
        }
    }

    execute_url = f"https://api.dune.com/api/v1/query/{QUERY_ID}/execute"
    response = requests.post(execute_url, headers=headers, json=payload)
    print(f"Execute response: {response.status_code} {response.text}")
    response.raise_for_status()

    execution_id = response.json().get("execution_id")
    print(f"Execution ID: {execution_id}")

    return execution_id

# === 4. WAIT FOR CSV RESULT ===
def wait_for_csv(execution_id, dune_api_key):
    headers = {
        "X-DUNE-API-KEY": dune_api_key,
        "Content-Type": "application/json"
    }
    csv_url = f"https://api.dune.com/api/v1/execution/{execution_id}/results/csv"
    start_time = time.time()
    max_wait = 12 * 60  # 12 minutes — stay within Lambda 15-min timeout

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            raise TimeoutError(f"Dune query did not complete within {max_wait // 60} minutes")
        try:
            response = requests.get(csv_url, headers=headers)
            if response.status_code == 200 and response.text.strip():
                print("✅ Query finished!")
                return response.text
            elif response.status_code in [202, 409]:
                print("⏳ Still running... wait 30s")
                time.sleep(30)
            else:
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"⚠ Network error: {e}, retrying in 10s...")
            time.sleep(10)

# === 5. WRITE TO GOOGLE SHEET (CLEAR FIRST + NUMBERS) ===
def write_to_gsheet(client, csv_text):
    spreadsheet = client.open(GOOGLE_SHEET_NAME)

    try:
        sheet = spreadsheet.worksheet(OUTPUT_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        print(f"Sheet '{OUTPUT_SHEET_NAME}' not found. Creating it...")
        sheet = spreadsheet.add_worksheet(title=OUTPUT_SHEET_NAME, rows="1000", cols="20")

    # Parse CSV
    reader = csv.reader(StringIO(csv_text))
    data = list(reader)

    print(f"Writing {len(data)} rows to Google Sheet...")

    # Clear sheet first
    sheet.clear()

    # Convert numeric strings to floats, keep first column as string
    processed_data = []
    for i, row in enumerate(data):
        if i == 0:
            processed_data.append(row)  # header
            continue
        new_row = [row[0]]  # first column = wallet (string)
        for cell in row[1:]:
            try:
                new_row.append(float(cell))
            except ValueError:
                new_row.append(cell)
        processed_data.append(new_row)

    # Batch write to avoid large payload issues
    BATCH_SIZE = 500
    for i in range(0, len(processed_data), BATCH_SIZE):
        batch = processed_data[i:i + BATCH_SIZE]
        range_name = f"A{i+1}"
        sheet.update(range_name, batch)
        time.sleep(1)  # avoid rate limit

    print("✅ Sheet updated with proper numeric values!")

# === MAIN (worker pipeline: reads input sheet, runs Dune, writes output sheet) ===
def main(google_creds_dict, dune_api_key):
    client = get_gsheet_client(google_creds_dict)
    wallets, token_address = read_parameters(client)
    execution_id = run_dune_query(wallets, token_address, dune_api_key)
    csv_text = wait_for_csv(execution_id, dune_api_key)
    write_to_gsheet(client, csv_text)

# === RUN (local) ===
if __name__ == "__main__":
    _creds = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    _dune_api_key = os.environ["DUNE_API_KEY"]
    main(_creds, _dune_api_key)
