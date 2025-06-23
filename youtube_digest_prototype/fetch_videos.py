import os
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
# This script uses the same credentials as your auth_backend.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# Paste the REFRESH TOKEN you received on the "Authentication Successful!" page.
# In a real app, this would be retrieved from your database for a specific user.
USER_REFRESH_TOKEN = "1//05ISzoTfxzpoHCgYIARAAGAUSNwF-L9IrVYleIr2eJqF_dYUAD5gcjCM-0zlYHlPtatbh_jbB33IMT10vRI1gwO1rHqFyrAR6W2E" 
# ---------------------

def get_credentials_from_refresh_token(refresh_token):
    """Creates Google API credentials from a refresh token."""
    credentials = google.oauth2.credentials.Credentials(
        None,  # No access token needed initially
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
    )
    # The credentials object will automatically handle refreshing the access token.
    return credentials

def fetch_recent_liked_videos(credentials):
    """
    Fetches videos from the "Liked videos" playlist that were liked in the last 24 hours.
    """
    youtube = build("youtube", "v3", credentials=credentials)

    # Get the "Liked videos" playlist ID. 'LL' is the static ID for this playlist.
    channels_response = youtube.channels().list(
        part="contentDetails",
        mine=True
    ).execute()
    
    liked_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["likes"]

    print(f"Found 'Liked videos' playlist with ID: {liked_playlist_id}")

    # Calculate the timestamp for 24 hours ago
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(days=1)

    recent_videos = []
    next_page_token = None

    print("\nFetching recently liked videos...")
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=liked_playlist_id,
            maxResults=50, # Max allowed per page
            pageToken=next_page_token
        ).execute()

        for item in playlist_response["items"]:
            # The 'publishedAt' for a playlistItem is when it was added to the playlist (i.e., when it was 'liked')
            liked_at_str = item["snippet"]["publishedAt"]
            liked_at = datetime.fromisoformat(liked_at_str.replace("Z", "+00:00"))
            
            if liked_at >= twenty_four_hours_ago:
                video_title = item["snippet"]["title"]
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                recent_videos.append({"title": video_title, "url": video_url})
                print(f"  - Found recent video: {video_title}")

        next_page_token = playlist_response.get("nextPageToken")
        
        # If the next page contains videos older than our cutoff, we can stop early.
        # This is an optimization for users with many liked videos.
        if not next_page_token or (playlist_response["items"] and datetime.fromisoformat(playlist_response["items"][-1]["snippet"]["publishedAt"].replace("Z", "+00:00")) < twenty_four_hours_ago):
            break

    return recent_videos

if __name__ == "__main__":
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        print("ERROR: Make sure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set in your .env file.")
    elif USER_REFRESH_TOKEN == "PASTE_YOUR_REFRESH_TOKEN_HERE":
        print("ERROR: Please paste your refresh token into the USER_REFRESH_TOKEN variable in this script.")
    else:
        # Step 1: Get credentials using the user's stored refresh token
        user_credentials = get_credentials_from_refresh_token(USER_REFRESH_TOKEN)
        
        # Step 2: Fetch the recent videos
        videos = fetch_recent_liked_videos(user_credentials)
        
        print("\n--- DAILY DIGEST REPORT ---")
        if videos:
            print(f"Found {len(videos)} new videos in the last 24 hours to analyze:")
            for video in videos:
                print(f"  - Title: {video['title']}")
                print(f"    URL: {video['url']}")
        else:
            print("No new videos found in the last 24 hours.")
        print("-------------------------")