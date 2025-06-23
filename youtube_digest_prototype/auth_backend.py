import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Serves the main login page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login")
def login(request: Request):
    """Redirects the user to Google's OAuth consent screen."""
    redirect_uri = request.url_for('auth_callback')
    auth_redirect_url = (
        f"{AUTH_URL}?response_type=code&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}&scope={SCOPE}&access_type=offline"
    )
    return RedirectResponse(auth_redirect_url)


@app.get("/auth/callback", response_class=HTMLResponse)
def auth_callback(request: Request, code: str):
    """
    Handles the callback from Google after the user grants permission.
    Exchanges the authorization code for an access token and refresh token.
    """
    redirect_uri = request.url_for('auth_callback')
    
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    response = requests.post(TOKEN_URL, data=token_data)
    token_info = response.json()

    # In a real application, you would securely encrypt and store these tokens
    # in your PostgreSQL database, associated with the user's account.
    access_token = token_info.get("access_token")
    refresh_token = token_info.get("refresh_token")

    print("--- AUTH SUCCESSFUL ---")
    print(f"Access Token: {access_token[:20]}...")
    print(f"Refresh Token: {refresh_token}")
    print("-----------------------")
    
    return templates.TemplateResponse("success.html", {
        "request": request,
        "access_token": access_token,
        "refresh_token": refresh_token
    })
