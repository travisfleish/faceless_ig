import time
import json
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
import re
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from io import BytesIO
import requests
import os
import mimetypes
import urllib.parse
import hashlib
from PIL import Image

# Google Drive Authentication
SERVICE_ACCOUNT_FILE = "google_sheets_credentials.json"  # Ensure this file exists
SCOPES = ["https://www.googleapis.com/auth/drive"]

def file_exists_in_drive(file_name, folder_id):
    """Check if a file already exists in Google Drive."""
    try:
        query = f"name = '{file_name}' and '{folder_id}' in parents and trashed=false"
        results = drive_service.files().list(q=query, spaces="drive", fields="files(id, webViewLink)").execute()
        files = results.get("files", [])
        if files:
            print(f"🔍 Found existing file: {file_name} → {files[0]['webViewLink']}")
            return files[0]["webViewLink"]  # Return existing file link
        return None
    except HttpError as error:
        print(f"⚠️ Error checking file existence: {error}")
        return None

def authenticate_google_drive():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

drive_service = authenticate_google_drive()

PARENT_FOLDER_ID = "1rwDDM5pC1UYYErDJ7WuspwVMhWDN5Uxl"  # Your Google Drive Folder ID

def create_drive_folder(folder_name):
    """Create a folder inside the shared Google Drive folder."""
    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [PARENT_FOLDER_ID]  # Parent folder is your personal Drive folder
    }
    folder = drive_service.files().create(body=file_metadata, fields="id").execute()
    print(f"📁 Created folder: {folder_name} (ID: {folder.get('id')}) inside {PARENT_FOLDER_ID}")
    return folder.get("id")

def upload_image_to_drive(image_url, folder_id, listing_address, index):
    """Uploads an image to Google Drive, avoiding duplicates."""
    print(f"📤 Processing image: {image_url}")

    try:
        response = requests.get(image_url, stream=True, timeout=10)
        if response.status_code == 200:
            # **Step 1: Detect the correct file extension**
            parsed_url = urllib.parse.urlparse(image_url)
            file_ext = os.path.splitext(parsed_url.path)[-1] or ".jpg"
            if len(file_ext) > 5:  # Handle missing or invalid extensions
                file_ext = mimetypes.guess_extension(response.headers.get('Content-Type', '')) or ".jpg"

            # **Step 2: Convert WebP to JPEG if needed**
            image_data = BytesIO(response.content)
            if file_ext.lower() == ".webp":
                image = Image.open(image_data).convert("RGB")
                image_data = BytesIO()
                image.save(image_data, format="JPEG", quality=95)
                file_ext = ".jpg"
                image_data.seek(0)

            # **Step 3: Generate a unique filename**
            clean_address = listing_address.replace(" ", "_").replace(",", "").replace("#", "").replace("/", "_")[:30]
            file_name = f"{clean_address}_{index}{file_ext}"

            # **Step 4: Check if file already exists**
            existing_file_link = file_exists_in_drive(file_name, folder_id)
            if existing_file_link:
                return existing_file_link  # Return existing link, no re-upload

            # **Step 5: Upload to Google Drive**
            file_metadata = {"name": file_name, "parents": [folder_id]}
            media = MediaIoBaseUpload(image_data, mimetype="image/jpeg", resumable=True)

            file = drive_service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()

            # **Step 6: Make file public**
            permission = {"type": "anyone", "role": "reader"}
            drive_service.permissions().create(fileId=file.get("id"), body=permission).execute()

            print(f"✅ Uploaded: {file_name} → {file.get('webViewLink')}")
            return file.get("webViewLink")

        else:
            print(f"❌ Failed to download image: {image_url} (Status Code: {response.status_code})")
            return None

    except Exception as e:
        print(f"⚠️ Error processing image: {image_url} → {e}")
        return None

# OpenAI API Key (Mock for Testing)
OPENAI_API_KEY = "sk-proj-XXXXXXX"
USE_MOCK_OPENAI = True  # Set to False to use real API calls

# Generate Instagram Caption (Mocked)
def generate_instagram_post(description, price, beds, baths, sqft, address):
    if USE_MOCK_OPENAI:
        return f"🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft - Test caption for {address}"

    prompt = f"""
    Create an engaging Instagram post for a luxury home listing.
    - Keep it under 200 words.
    - Include emojis, short sentences, and engaging copy.
    - Use a call-to-action like 'DM us for details!' or 'Tag someone who'd love this!'.
    - Highlight the property's unique features.

    Listing Details:
    📍 Location: {address}
    💰 Price: {price}
    🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft

    Property Description:
    {description}
    """
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a luxury real estate social media expert."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Save to Google Sheets
def save_to_google_sheets(data, sheet_name="Real_Estate_Faceless"):
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_sheets_credentials.json",
                                                             ["https://spreadsheets.google.com/feeds",
                                                              "https://www.googleapis.com/auth/drive"])
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1

    formatted_data = []
    headers = ["listing_url", "price", "address", "beds", "baths", "sqft", "description", "video_url",
               "instagram_account", "instagram_caption"] + [f"image_{i + 1}" for i in range(10)]
    formatted_data.append(headers)

    for listing in data:
        row = [
            listing.get("listing_url", "N/A"),
            listing.get("price", "N/A"),
            listing.get("address", "N/A"),
            listing.get("beds", "N/A"),
            listing.get("baths", "N/A"),
            listing.get("sqft", "N/A"),
            listing.get("description", "N/A"),
            listing.get("video_url", "N/A"),
            listing.get("instagram_account", "N/A"),
            listing.get("instagram_caption", "N/A"),
        ]

        # Append first 10 images (if available)
        images = listing.get("image_urls", [])[:10]
        images += [""] * (10 - len(images))  # Fill remaining slots with empty strings
        row.extend(images)

        formatted_data.append(row)

    sheet.clear()
    sheet.update(formatted_data)
    print("Data successfully stored in Google Sheets.")

