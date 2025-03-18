import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import SERVICE_ACCOUNT_FILE, DISABLE_CAPTION_UPDATE
import time
from collections import defaultdict


def authenticate_google_sheets():
    """Authenticates Google Sheets API."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, [
        "https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"
    ])
    return gspread.authorize(creds)


def save_to_google_sheets(data, sheet_name="Real_Estate_Faceless"):
    """Appends new listings and batch updates existing ones in Google Sheets while minimizing read requests."""
    client = authenticate_google_sheets()
    spreadsheet = client.open(sheet_name)

    # ✅ Cache worksheets to prevent multiple API calls
    worksheets = {ws.title: ws for ws in spreadsheet.worksheets()}
    existing_data_cache = {}  # Stores existing rows to reduce API requests

    # ✅ Group listings by county to prevent redundant loops
    listings_by_county = defaultdict(list)
    for listing in data:
        listings_by_county[listing["instagram_account"]].append(listing)

    # ✅ Now process each county only once
    for county_name, listings in listings_by_county.items():
        # ✅ Check if the worksheet exists in cache, otherwise create it
        if county_name in worksheets:
            sheet = worksheets[county_name]
        else:
            print(f"🚀 Creating new worksheet: {county_name}")
            sheet = spreadsheet.add_worksheet(title=county_name, rows="1000", cols="10")
            sheet.append_row([
                "listing_url", "price", "address", "beds", "baths", "sqft", "description", "instagram_account", "instagram_caption", "listing_agents", "agent_company"
            ])
            worksheets[county_name] = sheet

        # ✅ Fetch existing rows only ONCE per worksheet and cache them
        if county_name not in existing_data_cache:
            print(f"📊 Fetching existing data for {county_name} to avoid redundant API calls...")
            existing_rows = sheet.get_all_values()
            existing_urls = {row[0]: idx + 1 for idx, row in enumerate(existing_rows) if row}
            existing_data_cache[county_name] = existing_urls  # ✅ Cache data for this worksheet
        else:
            existing_urls = existing_data_cache[county_name]  # ✅ Use cached data

        formatted_data = []
        batch_updates = []

        for listing in listings:  # ✅ Only process once per listing
            row_data = [
                listing.get("listing_url", "N/A"),
                listing.get("price", "N/A"),
                listing.get("address", "N/A"),
                listing.get("beds", "N/A"),
                listing.get("baths", "N/A"),
                listing.get("sqft", "N/A"),
                listing.get("description", "N/A"),
                listing.get("instagram_caption", "N/A"),
                listing.get("listing_agents", "N/A"),  # ✅ New field
                listing.get("agent_company", "N/A")  # ✅ New fi
            ]

            if listing["listing_url"] in existing_urls:
                row_index = existing_urls[listing["listing_url"]]

                if DISABLE_CAPTION_UPDATE:
                    print(f"🚫 Skipping caption update for {listing['listing_url']}")
                    row_data[-1] = existing_rows[row_index - 1][-1]  # ✅ Keep the existing caption

                batch_updates.append({"range": f"A{row_index}:H{row_index}", "values": [row_data]})
                print(f"✅ Prepared batch update for row {row_index} in {county_name}")
            else:
                formatted_data.append(row_data)

        # ✅ Apply all batch updates at once to avoid rate limits
        if batch_updates:
            sheet.batch_update(batch_updates)
            print(f"✅ Batch updated {len(batch_updates)} rows in {county_name}")

        if formatted_data:
            sheet.append_rows(formatted_data, value_input_option="RAW")
            print(f"✅ Added {len(formatted_data)} new rows to {county_name}.")
        else:
            print(f"✅ No new listings added to {county_name}, only updates applied.")
