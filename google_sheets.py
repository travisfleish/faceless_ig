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

            # Check if headers need to be updated (missing agent columns)
            try:
                header_row = sheet.row_values(1)
                if len(header_row) < 11 or "listing_agents" not in header_row or "agent_company" not in header_row:
                    print(f"📊 Updating headers for {county_name} to include agent columns")
                    sheet.update('A1:K1', [[
                        "listing_url", "price", "address", "beds", "baths", "sqft", "description",
                        "instagram_account", "instagram_caption", "listing_agents", "agent_company"
                    ]])
            except Exception as e:
                print(f"⚠️ Error checking header row: {e}")
                # Continue with best effort
        else:
            print(f"🚀 Creating new worksheet: {county_name}")
            sheet = spreadsheet.add_worksheet(title=county_name, rows="1000", cols="11")  # Ensure 11 columns
            sheet.update('A1:K1', [[
                "listing_url", "price", "address", "beds", "baths", "sqft", "description",
                "instagram_account", "instagram_caption", "listing_agents", "agent_company"
            ]])
            worksheets[county_name] = sheet

        # ✅ Fetch existing rows only ONCE per worksheet and cache them
        if county_name not in existing_data_cache:
            print(f"📊 Fetching existing data for {county_name} to avoid redundant API calls...")
            try:
                existing_rows = sheet.get_all_values()
                existing_urls = {row[0]: idx + 1 for idx, row in enumerate(existing_rows) if row and len(row) > 0}
                existing_data_cache[county_name] = (existing_urls, existing_rows)  # Cache both URLs and rows
            except Exception as e:
                print(f"⚠️ Error fetching existing data: {e}")
                existing_urls, existing_rows = {}, []
                existing_data_cache[county_name] = (existing_urls, existing_rows)
        else:
            existing_urls, existing_rows = existing_data_cache[county_name]  # Use cached data

        formatted_data = []
        batch_updates = []

        for listing in listings:  # ✅ Only process once per listing
            # Create full row data with all columns in the correct order
            row_data = [
                listing.get("listing_url", "N/A"),
                listing.get("price", "N/A"),
                listing.get("address", "N/A"),
                listing.get("beds", "N/A"),
                listing.get("baths", "N/A"),
                listing.get("sqft", "N/A"),
                listing.get("description", "N/A"),
                listing.get("instagram_account", "N/A"),  # Make sure instagram_account is included
                listing.get("instagram_caption", "N/A"),
                listing.get("listing_agents", "N/A"),
                listing.get("agent_company", "N/A")
            ]

            # Check if this is an update or a new listing
            if listing["listing_url"] in existing_urls:
                row_index = existing_urls[listing["listing_url"]]

                # Get existing row to preserve data if needed
                existing_row = existing_rows[row_index - 1] if row_index - 1 < len(existing_rows) else []

                # Handle caption updates based on settings
                if DISABLE_CAPTION_UPDATE and len(existing_row) >= 9:  # Check if caption column exists
                    print(f"🚫 Skipping caption update for {listing['listing_url']}")
                    row_data[8] = existing_row[8]  # Keep the existing caption (index 8)

                # Create the proper range string for all 11 columns
                range_str = f"A{row_index}:K{row_index}"  # A through K (11 columns)

                batch_updates.append({"range": range_str, "values": [row_data]})
                print(f"✅ Prepared batch update for row {row_index} in {county_name}")
            else:
                formatted_data.append(row_data)

        # ✅ Apply all batch updates at once to avoid rate limits
        if batch_updates:
            try:
                sheet.batch_update(batch_updates)
                print(f"✅ Batch updated {len(batch_updates)} rows in {county_name}")
            except Exception as e:
                print(f"❌ Error in batch update: {e}")

                # Fallback: try updating one row at a time
                for update in batch_updates:
                    try:
                        row_num = update["range"].split(":")[0][1:]  # Extract row number
                        sheet.update(update["range"], update["values"])
                        print(f"✅ Updated row {row_num} individually")
                    except Exception as row_error:
                        print(f"❌ Could not update row: {row_error}")

        # ✅ Add any new listings
        if formatted_data:
            try:
                sheet.append_rows(formatted_data, value_input_option="RAW")
                print(f"✅ Added {len(formatted_data)} new rows to {county_name}.")
            except Exception as e:
                print(f"❌ Error adding new rows: {e}")
                # Try adding one at a time
                for row in formatted_data:
                    try:
                        sheet.append_row(row, value_input_option="RAW")
                        print(f"✅ Added a single new row for {row[2]}")
                    except Exception as row_error:
                        print(f"❌ Could not add row: {row_error}")
        else:
            print(f"✅ No new listings added to {county_name}, only updates applied.")