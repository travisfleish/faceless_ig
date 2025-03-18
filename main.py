from scraper import scrape_listings, scrape_specific_listing
from drive_uploader import create_drive_folder, upload_image_to_drive, authenticate_google_drive
from google_sheets import save_to_google_sheets
from instagram_captions import generate_instagram_post
from config import SKIP_IMAGE_UPLOAD, IMAGE_ONLY_MODE, GOOGLE_DRIVE_FOLDER_ID
import time
import random


def get_existing_drive_folders():
    """Get all existing folders in the main Google Drive folder."""
    drive_service = authenticate_google_drive()
    existing_folders = {}
    existing_folder_variants = {}

    try:
        query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = drive_service.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name)",
            pageSize=1000
        ).execute()

        items = results.get('files', [])

        for item in items:
            folder_name = item['name']
            folder_id = item['id']

            # Store original folder name
            existing_folders[folder_name] = folder_id

            # Generate canonical form
            canonical = canonical_address(folder_name)
            existing_folder_variants[canonical] = folder_id

        print(f"✅ Found {len(items)} existing folders in Google Drive")
        return existing_folders, existing_folder_variants

    except Exception as e:
        print(f"❌ Error getting existing folders: {e}")
        return {}, {}


def canonical_address(address):
    """
    Convert any address format to a canonical form for comparison.
    This strips out all punctuation, spaces, and converts to lowercase.
    """
    # Remove commas, periods, underscores, hyphens, #, and /
    canonical = address.lower()
    canonical = canonical.replace(',', '').replace('.', '')
    canonical = canonical.replace('_', '').replace('-', '')
    canonical = canonical.replace('#', '').replace('/', '')
    canonical = canonical.replace(' ', '')  # Remove spaces

    # Remove common words that could be abbreviated differently
    canonical = canonical.replace('road', 'rd').replace('street', 'st')
    canonical = canonical.replace('avenue', 'ave').replace('lane', 'ln')
    canonical = canonical.replace('drive', 'dr').replace('boulevard', 'blvd')
    canonical = canonical.replace('court', 'ct').replace('place', 'pl')

    return canonical


def check_address_exists(address, existing_folders, existing_folder_variants):
    """
    Check if an address already has a folder in Google Drive.
    Returns the folder ID if it exists, None otherwise.
    """
    print(f"\n🔍 DEBUG: Checking if address exists: '{address}'")

    # Case 1: Direct match with an existing folder
    if address in existing_folders:
        print(f"✅ DEBUG: Found direct match with existing folder")
        return existing_folders[address]
    else:
        print(f"❌ DEBUG: No direct match found")

    # Case 2: Underscore format match
    address_underscore = address.replace(" ", "_").replace(",", "")
    print(f"🔄 DEBUG: Converted to underscore format: '{address_underscore}'")

    # Print first 10 existing folder names for debugging
    print(f"📂 DEBUG: First 10 existing folders:")
    counter = 0
    for folder_name in existing_folders.keys():
        if counter < 10:
            print(f"  - '{folder_name}'")
            counter += 1
        else:
            break

    if address_underscore in existing_folders:
        print(f"✅ DEBUG: Found match with underscore format")
        return existing_folders[address_underscore]
    else:
        print(f"❌ DEBUG: No underscore format match found")

    # Case 3: Check using canonical form
    canonical = canonical_address(address)
    print(f"🧩 DEBUG: Canonical form: '{canonical}'")

    # Print first 10 canonical forms for debugging
    print(f"🔤 DEBUG: First 10 canonical forms:")
    counter = 0
    for can_form in existing_folder_variants.keys():
        if counter < 10:
            print(f"  - '{can_form}'")
            counter += 1
        else:
            break

    if canonical in existing_folder_variants:
        print(f"✅ DEBUG: Found match with canonical form")
        return existing_folder_variants[canonical]
    else:
        print(f"❌ DEBUG: No canonical form match found")

    # No match found
    print(f"❗ DEBUG: No match found for address: '{address}'")
    return None


