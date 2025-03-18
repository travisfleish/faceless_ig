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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from config import COMPASS_URL
from drive_uploader import create_drive_folder, upload_image_to_drive
from instagram_captions import generate_instagram_post
from config import SKIP_IMAGE_UPLOAD


def start_driver():
    """Starts a headless Selenium WebDriver."""
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
                r"Listed by\s+(.*?)\s*·\s*(.*?)(?=\s*\||\s*P:|\s*Phone:|\s*$)",  # "Listed by Agent · Company"
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
    """Extract both Compass and non-Compass agent information."""
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

        print(f"✅ Found {len(agent_names)} Compass agents")

        # Method 2: Extract non-Compass agents using our improved function
        non_compass_names, non_compass_companies = extract_non_compass_agents(listing_soup)

        # Add non-duplicate non-Compass agents
        for name, company in zip(non_compass_names, non_compass_companies):
            if name and not any(existing == name for existing in agent_names):
                agent_names.append(name)
                agent_companies.append(company)
                print(f"✅ Added non-Compass agent: {name} ({company})")

        # Fallback Method 3: Try the old implementation if no non-Compass agents were found
        if not non_compass_names:
            non_compass_agents = listing_soup.find_all("div", string=re.compile(r"Listed by"))
            for agent_block in non_compass_agents:
                agent_text = agent_block.get_text(strip=True)
                match = re.search(r"Listed by (.+?) · (.+)", agent_text)
                if match:
                    agent_name, company_name = match.groups()

                    # Clean company name to remove contact info
                    company_name = re.sub(r'\s*\|.*$', '', company_name).strip()

                    if agent_name and not any(existing == agent_name.strip() for existing in agent_names):
                        agent_names.append(agent_name.strip())
                        agent_companies.append(company_name)
                        print(f"✅ Old method found agent: {agent_name.strip()} ({company_name})")

        return agent_names, agent_companies

    except Exception as e:
        print(f"❌ Error in extract_agents: {e}")
        return agent_names, agent_companies  # Return whatever we found before the error


def extract_county_from_url(listing_url, address):
    """Extract county name from the listing URL or address with improved accuracy."""
    # Default value
    county_name = "Unknown County"

    try:
        # Try multiple patterns to find county in the URL
        county_patterns = [
            r"homes-for-sale/([a-zA-Z-]+)-md",  # Standard pattern
            r"/listing/\d+-[a-zA-Z-]+-([a-zA-Z-]+)-md",  # Extract from listing path
        ]

        for pattern in county_patterns:
            county_match = re.search(pattern, listing_url)
            if county_match:
                extracted_county = county_match.group(1).replace("-", " ").title()
                if extracted_county and extracted_county != "Md":
                    county_name = f"{extracted_county} County"
                    break

        # Check for specific cities in the URL that indicate Montgomery County
        montgomery_locations = ["bethesda", "potomac", "chevy-chase", "rockville", "gaithersburg", "silver-spring"]
        for location in montgomery_locations:
            if location in listing_url.lower():
                county_name = "Montgomery County"
                break

        # If still unknown, check the address for city names
        if county_name == "Unknown County" and address != "N/A":
            cities_to_counties = {
                "Bethesda": "Montgomery County",
                "Potomac": "Montgomery County",
                "Chevy Chase": "Montgomery County",
                "Silver Spring": "Montgomery County",
                "Rockville": "Montgomery County",
                "Gaithersburg": "Montgomery County",
                "Kensington": "Montgomery County"
            }

            for city, county in cities_to_counties.items():
                if city in address:
                    county_name = county
                    break

        print(f"📍 Extracted county: {county_name} from {listing_url}")
        return county_name

    except Exception as e:
        print(f"❌ Error extracting county: {e}")
        return county_name


def scrape_listings():
    """Scrapes the first page of real estate listings from Compass and uploads images if enabled."""
    driver = start_driver()
    driver.get(COMPASS_URL)
    time.sleep(random.uniform(3, 6))

    scraped_urls = set()
    listings_data = []

    print("\nScraping Page 1...")

    try:
        listings_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".sc-mrags4.kgcPsu"))
        )

        for _ in range(20):  # Scroll within the listings container
            driver.execute_script("arguments[0].scrollTop += 500;", listings_container)
            time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        listings = soup.find_all("div", class_="uc-listingCard")
        print(f"Total listings found: {len(listings)}")

        for listing in listings:
            link_tag = listing.find("a", href=True)
            listing_url = f"https://www.compass.com{link_tag['href']}" if link_tag else None

            if not listing_url or "/private-exclusives/" in listing_url or listing_url in scraped_urls:
                continue

            print(f"Scraping: {listing_url}")
            scraped_urls.add(listing_url)

            driver.get(listing_url)
            time.sleep(random.uniform(3, 6))

            # Wait for page to load
            wait_for_page_load(driver)

            # Try to locate agent section and scroll to it to ensure it's loaded
            try:
                agent_sections = driver.find_elements(By.CSS_SELECTOR,
                                                      "[data-tn*='agent'], .agent-card, div[class*='Agent'], div[class*='agent'], [data-tn='listing-page-listed-by-agents']")
                if agent_sections:
                    driver.execute_script("arguments[0].scrollIntoView(true);", agent_sections[0])
                    time.sleep(1)  # Give it a moment to load after scrolling
            except Exception as e:
                print(f"⚠️ Could not scroll to agent section: {e}")

            listing_soup = BeautifulSoup(driver.page_source, 'html.parser')

            # ✅ Extract Basic Listing Details
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

            # ✅ Extract Listing Agents (Compass & Non-Compass) using the improved method
            agent_names, agent_companies = extract_agents(driver, listing_soup)

            # ✅ Store agent names and companies separately
            listing_agents = "; ".join(agent_names)  # ✅ Separate multiple agents with ";"
            agent_company = "; ".join(agent_companies)  # ✅ Separate multiple companies with ";"

            print(f"✅ Extracted Agents: {listing_agents}")
            print(f"✅ Extracted Companies: {agent_company}")

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

            # ✅ Extract county name with the improved method
            county_name = extract_county_from_url(listing_url, address)

            # ✅ Set Instagram account name as "Most Expensive Homes in {County Name}"
            instagram_account = f"Most Expensive Homes in {county_name}"

            # Generate Instagram caption
            instagram_caption = generate_instagram_post(description, price, beds, baths, sqft, address)

            # ✅ Append Listing Data
            listings_data.append({
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
                "county": county_name.replace(" County", "")  # Store county name without "County" suffix
            })

    except Exception as e:
        print(f"❌ Error during scraping: {e}")

    finally:
        driver.quit()

    return listings_data