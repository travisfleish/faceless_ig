import time
import random
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from config import COMPASS_URL, SKIP_IMAGE_UPLOAD
from drive_uploader import create_drive_folder, upload_image_to_drive
from instagram_captions import generate_instagram_post
from google_sheets import save_to_google_sheets  # ✅ Now includes Google Sheets

def start_driver():
    """Starts a headless Selenium WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Runs Chrome in headless mode
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

    return driver

def test_scrape_and_upload_to_sheets():
    """Scrapes and uploads only one listing to Google Sheets for testing."""
    driver = start_driver()
    driver.get(COMPASS_URL)
    time.sleep(random.uniform(3, 6))  # Let page load

    print("\n🔍 Finding first listing...")

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    listing = soup.find("div", class_="uc-listingCard")

    if not listing:
        print("❌ No listings found.")
        driver.quit()
        return

    link_tag = listing.find("a", href=True)
    listing_url = f"https://www.compass.com{link_tag['href']}" if link_tag else None

    if not listing_url:
        print("❌ Could not extract listing URL.")
        driver.quit()
        return

    print(f"✅ Scraping: {listing_url}")

    driver.get(listing_url)
    time.sleep(random.uniform(3, 6))

    listing_soup = BeautifulSoup(driver.page_source, 'html.parser')

    price, beds, baths, sqft, address, description = "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"

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

    # ✅ Only create a folder & upload images **if SKIP_IMAGE_UPLOAD is False**
    listing_folder_id = None
    if not SKIP_IMAGE_UPLOAD:
        listing_folder_id = create_drive_folder(address)

    image_urls = []
    hero_image = listing_soup.find("img", id="media-gallery-hero-image")
    if hero_image and hero_image.get("src"):
        image_urls.append(hero_image["src"])

    carousel_images = listing_soup.select("img[data-flickity-lazyload-src]")
    for img in carousel_images:
        if img.get("data-flickity-lazyload-src"):
            image_urls.append(img["data-flickity-lazyload-src"])

    drive_image_links = []
    if not SKIP_IMAGE_UPLOAD:
        drive_image_links = [
            upload_image_to_drive(img_url, listing_folder_id, address, idx)
            for idx, img_url in enumerate(image_urls, start=1)
        ]

    instagram_caption = generate_instagram_post(description, price, beds, baths, sqft, address)
    instagram_account = f"Most Expensive Homes in {address.split()[-1]}"

    # ✅ Print extracted data before saving
    print("\n📄 **Extracted Listing Details:**")
    print(f"🔹 URL: {listing_url}")
    print(f"🏡 Address: {address}")
    print(f"💰 Price: {price}")
    print(f"🛏 Beds: {beds} | 🛁 Baths: {baths} | 📏 Sqft: {sqft}")
    print(f"📜 Description: {description[:200]}...")  # Truncate for readability
    print(f"📸 Instagram Account: {instagram_account}")
    print(f"📝 Instagram Caption: {instagram_caption}")

    # ✅ Upload to Google Sheets
    listing_data = [{
        "listing_url": listing_url,
        "price": price,
        "address": address,
        "beds": beds,
        "baths": baths,
        "sqft": sqft,
        "description": description,
        "instagram_account": instagram_account,
        "instagram_caption": instagram_caption
    }]

    print("\n📤 Uploading to Google Sheets...")
    save_to_google_sheets(listing_data)
    print("✅ Successfully uploaded one listing to Google Sheets!")

    driver.quit()

# ✅ Run the test
if __name__ == "__main__":
    test_scrape_and_upload_to_sheets()
