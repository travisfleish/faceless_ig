import openai
import time
import random
from config import OPENAI_API_KEY, USE_MOCK_OPENAI


def generate_instagram_post(description, price, beds, baths, sqft, address, listing_agents=None, agent_company=None):
    """
    Generates an Instagram caption using OpenAI or returns a mock response.
    Now includes optional listing agent attribution.
    """

    if USE_MOCK_OPENAI:
        # Agent attribution line
        agent_line = ""
        if listing_agents and agent_company:
            agent_line = f"\nListed by: {listing_agents} ({agent_company})"

        # Return a properly formatted mock response for testing
        return f"""📍 {address}
💰 {price}
🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft{agent_line}

Perched dramatically above the Potomac River, this waterfront masterpiece offers unparalleled luxury living with breathtaking panoramic views.

Step inside to discover a chef's kitchen, home theater, wine cellar, and smart home technology that controls everything from lighting to security.

Follow us for more amazing luxury homes in Bethesda that'll make your jaw drop."""

    # Extract notable features from the description for better prompting
    notable_features = extract_notable_features(description)

    # Get location for customized CTA
    location = extract_location(address)

    # Generate a custom CTA based on the location
    custom_cta = generate_custom_cta(location)

    # Create agent attribution if provided
    agent_attribution = ""
    if listing_agents and agent_company:
        agent_attribution = f"Listed by: {listing_agents} ({agent_company})"

    prompt = f"""
    You are a social media expert creating Instagram captions for luxury real estate listings. Your goal is to create content that will make people want to follow a luxury real estate Instagram page.

    FORMAT REQUIREMENTS:
    - STRICT WORD COUNT: 120-150 words maximum, not including the header
    - EXACT STRUCTURE: Exactly 4 distinct parts:
      1. Header (formatted exactly as shown below)
      2. Paragraph about the property's standout external features (1-2 sentences)
      3. Paragraph about interior features (1-2 sentences)
      4. Call-to-action paragraph (exactly 1 sentence)

    THE HEADER MUST BE FORMATTED EXACTLY LIKE THIS:
    📍 {address}
    💰 {price}
    🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft
    {"Listed by: " + listing_agents + " (" + agent_company + ")" if listing_agents and agent_company else ""}

    TONE EXAMPLES:
    ✓ "This place isn't just a house, it's basically a private resort."
    ✓ "Imagine sipping your morning coffee while watching boats sail by on the Potomac."
    ✓ "The kitchen is what cooking dreams are made of."
    ✓ "Let's be honest, the wine cellar alone is worth the price tag."
    ✗ AVOID: "This prestigious domicile offers unparalleled accommodations."
    ✗ AVOID: "A testament to architectural brilliance."

    CALL-TO-ACTION:
    End with this specific CTA: "{custom_cta}"

    CONTENT GUIDELINES:
    - Use conversational, slightly casual language
    - Focus on lifestyle benefits, not just features
    - Highlight these specific features if relevant: {notable_features}
    - Be concise - short sentences have more impact
    - Include only the most impressive 2-3 features 

    AVOID:
    - Flowery or overly formal language
    - Real estate clichés like "luxury living" or "breathtaking views"
    - Generic descriptions
    - Mentioning investment potential
    - Going over the word count limit

    Property Description:
    {description}
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system",
                     "content": "You are a luxury real estate social media expert who creates engaging, conversational captions that highlight what makes each property special without sounding pretentious."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Slightly increase creativity while maintaining consistency
                max_tokens=300  # Limit token length to enforce brevity
            )

            # Verify the response has the proper format
            caption = response.choices[0].message.content.strip()

            # Simple validation to ensure proper formatting
            if validate_caption_format(caption, address, price):
                # Check word count
                content_only = extract_content_without_header(caption)
                word_count = len(content_only.split())

                if word_count > 150:
                    time.sleep(random.uniform(1, 2))
                    continue

                return caption
            else:
                time.sleep(random.uniform(1, 2))  # Small delay before retry
                continue

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(random.uniform(2, 5))  # Exponential backoff
            else:
                # Fallback caption with agent attribution if provided
                agent_line = ""
                if listing_agents and agent_company:
                    agent_line = f"\nListed by: {listing_agents} ({agent_company})"

                return f"""📍 {address}
💰 {price}
🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft{agent_line}

This stunning property combines luxury with comfort in a prime location.

Inside you'll find high-end finishes and thoughtful design that elevates everyday living.

