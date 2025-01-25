from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import boto3
import os
import io

app = Flask(__name__)

# AWS S3 Configuration
AWS_ACCESS_KEY = "AKIAYS2NXHWN5VAG4MRF"
AWS_SECRET_KEY = "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"
AWS_REGION = "us-east-1"
AWS_BUCKET_NAME = "songsuploadmonarrch"

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

            # Save the credentials to token.json
            with open('token.json', 'w') as token_file:
                token_file.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

# Fetch files in a Google Drive folder
def fetch_files_from_folder(folder_id, service):
    query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    return files

# Upload a file to S3
def upload_to_s3(file_stream, file_name):
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )
        s3_client.upload_fileobj(file_stream, AWS_BUCKET_NAME, file_name)
        file_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{file_name}"
        return file_url
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        raise

# Download a file from Google Drive and upload it to S3
def download_and_upload(file_id, file_name, service):
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    file_stream.seek(0)  # Reset stream position for upload
    return upload_to_s3(file_stream, file_name)

# Flask Routes
@app.route('/fetch-files', methods=['POST'])
def fetch_files():
    try:
        data = request.json
        folder_id = data.get('folder_id')
        if not folder_id:
            return jsonify({'error': 'Folder ID is required'}), 400

        service = authenticate_google_drive()
        files = fetch_files_from_folder(folder_id, service)
        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload-to-s3', methods=['POST'])
def upload():
    try:
        data = request.json
        file_id = data.get('file_id')
        file_name = data.get('file_name')
        if not file_id or not file_name:
            return jsonify({'error': 'File ID and File Name are required'}), 400

        service = authenticate_google_drive()
        file_url = download_and_upload(file_id, file_name, service)
        return jsonify({'message': 'File uploaded successfully', 'file_url': file_url}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return jsonify({'message': 'Google Drive to S3 API is running'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
