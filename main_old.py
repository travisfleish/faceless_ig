from scraper import scrape_listings
from drive_uploader import create_drive_folder, upload_image_to_drive
from google_sheets import save_to_google_sheets
from instagram_captions import generate_instagram_post
from config import SKIP_IMAGE_UPLOAD  # ✅ Remove DISABLE_CAPTION_UPDATE
import time
import random


def main():
    listings = scrape_listings()
    processed_listings = []  # ✅ Store processed listings to prevent duplicate updates

    for listing in listings:
        # ✅ Only create a folder and upload images if SKIP_IMAGE_UPLOAD is False
        listing_folder_id = None
        if not SKIP_IMAGE_UPLOAD:
            listing_folder_id = create_drive_folder(listing["address"])
            listing["image_urls"] = [
                upload_image_to_drive(img_url, listing_folder_id, listing["address"], idx)
                for idx, img_url in enumerate(listing["image_urls"], start=1)
            ]

        # ✅ Always generate captions (DISABLE_CAPTION_UPDATE removed)
        print(f"⏳ Generating caption for: {listing['address']}...")
        listing["instagram_caption"] = generate_instagram_post(
            listing["description"], listing["price"], listing["beds"],
            listing["baths"], listing["sqft"], listing["address"]
        )
        print(f"✅ Caption generated for: {listing['address']}")
        time.sleep(random.uniform(2, 5))  # ✅ Prevents OpenAI rate-limiting

        # ✅ Add listing to processed list to avoid duplicates
        processed_listings.append(listing)

    # ✅ Process ALL listings once at the end
    sheet_name = "Real_Estate_Faceless"
    print(f"📤 Uploading data to Google Sheet: {sheet_name}")
    save_to_google_sheets(processed_listings, sheet_name)  # ✅ Pass processed listings
    print("✅ Data successfully saved!")


if __name__ == "__main__":
    main()