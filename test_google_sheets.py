import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import SERVICE_ACCOUNT_FILE


def test_google_sheets():
    """Tests reading and writing to Google Sheets."""
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, [
        "https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"
    ]))

    sheet = client.open("Real_Estate_Faceless").sheet1
    existing_data = sheet.get_all_values()

    print(f"✅ Connected to Google Sheets. Existing rows: {len(existing_data)}")

    # ✅ Test writing
    sheet.append_row(["NEWTest URL", "Test Price", "Test Address", "Beds", "Baths", "Sqft", "Description", "Caption"])
    print("✅ Successfully added a test row!")


test_google_sheets()
