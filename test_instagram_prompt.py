import openai
from config import OPENAI_API_KEY, USE_MOCK_OPENAI  # ✅ Ensure these are in config.py

def generate_instagram_post(description, price, beds, baths, sqft, address):
    """Generates an Instagram caption using OpenAI or returns a mock response."""

    if USE_MOCK_OPENAI:  # ✅ Use mock mode if enabled
        return f"🏡 {beds} Beds | 🛁 {baths} Baths | 📏 {sqft} Sq Ft - Test caption for {address}"

    # ✅ **Modify this prompt to test different versions**
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


# ✅ **Modify this sample listing to test different prompts**
sample_listing = {
    "address": "9010 Congressional Parkway, Potomac, MD 20854",
    "price": "$9,995,000",
    "beds": "7",
    "baths": "9",
    "sqft": "15,410",
    "description": "Gracefully sprawling across 4.56 manicured acres in Potomac’s coveted Golden Horseshoe, 9010 Congressional Parkway is one of the region’s premier estates. The residence embodies East Coast timelessness, blending the grandeur of expansive country manors with the tranquility of coastal retreats—all crafted to the highest finish level in the luxury space. Originally designed by the esteemed architectural firm Versaci Neumann and painstakingly transformed by its current owners, the home underwent an Gracefully sprawling across 4.56 manicured acres in Potomac’s coveted Golden Horseshoe, 9010 Congressional Parkway is one of the region’s premier estates. The residence embodies East Coast timelessness, blending the grandeur of expansive country manors with the tranquility of coastal retreats—all crafted to the highest finish level in the luxury space. Originally designed by the esteemed architectural firm Versaci Neumann and painstakingly transformed by its current owners, the home underwent an exquisite restoration that introduced unique, imported finishes and bespoke elements from around the world, elevating its stature to new heights of luxury. As you arrive, automatic gates part to reveal a meandering, newly laid driveway leading to a central motor court lined with pavers. The estate’s architectural significance is immediately apparent, with symmetry-driven design complemented by lush, tailored plantings. Federalist-style double doors open to a grand rotunda, introducing a gracious floor plan spanning 15,451 square feet of sophisticated living space. Formal rooms radiate from the grand foyer. The living room extends 34 feet, anchored by a roaring fireplace and lighted, molded built-ins shimmering against lacquered walls and ceilings. A marble wet bar with smoked mirrors connects to the custom-paneled sitting room, which opens to gardens via French doors. The informal areas carry a coastal flair, starting with the chef’s kitchen, where soaring beamed and shiplap cathedral ceilings frame the space and whimsical antique theater lights imported from Paris are a show-stopper above the oversized center island. Redundant commercial-grade appliances are nestled within furniture-grade inset cabinetry and waterfall countertops. The adjacent family room features a mirrored ceiling design, masonry fireplace, and chair rail moldings that complement built-ins, creating an intimate yet expansive atmosphere. The solarium and garden cutting room dazzles with inlaid marble floors, built-in planters, and intricate latticework, seamlessly connecting to the outdoors, storage areas, and mudroom. On the opposite end of the main level, the private primary retreat boasts soaring ceilings, a gas fireplace, and a sitting room with direct outdoor access. The marble-clad ensuite rivals world-class resorts and is paired with two dressing rooms, each with a center island. Directly connected to the suite is a spectacular game room with cathedral-beamed ceilings, a masonry fireplace and custom paneling, leading to a fitness center that opens to an outdoor terrace with a spa and shower. The second floor features four spacious bedrooms and three baths surrounding the rotunda. A third-floor suite enhances versatility, while a separate apartment above the four-car garage offers additional accommodations. The lower level centers on entertainment, with a large recreation room, wet bar, and private cinema professionally designed with tiered seating and high-end equipment for an unparalleled viewing experience. Outside, the estate’s meticulously maintained grounds draw inspiration from grand European properties, blending hardscaping with exquisite landscaping. Features include a koi pond, trickling fountain, vegetable gardens, and four separate sheds, creating a serene, natural oasis. Supported by industrial-grade systems rarely seen in a residential setting, the estate is a fortress of luxury. Conveniently close to Washington yet offering complete seclusion, 9010 Congressional Parkway stands as a globally distinguished estate, embodying impeccable craftsmanship and timeless elegance."
}

# ✅ **Run the test**
print("\n🔹 Testing Instagram Caption Generation...\n")
generated_caption = generate_instagram_post(
    sample_listing["description"],
    sample_listing["price"],
    sample_listing["beds"],
    sample_listing["baths"],
    sample_listing["sqft"],
    sample_listing["address"]
)

print(f"📝 **Generated Caption:**\n{generated_caption}")