# Configure Selenium
chrome_options = Options()
# chrome_options.add_argument("--headless=new")  # Runs Chrome in headless mode for better efficiency
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--dns-prefetch-disable")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
        )

# Compass URL
compass_url = "https://www.compass.com/homes-for-sale/montgomery-county-md/sort=desc-price/start=41/"

# Open Compass Listing Page
driver.get(compass_url)
time.sleep(random.uniform(3, 6))  # Let page load

scraped_urls = set()
data = []

# **Loop through first 2 pages**
for page in range(2):
    print(f"\nScraping Page {page + 1}...")

    # Scroll within the listings container
    listings_container = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".sc-mrags4.kgcPsu"))  # Adjust class if needed
    )

    for _ in range(20):  # Adjust scrolling depth
        driver.execute_script("arguments[0].scrollTop += 500;", listings_container)
        time.sleep(1.5)

    # Extract listings on the current page
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    listings = soup.find_all("div", class_="uc-listingCard")
    print(f"Total listings found: {len(listings)}")


    # Loop through each listing
    for listing in listings:
        link_tag = listing.find("a", href=True)
        listing_url = f"https://www.compass.com{link_tag['href']}" if link_tag else None

        if not listing_url or "/private-exclusives/" in listing_url or listing_url in scraped_urls:
            continue

        print(f"Scraping: {listing_url}")
        scraped_urls.add(listing_url)

        driver.get(listing_url)
        time.sleep(random.uniform(3, 6))

        listing_soup = BeautifulSoup(driver.page_source, 'html.parser')

        price, beds, baths, sqft, address = "N/A", "N/A", "N/A", "N/A", "N/A"
        description = "N/A"

        remarks_section = listing_soup.find("div", {"data-tn": "uc-listing-description"})
        if remarks_section:
            spans = remarks_section.find_all("span")
            description = " ".join([span.text.strip() for span in spans if span.text.strip()])

        meta_description = listing_soup.find("meta", {"name": "description"})
        if meta_description:
            content = meta_description["content"]

            address_match = re.search(r"^(.*?)(?: is a single family home| is a townhome)", content)
            if address_match:
                address = address_match.group(1)

            price_match = re.search(r"listed for sale at (\$\d{1,3}(?:,\d{3})*)", content)
            beds_match = re.search(r"(\d+)-bed", content)
            baths_match = re.search(r"(\d+)-bath", content)
            sqft_match = re.search(r"(\d{1,3}(?:,\d{3})*) sqft", content)

            if price_match:
                price = price_match.group(1)
            if beds_match:
                beds = beds_match.group(1)
            if baths_match:
                baths = baths_match.group(1)
            if sqft_match:
                sqft = sqft_match.group(1)

        county_match = re.search(r"homes-for-sale/([a-zA-Z-]+)-md", compass_url)
        county_name = county_match.group(1).replace("-", " ").title() if county_match else "Unknown County"

        image_urls = []
        hero_image = listing_soup.find("img", id="media-gallery-hero-image")
        if hero_image and hero_image.get("src"):
            image_urls.append(hero_image["src"])

        carousel_images = listing_soup.select("img[data-flickity-lazyload-src]")
        for img in carousel_images:
            if img.get("data-flickity-lazyload-src"):
                image_urls.append(img["data-flickity-lazyload-src"])

        image_urls = list(dict.fromkeys(image_urls))
        print(f"Extracted {len(image_urls)} images.")

        ### **🔥 Google Drive Integration Starts Here 🔥 ###

        # ✅ Step 1: Create a folder for this listing inside the shared Google Drive folder
        listing_folder_name = address.replace(" ", "_").replace(",", "").replace("#", "").replace("/", "_")[
                              :50]  # Clean address for folder name
        listing_folder_id = create_drive_folder(listing_folder_name)

        # ✅ Step 2: Upload images into the newly created Google Drive folder
        drive_image_links = [
            upload_image_to_drive(img_url, listing_folder_id, address, index)
            for index, img_url in enumerate(image_urls, start=1)
        ]

        data.append({
            "listing_url": listing_url,
            "price": price,
            "address": address,
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "description": description,
            "video_url": "N/A",
            "instagram_account": f"Most Expensive Homes in {county_name}",
            "instagram_caption": generate_instagram_post(description, price, beds, baths, sqft, address),
            "image_urls": drive_image_links
        })

    # Click next page button
    try:
        next_button = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Next Page')]")
        driver.execute_script("arguments[0].click();", next_button)
        time.sleep(3)
    except:
        print("No more pages found.")
        break

# Close WebDriver
driver.quit()
save_to_google_sheets(data)
print("Scraped full details and saved to Google Sheets.")
