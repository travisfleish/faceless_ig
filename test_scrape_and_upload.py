import time
import random
import re
from bs4 import BeautifulSoup, Comment
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from drive_uploader import create_drive_folder, upload_image_to_drive
from instagram_captions import generate_instagram_post
from google_sheets import save_to_google_sheets


def start_driver():
    """Starts a headless Selenium WebDriver."""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Runs Chrome in headless mode
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--dns-prefetch-disable")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        # Add additional options to make scraping more robust
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-dev-shm-usage")

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
    except WebDriverException as e:
        print(f"❌ Error initializing WebDriver: {e}")
        raise


def wait_for_page_load(driver, timeout=10):
    """Wait for the page to fully load with a timeout."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except TimeoutException:
        print("⚠️ Page load timeout - continuing anyway")
        return False


def extract_listing_data(driver, listing_soup, listing_url):
    """Extract listing data from the BeautifulSoup object."""
    try:
        price, beds, baths, sqft, address, description = "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"

        # Extract description
        remarks_section = listing_soup.find("div", {"data-tn": "uc-listing-description"})
        if remarks_section:
            spans = remarks_section.find_all("span")
            description = " ".join([span.text.strip() for span in spans if span.text.strip()])

        # Extract metadata
        meta_description = listing_soup.find("meta", {"name": "description"})
        if meta_description and "content" in meta_description.attrs:
            content = meta_description["content"]

            # Extract address
            address_match = re.search(r"^(.*?)(?: is a single family home| is a townhome)", content)
            if address_match:
                address = address_match.group(1)

            # Extract price, beds, baths, sqft
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

        # Extract agents and companies
        agent_names, agent_companies = extract_agents(driver, listing_soup)

        # Format agent information
        listing_agents = "; ".join(agent_names)
        agent_company = "; ".join(agent_companies)

        # Extract county name from the listing URL
        county_match = re.search(r"homes-for-sale/([a-zA-Z-]+)-md", listing_url)
        county_name = county_match.group(1).replace("-", " ").title() if county_match else "Unknown County"

        # Set Instagram account name
        instagram_account = f"Most Expensive Homes in {county_name}"

        # Generate Instagram caption
        instagram_caption = generate_instagram_post(description, price, beds, baths, sqft, address)

        return {
            "listing_url": listing_url,
            "price": price,
            "address": address,
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "description": description,
            "instagram_account": instagram_account,
            "instagram_caption": instagram_caption,
            "listing_agents": listing_agents,
            "agent_company": agent_company,
            "county": county_name
        }
    except Exception as e:
        print(f"❌ Error extracting listing data: {e}")
        # Return partial data if possible
        return {
            "listing_url": listing_url,
            "price": price if 'price' in locals() else "Error",
            "address": address if 'address' in locals() else "Error",
            "beds": beds if 'beds' in locals() else "Error",
            "baths": baths if 'baths' in locals() else "Error",
            "sqft": sqft if 'sqft' in locals() else "Error",
            "description": description if 'description' in locals() else "Error",
            "instagram_account": "Error",
            "instagram_caption": "Error",
            "listing_agents": "Error",
            "agent_company": "Error",
            "county": "Error"
        }


def extract_non_compass_agents(listing_soup):
    """Extract non-Compass agent information with better company name handling."""
    agents = []
    companies = []

    try:
        # Look for the container with non-Compass agents
        containers = listing_soup.select(
            "li[data-tn='listing-page-listed-by-agents'], div.non-compass-contact-agent-slat__StyledSlatContainer-sc-10f1rjd-0")

        for container in containers:
            container_text = container.get_text(strip=True)
            print(f"🔍 Found non-Compass container: {container_text}")

            # First try to extract the agent name and raw company part
            agent_name = None
            company_name = None

            # Try different patterns to extract agent and raw company
            patterns = [
                r"Listed by\s*\|\s*(.*?)\s*•\s*(.*?)(?=\s*\||\s*P:|\s*Phone:|\s*$)",  # "Listed by | Agent • Company"
                r"([^•·|]+)(?:•|·)\s*(.*?)(?=\s*\||\s*P:|\s*Phone:|\s*$)",  # "Agent • Company" or "Agent · Company"
            ]

            for pattern in patterns:
                match = re.search(pattern, container_text)
                if match:
                    agent_name = match.group(1).strip()
                    company_name = match.group(2).strip()

                    # Clean up "Listed by" if present
                    if "Listed by" in agent_name:
                        agent_name = agent_name.replace("Listed by", "").strip()

                    # Remove any remaining non-alphanumeric characters at the end of company name
                    company_name = re.sub(r'[^\w\s&\'-]+$', '', company_name).strip()

                    break

            if agent_name and company_name:
                agents.append(agent_name)
                companies.append(company_name)
                print(f"✅ Extracted: Agent = '{agent_name}', Company = '{company_name}'")

    except Exception as e:
        print(f"❌ Error extracting non-Compass agents: {e}")

    return agents, companies


def extract_agents(driver, listing_soup):
    """Extract agent information from the listing."""
    agent_names = []
    agent_companies = []

    try:
        # Method 1: Extract Compass agents using original selectors
        compass_agents = listing_soup.select("a[data-tn='contactAgent-link-name']")
        compass_companies = listing_soup.select("p.textIntent-caption1")

        for agent, company in zip(compass_agents, compass_companies):
            agent_name = agent.get_text(strip=True)
            agent_company = company.get_text(strip=True).replace("Listed By ", "").strip()

            if agent_name and not any(name == agent_name for name in agent_names):
                agent_names.append(agent_name)
                agent_companies.append(agent_company)

        print(f"✅ Found {len(agent_names)} Compass agents using method 1")

        # Method 2: Extract non-Compass agents using our improved function
        non_compass_names, non_compass_companies = extract_non_compass_agents(listing_soup)

        # Add non-duplicate non-Compass agents
        for name, company in zip(non_compass_names, non_compass_companies):
            if name and not any(existing == name for existing in agent_names):
                agent_names.append(name)
                agent_companies.append(company)
                print(f"✅ Added non-Compass agent: {name} ({company})")

        # Fallback Method 3: If no agents found, try direct HTML inspection for specific patterns
        if not agent_names:
            print("⚠️ No agents found with standard methods, trying fallback...")

            # Try a different approach by looking at the raw HTML
            html = driver.page_source

            # Look for specific agent patterns in the HTML
            agent_patterns = [
                r"Listed by\s*\|\s*(.*?)\s*•\s*(.*?)(?=\s*\||\s*P:|\s*Phone:|\s*$)",  # "Listed by | Agent • Company"
                r"([^•·|]+)(?:•|·)\s*(.*?)(?=\s*\||\s*P:|\s*Phone:|\s*$)",  # "Agent • Company" or "Agent · Company"
            ]

            for pattern in agent_patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        agent = match[0].strip()
                        company = match[1].strip()

                        # Clean up "Listed by" if present
                        if "Listed by" in agent:
                            agent = agent.replace("Listed by", "").strip()

                        if agent and not any(existing == agent for existing in agent_names):
                            agent_names.append(agent)
                            agent_companies.append(company)
                            print(f"✅ Fallback extracted: Agent = '{agent}', Company = '{company}'")

        # Debug: Print what we found
        print(f"📊 Total agents found: {len(agent_names)}")
        for i, (name, company) in enumerate(zip(agent_names, agent_companies)):
            print(f"  {i + 1}. {name} ({company})")

        return agent_names, agent_companies

    except Exception as e:
        print(f"❌ Error in extract_agents: {e}")
        return agent_names, agent_companies  # Return whatever we found before the error


def scrape_listing(listing_url):
    """Scrape a single listing and return the data."""
    print(f"🔍 Scraping: {listing_url}")
    driver = None

    try:
        driver = start_driver()
        driver.get(listing_url)

        # Wait for page to load
        wait_for_page_load(driver)

        # Add a random delay to mimic human behavior
        time.sleep(random.uniform(2, 4))

        # Try to locate agent section and scroll to it to ensure it's loaded
        try:
            agent_sections = driver.find_elements(By.CSS_SELECTOR,
                                                  "[data-tn*='agent'], .agent-card, div[class*='Agent'], div[class*='agent'], [data-tn='listing-page-listed-by-agents']")
            if agent_sections:
                driver.execute_script("arguments[0].scrollIntoView(true);", agent_sections[0])
                time.sleep(1)  # Give it a moment to load after scrolling
        except Exception as e:
            print(f"⚠️ Could not scroll to agent section: {e}")

        # Get page source AFTER scrolling to ensure everything is loaded
        page_source = driver.page_source
        listing_soup = BeautifulSoup(page_source, 'html.parser')

        # Extract data
        listing_data = extract_listing_data(driver, listing_soup, listing_url)

        # Print extracted data for debugging
        print_listing_data(listing_data)

        return listing_data

    except Exception as e:
        print(f"❌ Error scraping listing {listing_url}: {e}")
        return {
            "listing_url": listing_url,
            "error": str(e)
        }
    finally:
        if driver:
            driver.quit()


def print_listing_data(listing_data):
    """Print the extracted listing data in a readable format."""
    print("\n📄 **Extracted Listing Details:**")
    print(f"🔹 URL: {listing_data.get('listing_url', 'N/A')}")
    print(f"🏡 Address: {listing_data.get('address', 'N/A')}")
    print(f"💰 Price: {listing_data.get('price', 'N/A')}")
    print(
        f"🛏 Beds: {listing_data.get('beds', 'N/A')} | 🛁 Baths: {listing_data.get('baths', 'N/A')} | 📏 Sqft: {listing_data.get('sqft', 'N/A')}")

    description = listing_data.get('description', 'N/A')
    if description != 'N/A':
        print(f"📜 Description: {description[:200]}...")  # Truncate for readability
    else:
        print(f"📜 Description: N/A")

    print(f"📸 Instagram Account: {listing_data.get('instagram_account', 'N/A')}")
    print(f"📝 Instagram Caption: {listing_data.get('instagram_caption', 'N/A')[:100]}...")  # Truncate for readability
    print(f"👤 Listing Agents: {listing_data.get('listing_agents', 'N/A')}")
    print(f"🏢 Agent Companies: {listing_data.get('agent_company', 'N/A')}")


def test_scrape_and_upload_to_sheets():
    """Scrapes and uploads a single listing to Google Sheets for testing."""
    try:
        # Hardcoded URL for testing a Non-Compass agent listing
        listing_url = "https://www.compass.com/listing/6699-macarthur-boulevard-bethesda-md-20816/1582777788926023321/"

        # Scrape the listing
        listing_data = scrape_listing(listing_url)

        if listing_data:
            # Upload to Google Sheets
            print("\n📤 Uploading to Google Sheets...")
            save_to_google_sheets([listing_data])
            print("✅ Successfully uploaded one listing to Google Sheets!")
        else:
            print("❌ Failed to scrape listing data")

    except Exception as e:
        print(f"❌ Error in test_scrape_and_upload_to_sheets: {e}")


# Function to scrape multiple listings
def scrape_multiple_listings(listing_urls):
    """Scrape multiple listings and upload to Google Sheets."""
    all_listings_data = []

    for url in listing_urls:
        try:
            listing_data = scrape_listing(url)
            if listing_data:
                all_listings_data.append(listing_data)

            # Add a random delay between requests to avoid detection
            time.sleep(random.uniform(5, 10))

        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")

    if all_listings_data:
        print(f"\n📊 Scraped {len(all_listings_data)} listings successfully")
        print("\n📤 Uploading to Google Sheets...")
        save_to_google_sheets(all_listings_data)
        print("✅ Successfully uploaded all listings to Google Sheets!")
    else:
        print("❌ No listings were successfully scraped")


# Run the test
if __name__ == "__main__":
    test_scrape_and_upload_to_sheets()

    # Uncomment to test multiple listings
    listing_urls = [
        "https://www.compass.com/listing/6699-macarthur-boulevard-bethesda-md-20816/1582777788926023321/",
        "https://www.compass.com/listing/11900-river-road-potomac-md-20854/1572526240814555385/"
    ]
    scrape_multiple_listings(listing_urls)