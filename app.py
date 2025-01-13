from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import io

app = Flask(__name__)

# Helper functions
def authenticate_google_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def fetch_files_from_folder(folder_id, service):
    query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get('files', [])

def download_file(file_id, file_name, service):
    request = service.files().get_media(fileId=file_id)
    file_path = os.path.join('downloads', file_name)
    os.makedirs('downloads', exist_ok=True)
    with open(file_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    return file_path

# API routes
@app.route('/fetch-files', methods=['POST'])
def fetch_files():
    data = request.json
    folder_id = data.get('folder_id')
    if not folder_id:
        return jsonify({"error": "Missing folder_id"}), 400
    
    try:
        service = authenticate_google_drive()
        files = fetch_files_from_folder(folder_id, service)
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download-file', methods=['POST'])
def download():
    data = request.json
    file_id = data.get('file_id')
    file_name = data.get('file_name')
    
    if not file_id or not file_name:
        return jsonify({"error": "Missing file_id or file_name"}), 400
    
    try:
        service = authenticate_google_drive()
        file_path = download_file(file_id, file_name, service)
        return jsonify({"message": f"File downloaded to {file_path}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