{custom_cta}"""


def extract_notable_features(description):
    """Extract key selling points from the property description."""
    notable_keywords = [
        "waterfront", "beachfront", "ocean view", "mountain view", "lake view", "river view", "panoramic",
        "historic", "award winning", "architect", "custom built", "newly renovated", "newly built",
        "infinity pool", "private pool", "tennis court", "wine cellar", "home theater", "gym",
        "smart home", "gated community", "chef's kitchen", "gourmet kitchen", "spa bathroom", "primary suite",
        "hardwood floors", "marble", "granite", "stainless steel", "double height", "cathedral ceiling",
        "private dock", "garage", "car enthusiast", "guest house", "outdoor kitchen", "fireplace",
        "rooftop", "balcony", "terrace", "garden", "landscaped", "acreage", "elevator", "generator",
        "security system", "home office", "library", "recreation room", "media room"
    ]

    found_features = []
    for keyword in notable_keywords:
        if keyword.lower() in description.lower():
            found_features.append(keyword)

    # Limit to top 5 features to keep prompt concise
    return ", ".join(found_features[:5]) if found_features else "luxury finishes, premium location"


def extract_location(address):
    """Extract location from address for customized CTA."""
    parts = address.split(',')
    if len(parts) >= 2:
        city_state = parts[-2].strip()
        # Try to extract just the city
        city = city_state.split()[0].strip()
        return city
    return "this area"


def generate_custom_cta(location):
    """Generate a custom call-to-action based on location."""
    cta_templates = [
        f"Follow us for more amazing luxury homes in {location} that'll make your jaw drop.",
        f"Hit follow to see more dream homes in {location} that you'll want to move into immediately.",
        f"Want to see more stunning {location} properties? Follow our page for daily luxury home inspiration.",
        f"Don't miss out on more incredible {location} estates – tap that follow button for your daily dose of luxury.",
        f"For more {location} dream homes that'll give you serious real estate envy, follow our page!",
    ]
    return random.choice(cta_templates)


def extract_content_without_header(caption):
    """Extract just the content portion of the caption without the header."""
    lines = caption.split('\n')

    # Find where the header ends and content begins
    content_start_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("🏡") or line.startswith("Listed by:"):
            content_start_idx = i + 1
            break

    # If we have a "Listed by" line after the emoji header
    if content_start_idx < len(lines) and lines[content_start_idx].startswith("Listed by:"):
        content_start_idx += 1

    # Join the content lines
    return '\n'.join(lines[content_start_idx:])


def validate_caption_format(caption, address, price):
    """Validate that the caption follows the required format."""
    try:
        lines = caption.split('\n')

        # Check minimum requirements
        if len(lines) < 4:  # Need at least the header (3-4 lines) plus 1 more paragraph
            return False

        # Check if first line contains address marker
        if not lines[0].startswith("📍"):
            return False

        # Check if second line contains price marker
        if not lines[1].startswith("💰"):
            return False

        # Check if third line contains beds/baths format
        if not lines[2].startswith("🏡") or "Beds" not in lines[2] or "Baths" not in lines[2]:
            return False

        # The fourth line might be agent attribution or the start of content
        content_start_idx = 3
        if len(lines) > 3 and lines[3].startswith("Listed by:"):
            content_start_idx = 4

        # Make sure we have content after the header
        if len(lines) <= content_start_idx:
            return False

        # Count paragraphs (empty lines separate paragraphs)
        content_paragraphs = [p for p in '\n'.join(lines[content_start_idx:]).split('\n\n') if p.strip()]
        if len(content_paragraphs) != 3:  # Should have exactly 3 paragraphs after header
            return False

        return True

    except Exception as e:
        return False  # If validation process errors out, fail safely


# When this script is run directly, test the caption generator
if __name__ == "__main__":
    # Simple test with mock data
    sample_description = "This waterfront property features 6 bedrooms, home theater, and infinity pool."
    sample_price = "$5,000,000"
    sample_beds = "6"
    sample_baths = "5"
    sample_sqft = "5,000"
    sample_address = "123 Main St, Bethesda, MD 20817"

    caption = generate_instagram_post(
        sample_description,
        sample_price,
        sample_beds,
        sample_baths,
        sample_sqft,
        sample_address,
        "John Smith",
        "Luxury Real Estate"
    )

    print("\nGENERATED CAPTION:")
    print("=" * 50)
    print(caption)
    print("=" * 50)