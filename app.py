from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import io

# Authenticate and create Google Drive service
def authenticate_google_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = None

    # Check for existing token.json
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            print(f"Error loading token.json: {e}")
            creds = None

    # If no valid credentials, perform a new login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())  # Refresh the token
                print("Token refreshed successfully.")
            except Exception as e:
                print(f"Token refresh failed: {e}. Starting re-authentication...")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)

            # Check if refresh_token is present
            if not creds.refresh_token:
                print("Warning: Refresh token is missing. Re-authentication will be required after the session.")

        # Save the credentials to token.json
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

# Fetch all files in a Google Drive folder
def fetch_files_from_folder(folder_id, service):
    query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    return files

# Download a file
def download_file(file_id, file_name, service):
    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join('downloads', file_name)
    os.makedirs('downloads', exist_ok=True)
    with open(file_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download progress: {int(status.progress() * 100)}%")
    return file_path

# Main function
if __name__ == "__main__":
    try:
        # Authenticate and create service
        service = authenticate_google_drive()

        # Example: Replace with the folder ID from the user's link
        folder_id = "1sIUhQoOpcQAJlFlfnshguglsEASufwew"

        # Fetch audio files
        files = fetch_files_from_folder(folder_id, service)
        print(f"Found {len(files)} audio files.")

        # Download all files
        for file in files:
            print(f"Downloading {file['name']}...")
            download_file(file['id'], file['name'], service)

    except Exception as e:
        print(f"An error occurred: {e}")
