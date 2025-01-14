from flask import Flask, request, jsonify, redirect, session, url_for
from google_auth_oauthlib.flow import Flow
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "1234")

# OAuth 2.0 Client Configuration
CLIENT_SECRETS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://downloaddrivefiles.onrender.com/callback')

# Route to start the authorization process
@app.route('/authorize', methods=['GET'])
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # Get the authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    # Save the state to the session
    session['state'] = state

    # Return the URL as JSON for the frontend to redirect the user
    return jsonify({'authorization_url': authorization_url})

# Route to handle the callback after user authorizes
@app.route('/callback', methods=['GET'])
def callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )

    # Exchange the authorization code for tokens
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Save credentials to a session or a secure database
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    return jsonify({'message': 'Authorization successful!'})

# Helper route to check credentials
@app.route('/check-credentials', methods=['GET'])
def check_credentials():
    if 'credentials' not in session:
        return jsonify({'error': 'User not authorized'}), 401
    return jsonify(session['credentials'])
