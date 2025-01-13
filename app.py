from flask import Flask, request, redirect, session, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import io

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', '1234')  # Replace with a secure key

# File paths
CLIENT_SECRETS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Initialize Google OAuth Flow
flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri=os.environ.get('REDIRECT_URI', 'https://downloaddrivefiles.onrender.com/callback')  # Update for Render
)

# Route: Initiate OAuth flow
@app.route('/authorize', methods=['GET'])
def authorize():
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    # Save state to session
    session['state'] = state
    return redirect(authorization_url)

# Route: Handle OAuth callback
@app.route('/callback', methods=['GET'])
def callback():
    # Validate state parameter
    if 'state' not in session or session['state'] != request.args.get('state'):
        return jsonify({"error": "Invalid state parameter"}), 400

    # Fetch token
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    # Save credentials to a file for reuse
    with open('token.json', 'w') as token_file:
        token_file.write(credentials.to_json())

    return jsonify({"message": "Authentication successful!"})

# Route: Fetch files from Google Drive folder
@app.route('/fetch-files', methods=['POST'])
def fetch_files():
    # Validate folder_id in request
    data = request.get_json()
    if 'folder_id' not in data:
        return jsonify({"error": "Missing 'folder_id' in request"}), 400
    folder_id = data['folder_id']

    # Load credentials from token.json
    try:
        with open('token.json', 'r') as token_file:
            credentials_data = token_file.read()
        credentials = Credentials.from_authorized_user_info(eval(credentials_data), SCOPES)
    except Exception as e:
        return jsonify({"error": f"Failed to load credentials: {str(e)}"}), 500

    # Authenticate with Google Drive
    service = build('drive', 'v3', credentials=credentials)

    # Fetch audio files in the folder
    try:
        query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch files: {str(e)}"}), 500

# Route: Download a specific file
@app.route('/download-file', methods=['POST'])
def download_file():
    # Validate file_id and file_name in request
    data = request.get_json()
    if 'file_id' not in data or 'file_name' not in data:
        return jsonify({"error": "Missing 'file_id' or 'file_name' in request"}), 400

    file_id = data['file_id']
    file_name = data['file_name']

    # Load credentials from token.json
    try:
        with open('token.json', 'r') as token_file:
            credentials_data = token_file.read()
        credentials = Credentials.from_authorized_user_info(eval(credentials_data), SCOPES)
    except Exception as e:
        return jsonify({"error": f"Failed to load credentials: {str(e)}"}), 500

    # Authenticate with Google Drive
    service = build('drive', 'v3', credentials=credentials)

    # Download the file
    try:
        request = service.files().get_media(fileId=file_id)
        os.makedirs('downloads', exist_ok=True)
        file_path = os.path.join('downloads', file_name)

        with open(file_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download progress: {int(status.progress() * 100)}%")

        return jsonify({"message": "File downloaded successfully!", "file_path": file_path})
    except Exception as e:
        return jsonify({"error": f"Failed to download file: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