def process_missing_folder_images():
    """
    Process listings that don't have folders in Google Drive.
    This implementation gets all current listings, then checks for missing folders.
    """
    # First, get all current listings
    print("🔍 Scraping current listings to identify missing folders...")
    all_listings = scrape_listings()
    print(f"📋 Found {len(all_listings)} current listings")

    # Get existing folders in Google Drive
    existing_folders, existing_folder_variants = get_existing_drive_folders()

    # Find listings that don't have folders
    missing_folders = []
    duplicate_check = set()  # Avoid processing the same address twice

    for listing in all_listings:
        address = listing.get("address")
        if not address or address == "N/A" or address in duplicate_check:
            continue

        duplicate_check.add(address)

        # Check if this address already has a folder
        folder_id = check_address_exists(address, existing_folders, existing_folder_variants)

        if folder_id:
            print(f"🔍 Found existing folder for: {address}")
        else:
            missing_folders.append(listing)

    print(f"🔍 Found {len(missing_folders)} listings without existing folders")

    # Process only the missing folders
    processed_count = 0
    for listing in missing_folders:
        try:
            address = listing["address"]
            print(f"\n🖼️ Processing images for: {address}")

            # Get image URLs (already included in the listing data)
            image_urls = listing.get("image_urls", [])

            if not image_urls:
                print(f"⚠️ No images found for: {address}")
                continue

            print(f"📸 Found {len(image_urls)} images")

            # Create folder and upload images
            listing_folder_id = create_drive_folder(address)

            uploaded_urls = []
            for idx, img_url in enumerate(image_urls, start=1):
                url = upload_image_to_drive(img_url, listing_folder_id, address, idx)
                if url:
                    uploaded_urls.append(url)

            print(f"✅ Uploaded {len(uploaded_urls)} images for: {address}")
            processed_count += 1

            # Add a small delay between listings
            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"❌ Error processing images for {address}: {e}")

    return processed_count


def main():
    if IMAGE_ONLY_MODE:
        print("🖼️ Running in IMAGE_ONLY_MODE - processing only listings without existing folders")

        if not SKIP_IMAGE_UPLOAD:
            processed_count = process_missing_folder_images()
            print(f"✅ Processed images for {processed_count} new listings")
        else:
            print("⚠️ SKIP_IMAGE_UPLOAD is True, but running in IMAGE_ONLY_MODE - no actions performed")

    else:
        # Regular full processing flow
        listings = scrape_listings()
        processed_listings = []  # ✅ Store processed listings to prevent duplicate updates

        for listing in listings:
            # ✅ Only create a folder and upload images if SKIP_IMAGE_UPLOAD is False
            listing_folder_id = None
            if not SKIP_IMAGE_UPLOAD:
                # Get existing folders to check if this listing already has one
                existing_folders, existing_folder_variants = get_existing_drive_folders()
                folder_id = check_address_exists(listing["address"], existing_folders, existing_folder_variants)

                if folder_id:
                    # Use existing folder
                    listing_folder_id = folder_id
                    print(f"📁 Using existing folder for: {listing['address']}")
                else:
                    # Create new folder
                    listing_folder_id = create_drive_folder(listing["address"])

                # Upload images
                uploaded_images = [
                    upload_image_to_drive(img_url, listing_folder_id, listing["address"], idx)
                    for idx, img_url in enumerate(listing.get("image_urls", []), start=1)
                ]
                # Store uploaded image URLs
                listing["uploaded_images"] = uploaded_images

            # ✅ Always generate captions
            print(f"⏳ Generating caption for: {listing['address']}...")
            listing["instagram_caption"] = generate_instagram_post(
                listing["description"], listing["price"], listing["beds"],
                listing["baths"], listing["sqft"], listing["address"],
                listing.get("listing_agents"), listing.get("agent_company")
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