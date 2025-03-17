import openai
from config import OPENAI_API_KEY, USE_MOCK_OPENAI  # ✅ Now controlled via config.py

def generate_instagram_post(description, price, beds, baths, sqft, address):
    """Generates an Instagram caption using OpenAI or returns a mock response."""

    if USE_MOCK_OPENAI:  # ✅ Now controlled by config.py
        return f"🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft - Test caption for {address}"

    prompt = f"""
    You are a social media expert creating engaging Instagram captions for luxury real estate listings. The goal for this page isn't to sell homes, but to promote fancy listings to entice people to follow the page.
    - Keep it under 200 words. 
    - Make it four separate paragraphs
    - The opening should be structured exactly like the listing details below. Make sure it is three separate lines like belwow:
    "📍 Location: {address}
    💰 Price: {price}
    🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft"
    - The caption should highlight the property's best features in an exciting way.
    - Have the final paragraph be a one sentence, brief, direct call-to-action to follow the page to see more luxury listings. 
    - The tone should be a little less pretentious. Make it somewhat self aware that this is a promotional page. Use less fancy language.

    🔹 **Listing Details**:
    📍 Location: {address}
    💰 Price: {price}
    🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft

    🔹 **Property Description**:
    {description}
    """

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a luxury real estate social media expert."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()
