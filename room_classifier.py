import os
import base64
import requests
from PIL import Image
import io
from config import OPENAI_API_KEY


def classify_real_estate_images_with_openai(image_paths_or_urls, max_batch_size=5):
    """
    Classify real estate images using OpenAI's GPT-4 Vision API.

    Args:
        image_paths_or_urls: List of either local file paths or URLs
        max_batch_size: Maximum number of images to process in one API call

    Returns:
        dict: Dictionary of categorized images
    """
    categories = {
        "exterior": [],  # Outside views, facade
        "living_room": [],  # Living room, family room
        "kitchen": [],  # Kitchen and dining areas
        "primary_bedroom": [],  # Master/primary bedroom
        "bathroom": [],  # Bathrooms
        "other_bedroom": [],  # Other bedrooms
        "special_feature": [],  # Pool, theater, gym, etc.
        "view": [],  # Views from property
        "outdoor_space": [],  # Deck, patio, backyard
        "other": []  # Anything else
    }

    # Process images in batches to avoid exceeding token limits
    for i in range(0, len(image_paths_or_urls), max_batch_size):
        batch = image_paths_or_urls[i:i + max_batch_size]
        batch_results = process_image_batch_with_openai(batch)

        for img_path, category in batch_results.items():
            if category in categories:
                categories[category].append(img_path)
            else:
                categories["other"].append(img_path)

    return categories


def process_image_batch_with_openai(image_paths_or_urls):
    """
    Process a batch of images using OpenAI's API

    Args:
        image_paths_or_urls: List of image paths or URLs

    Returns:
        dict: Mapping from image path to category
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    # Prepare messages for API
    messages = [
        {
            "role": "system",
            "content": """You are a real estate image classifier that identifies the type of room or feature 
            shown in each property image. For each image, respond with exactly one word from this list:

            exterior: Outside of house, facade, front/back of house
            living_room: Living room, family room, or great room
            kitchen: Kitchen or dining areas
            primary_bedroom: Master/primary bedroom
            bathroom: Any bathroom
            other_bedroom: Bedrooms that aren't the primary/master
            special_feature: Home theater, gym, wine cellar, office, etc.
            view: Views from the property (mountains, ocean, etc.)
            outdoor_space: Patios, decks, pool, garden, yard
            other: Anything that doesn't fit the above categories

            Respond ONLY with the category name, no other text."""
        }
    ]

    # Add each image to the message content
    for img_path_or_url in image_paths_or_urls:
        if img_path_or_url.startswith(('http://', 'https://')):
            # It's a URL
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "What category does this real estate photo belong to?"},
                    {"type": "image_url", "image_url": {"url": img_path_or_url}}
                ]
            })
        else:
            # It's a local file path
            with open(img_path_or_url, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What category does this real estate photo belong to?"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                })

    # Make the API request
    try:
        payload = {
            "model": "gpt-4-vision-preview",
            "messages": messages,
            "max_tokens": 300
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response_data = response.json()

        if "choices" not in response_data:
            print(f"API Error: {response_data}")
            return {}

        # Extract categories from response
        results = {}
        for i, img_path in enumerate(image_paths_or_urls):
            try:
                # Each response should be just the category name
                category = response_data["choices"][i]["message"]["content"].strip().lower()
                results[img_path] = category
            except (KeyError, IndexError):
                # If there's an error parsing the response, default to "other"
                results[img_path] = "other"

        return results

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return {img_path: "other" for img_path in image_paths_or_urls}


# Function to handle image resizing for API
def resize_image_for_api(image_path, max_size=800):
    """Resize image to a reasonable size for API processing."""
    img = Image.open(image_path)
    width, height = img.size

    if width > max_size or height > max_size:
        ratio = max(width, height) / max_size
        new_width = int(width / ratio)
        new_height = int(height / ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)

        # Save resized image to a temp file
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        buffer.seek(0)
        return buffer

    return image_path


# Example usage:
def test_openai_classifier(image_paths_or_urls):
    """Test the OpenAI-based classifier with a set of images."""
    print(f"Testing OpenAI classifier with {len(image_paths_or_urls)} images...")

    # Classify the images
    categorized_images = classify_real_estate_images_with_openai(image_paths_or_urls)

    # Print results
    print("\nClassification Results:")
    for category, images in categorized_images.items():
        print(f"{category}: {len(images)} images")
        for img in images[:3]:  # Show first 3 examples
            print(f"  - {os.path.basename(img) if not img.startswith('http') else img}")
        if len(images) > 3:
            print(f"  - ... and {len(images) - 3} more")

    return categorized_images