import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import SERVICE_ACCOUNT_FILE


def authenticate_google_sheets():
    """Authenticates Google Sheets API."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, [
        "https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"
    ])
    return gspread.authorize(creds)


def save_to_google_sheets(data, sheet_name="Real_Estate_Faceless"):
    """Appends new listings and updates existing ones in Google Sheets."""
    client = authenticate_google_sheets()
    sheet = client.open(sheet_name).sheet1

    existing_rows = sheet.get_all_values()
    existing_urls = {row[0]: idx + 1 for idx, row in enumerate(existing_rows) if row}  # Store URL & row index

    formatted_data = []
    for listing in data:
        row_data = [
            listing.get("listing_url", "N/A"),
            listing.get("price", "N/A"),
            listing.get("address", "N/A"),
            listing.get("beds", "N/A"),
            listing.get("baths", "N/A"),
            listing.get("sqft", "N/A"),
            listing.get("description", "N/A"),
            listing.get("video_url", "N/A"),
            listing.get("instagram_account", "N/A"),
            listing.get("instagram_caption", "N/A")
        ]

        if listing["listing_url"] in existing_urls:
            # ✅ Update existing row
            row_index = existing_urls[listing["listing_url"]]  # Find row number
            sheet.update(f"A{row_index}:J{row_index}", [row_data])
            print(f"✅ Updated existing row {row_index} for {listing['listing_url']}")
        else:
            # ✅ Append new row
            formatted_data.append(row_data)

    if formatted_data:
        sheet.append_rows(formatted_data, value_input_option="RAW")
        print(f"✅ Added {len(formatted_data)} new rows to Google Sheets.")
    else:
        print("✅ No new listings added, only updates applied.")

