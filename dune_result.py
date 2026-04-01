import requests
import time
import csv
import gspread
from google.oauth2.service_account import Credentials
from io import StringIO

# === CONFIG ===
DUNE_API_KEY = "H6OJorFqIQ3u1feaIT8O3vekFN3aFxuZ"
QUERY_ID = "6666216"

GOOGLE_SHEET_NAME = "Pump Pnl"
INPUT_SHEET_NAME = "Internal_wallet"
OUTPUT_SHEET_NAME = "Data"

GOOGLE_CREDS_FILE = "gsheet_credentials.json"

# === AUTH HEADERS ===
headers = {
    "X-DUNE-API-KEY": DUNE_API_KEY,
    "Content-Type": "application/json"
}

# === 1. CONNECT TO GOOGLE SHEETS ===
def get_gsheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client

# === 2. READ PARAMETERS FROM GSHEET ===
def read_parameters(client):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(INPUT_SHEET_NAME)
    data = sheet.get_all_values()

    wallets = []
    for row in data[1:]:  # skip header
        wallets.extend(row[0].split())

    token_address = data[1][1]

    print(f"Wallets: {wallets}")
    print(f"Token Address: {token_address}")

    return wallets, token_address

# === 3. EXECUTE DUNE QUERY ===
def run_dune_query(wallets, token_address):
    query_parameters = {
        "wallets": wallets,
        "token_address": token_address
    }

    execute_url = f"https://api.dune.com/api/v1/query/{QUERY_ID}/execute"
    response = requests.post(
        execute_url,
        headers=headers,
        json={"parameters": query_parameters}
    )
    response.raise_for_status()

    execution_id = response.json().get("execution_id")
    print(f"Execution ID: {execution_id}")

    return execution_id

# === 4. WAIT FOR CSV RESULT ===
def wait_for_csv(execution_id):
    csv_url = f"https://api.dune.com/api/v1/execution/{execution_id}/results/csv"

    while True:
        response = requests.get(csv_url, headers=headers)

        if response.status_code == 200 and response.text.strip():
            print("✅ Query finished!")
            return response.text

        elif response.status_code in [202, 409]:
            print("⏳ Still running... wait 30s")
            time.sleep(30)

        else:
            response.raise_for_status()

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
            # header
            processed_data.append(row)
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
        start_row = i + 1
        end_row = i + len(batch)
        range_name = f"A{start_row}"
        print(f"Writing rows {start_row} to {end_row}...")
        sheet.update(range_name, batch)
        time.sleep(1)  # avoid rate limit

    print("✅ Sheet updated with proper numeric values!")

# === MAIN ===
def main():
    client = get_gsheet_client()

    wallets, token_address = read_parameters(client)

    execution_id = run_dune_query(wallets, token_address)

    csv_text = wait_for_csv(execution_id)

    write_to_gsheet(client, csv_text)

# === RUN ===
if __name__ == "__main__":
    main()