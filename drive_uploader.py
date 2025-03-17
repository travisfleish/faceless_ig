import mimetypes
import urllib.parse
import hashlib
import requests
from io import BytesIO
from PIL import Image
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from config import SERVICE_ACCOUNT_FILE, GOOGLE_DRIVE_FOLDER_ID

# ✅ Google Drive Authentication
def authenticate_google_drive():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)

drive_service = authenticate_google_drive()

# ✅ Check if File Exists in Google Drive
def file_exists_in_drive(file_name, folder_id):
    """Check if a file already exists in Google Drive to prevent duplicate uploads."""
    try:
        query = f"name = '{file_name}' and '{folder_id}' in parents and trashed=false"
        results = drive_service.files().list(q=query, spaces="drive", fields="files(id, webViewLink)").execute()
        files = results.get("files", [])
        if files:
            print(f"🔍 Found existing file: {file_name} → {files[0]['webViewLink']}")
            return files[0]["webViewLink"]
        return None
    except HttpError as error:
        print(f"⚠️ Error checking file existence: {error}")
        return None

# ✅ Create Google Drive Folder for Listings
def create_drive_folder(folder_name):
    """Creates a folder inside the shared Google Drive folder."""
    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [GOOGLE_DRIVE_FOLDER_ID]
    }
    folder = drive_service.files().create(body=file_metadata, fields="id").execute()
    print(f"📁 Created folder: {folder_name} (ID: {folder.get('id')}) inside {GOOGLE_DRIVE_FOLDER_ID}")
    return folder.get("id")

# ✅ Upload Images to Google Drive
def upload_image_to_drive(image_url, folder_id, listing_address, index):
    """Uploads an image to Google Drive, avoiding duplicates."""
    print(f"📤 Processing image: {image_url}")

    try:
        response = requests.get(image_url, stream=True, timeout=10)
        if response.status_code == 200:
            # **Step 1: Detect file extension**
            parsed_url = urllib.parse.urlparse(image_url)
            file_ext = os.path.splitext(parsed_url.path)[-1] or ".jpg"
            if len(file_ext) > 5:
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

            # **Step 4: Check if file exists**
            existing_file_link = file_exists_in_drive(file_name, folder_id)
            if existing_file_link:
                return existing_file_link

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
