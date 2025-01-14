from flask import Flask, request, jsonify, redirect, session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import io
import boto3

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "1234")

# Google OAuth Configuration
CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://downloaddrivefiles.onrender.com/callback")

# AWS S3 Configuration
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "monarchsongs")
s3_client = boto3.client('s3')


# Route to start Google OAuth process
@app.route('/authorize', methods=['GET'])
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return jsonify({"authorization_url": authorization_url})


# Callback route after Google authorization
@app.route('/callback', methods=['GET'])
def callback():
    state = session.get('state')
    if not state:
        return jsonify({"error": "State missing or expired."}), 400

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    return jsonify({"message": "Authorization successful!"})


# Helper function to authenticate Google Drive service
def authenticate_google_drive():
    if 'credentials' not in session:
        raise Exception("User not authenticated")

    creds_data = session['credentials']
    credentials = Credentials(
        creds_data['token'],
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    return build('drive', 'v3', credentials=credentials)


# Route to fetch audio files from Google Drive folder
@app.route('/fetch-files', methods=['POST'])
def fetch_files():
    try:
        folder_id = request.json.get("folder_id")
        if not folder_id:
            return jsonify({"error": "folder_id is required"}), 400

        service = authenticate_google_drive()
        query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Route to download a file from Google Drive and upload to S3
@app.route('/download-and-upload', methods=['POST'])
def download_and_upload():
    try:
        file_id = request.json.get("file_id")
        file_name = request.json.get("file_name")
        if not file_id or not file_name:
            return jsonify({"error": "file_id and file_name are required"}), 400

        service = authenticate_google_drive()

        # Download file from Google Drive
        request_drive = service.files().get_media(fileId=file_id)
        file_data = io.BytesIO()
        downloader = MediaIoBaseDownload(file_data, request_drive)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        # Reset buffer position to the start
        file_data.seek(0)

        # Upload to S3
        s3_client.upload_fileobj(file_data, S3_BUCKET, file_name)
        s3_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{file_name}"

        return jsonify({"message": "File uploaded to S3", "s3_url": s3_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Route to check if user is authenticated
@app.route('/is-authenticated', methods=['GET'])
def is_authenticated():
    if 'credentials' in session:
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False})


# Logout and clear session
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


if __name__ == '__main__':
    app.run(debug=True)
