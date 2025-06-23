import os
import requests
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from the .env file in the parent directory
load_dotenv(dotenv_path='../.env')

# --- CONFIGURATION ---
# This script uses the same Google credentials as your authentication prototype.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# This is the user's refresh token you would retrieve from your database.
# Paste the REFRESH TOKEN you received from the authentication prototype here.
USER_REFRESH_TOKEN = "1//05ISzoTfxzpoHCgYIARAAGAUSNwF-L9IrVYleIr2eJqF_dYUAD5gcjCM-0zlYHlPtatbh_jbB33IMT10vRI1gwO1rHqFyrAR6W2E" 

# This is the URL of your running backend API.
API_BASE_URL = "http://127.0.0.1:8000"
# ---------------------

def get_credentials_from_refresh_token(refresh_token):
    """Creates Google API credentials from a refresh token."""
    return google.oauth2.credentials.Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
    )

def fetch_recent_liked_videos(credentials):
    """Fetches videos from the "Liked videos" playlist from the last 24 hours."""
    youtube = build("youtube", "v3", credentials=credentials)
    
    channels_response = youtube.channels().list(
        part="contentDetails",
        mine=True
    ).execute()
    liked_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["likes"]
    print(f"Found 'Liked videos' playlist with ID: {liked_playlist_id}")

    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(days=1)
    recent_videos = []
    next_page_token = None

    print("\nFetching recently liked videos...")
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=liked_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in playlist_response["items"]:
            liked_at_str = item["snippet"]["publishedAt"]
            liked_at = datetime.fromisoformat(liked_at_str.replace("Z", "+00:00"))
            
            if liked_at >= twenty_four_hours_ago:
                video_title = item["snippet"]["title"]
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                recent_videos.append({"title": video_title, "url": video_url})
                print(f"  - Found recent video: {video_title}")

        next_page_token = playlist_response.get("nextPageToken")
        
        if not next_page_token or (playlist_response["items"] and datetime.fromisoformat(playlist_response["items"][-1]["snippet"]["publishedAt"].replace("Z", "+00:00")) < twenty_four_hours_ago):
            break

    return recent_videos

def submit_video_for_analysis(video_url: str):
    """Makes an API call to your backend to start an analysis task."""
    try:
        response = requests.post(f"{API_BASE_URL}/analyze", json={"url": video_url})
        response.raise_for_status()
        data = response.json()
        print(f"  -> Successfully queued task. Task ID: {data['task_id']}")
    except requests.exceptions.RequestException as e:
        print(f"  -> Failed to queue task for {video_url}. Error: {e}")

if __name__ == "__main__":
    print("--- Starting Daily Digest Job ---")
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        print("ERROR: Make sure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set in your .env file.")
    elif USER_REFRESH_TOKEN == "PASTE_YOUR_REFRESH_TOKEN_HERE":
        print("ERROR: Please paste your refresh token into the USER_REFRESH_TOKEN variable in this script.")
    else:
        # Step 1: Authenticate to YouTube API on behalf of the user
        user_credentials = get_credentials_from_refresh_token(USER_REFRESH_TOKEN)
        
        # Step 2: Fetch the recent videos
        videos_to_process = fetch_recent_liked_videos(user_credentials)
        
        # Step 3: Submit each video to your backend API for analysis
        if videos_to_process:
            print(f"\nSubmitting {len(videos_to_process)} videos to the analysis queue...")
            for video in videos_to_process:
                submit_video_for_analysis(video["url"])
        else:
            print("\nNo new videos to process.")

    print("\n--- Daily Digest Job Finished ---")