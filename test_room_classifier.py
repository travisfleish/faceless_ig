import os
import io
import time
import json
import base64
import random
import requests
from PIL import Image
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from config import SERVICE_ACCOUNT_FILE, OPENAI_API_KEY


def authenticate_google_drive():
    """Authenticate to Google Drive."""
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE,
                                                  scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)


def download_image_from_drive(file_id, drive_service):
    """Download an image from Google Drive by file ID."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file_content = request.execute()
        return file_content
    except Exception as e:
        print(f"Error downloading file {file_id}: {e}")
        return None


def get_files_from_folder(folder_id, drive_service):
    """Get all files from a Google Drive folder."""
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = drive_service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType, webContentLink)"
        ).execute()

        files = results.get("files", [])
        return files
    except Exception as e:
        print(f"Error getting files from folder: {e}")
        return []


def classify_images_with_openai(image_urls, max_batch_size=5):
    """
    Classify real estate images using OpenAI's Vision API.

    Args:
        image_urls: List of image URLs
        max_batch_size: Maximum number of images to process in one API call

    Returns:
        list: List of dictionaries with image data and categories
    """
    results = []

    # Process images in batches to avoid token limits
    for i in range(0, len(image_urls), max_batch_size):
        batch = image_urls[i:i + max_batch_size]
        print(
            f"Processing batch {i // max_batch_size + 1} of {(len(image_urls) + max_batch_size - 1) // max_batch_size} ({len(batch)} images)...")

        batch_results = process_image_batch_with_openai(batch)
        results.extend(batch_results)

        # Add a delay between batches to avoid rate limits
        if i + max_batch_size < len(image_urls):
            print("Waiting 3 seconds between batches...")
            time.sleep(3)

    return results


def process_image_batch_with_openai(image_urls):
    """
    Process a batch of images using OpenAI's Vision API.

    Args:
        image_urls: List of image URLs

    Returns:
        list: List of dictionaries with image URLs and categories
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    # Prepare the messages
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

            Respond ONLY with the category name, nothing else."""
        }
    ]

    # Add each image to the content
    for url in image_urls:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "What category does this real estate photo belong to?"},
                {"type": "image_url", "image_url": {"url": url}}
            ]
        })

    # Call the OpenAI API
    try:
        print("Calling OpenAI API...")
        payload = {
            "model": "gpt-4o",  # Using the known working model
            "messages": messages,
            "max_tokens": 200,
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response_data = response.json()

        if 'error' in response_data:
            print(f"API Error: {response_data.get('error', {})}")
            return []

        # Parse the results
        results = []
        choices = response_data.get("choices", [])

        for i, choice in enumerate(choices):
            if i >= len(image_urls):
                break

            category = choice.get("message", {}).get("content", "").strip().lower()

            # Validate the category
            valid_categories = ["exterior", "living_room", "kitchen", "primary_bedroom",
                                "bathroom", "other_bedroom", "special_feature", "view",
                                "outdoor_space", "other"]

            # Make sure the response is one of our valid categories
            if category not in valid_categories:
                # Try to match partial responses
                for valid_cat in valid_categories:
                    if valid_cat in category:
                        category = valid_cat
                        break
                else:
                    category = "other"  # Default if no match

            results.append({
                "url": image_urls[i],
                "category": category
            })

        print(f"Received {len(results)} classifications from OpenAI")
        return results

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return []


def test_room_classifier():
    """Test the OpenAI Vision-based room classifier on images from a Google Drive folder."""

    # Enter your Google Drive folder ID here
    test_folder_id = "1kRC5UBuSgkxvvT4D8gXiyOk_oVbqfVBP"

    # Initialize Google Drive API
    drive_service = authenticate_google_drive()

    # Get all files from the test folder
    print(f"Fetching files from Google Drive folder: {test_folder_id}")
    image_files = get_files_from_folder(test_folder_id, drive_service)

    # Filter for only image files
    image_files = [f for f in image_files if f.get('mimeType', '').startswith('image/')]

    if not image_files:
        print("No image files found in the specified folder.")
        return

    print(f"Found {len(image_files)} images in the folder.")

    # Create a list of image URLs from Drive's webContentLink
    image_urls = []
    for img in image_files:
        if 'webContentLink' in img:
            # Remove download parameters to make it viewable
            url = img['webContentLink'].split('&export=download')[0]
            image_urls.append(url)
        else:
            # Generate a viewable URL if webContentLink is not available
            image_urls.append(f"https://drive.google.com/uc?id={img['id']}")

    # Process all images (removed the limit)
    print(f"Processing all {len(image_urls)} images...")

    # Classify images using OpenAI Vision API
    print("Classifying images with OpenAI Vision API...")
    classified_images = classify_images_with_openai(image_urls)

    # Create a lookup from URL to classification result
    url_to_classification = {result['url']: result['category'] for result in classified_images}

    # Create a lookup from file ID to name
    id_to_name = {img['id']: img['name'] for img in image_files}

    # Group images by category
    categories = {
        "exterior": [],
        "living_room": [],
        "kitchen": [],
        "primary_bedroom": [],
        "bathroom": [],
        "other_bedroom": [],
        "special_feature": [],
        "view": [],
        "outdoor_space": [],
        "other": []
    }

    for result in classified_images:
        category = result['category']
        if category in categories:
            categories[category].append(result['url'])

    # Print classification results
    print("\nClassification Results:")
    print("======================")
    for category, urls in categories.items():
        print(f"{category}: {len(urls)} images")
        for url in urls[:3]:  # Show first 3 examples
            file_id = url.split('id=')[-1].split('&')[0] if 'id=' in url else None
            file_name = id_to_name.get(file_id, url)
            print(f"  - {file_name}")
        if len(urls) > 3:
            print(f"  - ... and {len(urls) - 3} more")

    # Select diverse set of photos for Instagram
    max_photos = 10
    selected_images = []

    # First image is always the hero image
    if image_urls:
        hero_image_url = image_urls[0]
        selected_images.append(hero_image_url)

        # Priority order for categories
        priority_categories = [
            "exterior",
            "kitchen",
            "living_room",
            "primary_bedroom",
            "bathroom",
            "special_feature",
            "outdoor_space",
            "view",
            "other_bedroom",
            "other"
        ]

        # First round: take one from each category in priority order
        for category in priority_categories:
            if len(selected_images) >= max_photos:
                break

            for url in categories[category]:
                if url not in selected_images:
                    selected_images.append(url)
                    categories[category].remove(url)
                    break

        # Second round: take another from key categories if needed
        second_round = ["kitchen", "living_room", "primary_bedroom", "special_feature"]
        for category in second_round:
            if len(selected_images) >= max_photos:
                break

            for url in categories[category]:
                if url not in selected_images:
                    selected_images.append(url)
                    categories[category].remove(url)
                    break

    # Print selection results
    print("\nSelected Photos for Instagram:")
    print("================================")
    for i, url in enumerate(selected_images):
        # Try to find the original file name
        file_id = url.split('id=')[-1].split('&')[0] if 'id=' in url else None
        file_name = id_to_name.get(file_id, f"Image {i + 1}")

        # Get the category
        category = url_to_classification.get(url, "unknown")

        print(f"{i + 1}. {file_name} ({category})")

    print(f"\nTotal selected: {len(selected_images)} out of {len(image_files)} available images")

    # Output a summary of the representation
    categories_in_selection = {}
    for url in selected_images:
        category = url_to_classification.get(url, "unknown")

        if category not in categories_in_selection:
            categories_in_selection[category] = 0
        categories_in_selection[category] += 1

    print("\nCategory representation in selection:")
    for category, count in categories_in_selection.items():
        print(f"{category}: {count} images")


if __name__ == "__main__":
    test_room_classifier()