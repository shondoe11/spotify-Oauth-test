import os
import requests
from datetime import datetime, timedelta
from flask import Flask, redirect, request, jsonify, session
import urllib.parse
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

#! secrets, in real proj store in env & import out
app.secret_key = os.getenv('FLASK_SECRET_KEY')
#^ random string for now
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'

#? home page
@app.route('/')
def index(): return "Welcome to my Spotify test App <a href='/login'>Login with Spotify</a>"

#? login page
@app.route('/login')
def login():
    scope = 'user-read-private user-read-email'
    #! required by Spotify docs
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI,
        'show_dialog': True #~ so can open debug & test when user tries login, remove later in production
    }
    #? encode the params using urllib library
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)

#? callback endpoint
@app.route('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})
    
    if 'code' in request.args:
        req_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        #~send to spotify
        response = requests.post(TOKEN_URL, data=req_body)
        #~ if ok, spotify returns token info in json
        token_info = response.json()
        #? 3 pieces of key info req by spotify - magic of Oauth
        session['access_token'] = token_info['access_token'] #~to make req to spotify-api, access_token lasts for 1d
        session['refresh_token'] = token_info['refresh_token'] #~to refresh access_token when it expires
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in'] #~ can modify token_info['expires_in'] to + 10 for example (10 seconds to test refresh token logic)
        #^ gets the current datetime, turned into timestamp (ss epoch) exactly when token expires

        return redirect('/playlists')


#? endpoint to retrieve current user's playlists
@app.route('/playlists')
def get_playlists():
    #~ err handling
    if 'access_token' not in session: 
        return redirect('/login')
    #~ if token expires, redirect to refresh first
    if datetime.now().timestamp() > session['expires_at']:
        print("TOKEN EXPIRED. REFRESHING...") #~ test refresh token logic
        return redirect('/refresh-token')
    #~ if all ok, actual req
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }

    response = requests.get(API_BASE_URL + 'me/playlists', headers=headers)
    #~ once get response back ok, extract json corresponding to playlists
    playlists = response.json()

    return jsonify(playlists)


#? endpoint for refreshing the token
@app.route('/refresh-token')
def refresh_token():
    #~ err handling check
    if 'refresh_token' not in session:
        #~ if token expires, redirect to refresh first
        return redirect('/login')
    
    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            #~ req by spotify api specifically
            'grant_type': 'refresh_token',
            'refresh_token' : session['refresh_token'],
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        response = requests.post(TOKEN_URL, data=req_body)
        new_token_info = response.json()
        #~ override with new access token, 
        session['access_token'] = new_token_info['access_token']
        #~ convert new expire date&time again
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in'] 

        return redirect('/playlists')


if __name__ == '__main__':
    #~run on localhost, debug true means auto-refresh during code changes here
    app.run(host='0.0.0.0', debug=True, port=5001)
    #^ port 5001, as 5000 is used by MacOS ControlCenter