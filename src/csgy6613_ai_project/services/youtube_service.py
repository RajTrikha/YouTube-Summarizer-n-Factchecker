import re
from youtube_transcript_api import YouTubeTranscriptApi

def get_transcript(video_id: str, with_timestamps: bool = False):
    """
    Fetches the transcript, optionally with timestamps.
    
    Args:
        video_id: The YouTube video ID
        with_timestamps: If True, returns list of dicts with timestamps
                        If False, returns plain text string
    
    Returns:
        List of dicts with timestamps if with_timestamps=True
        Plain text string if with_timestamps=False
        None if error occurs
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        
        if with_timestamps:
            return transcript_list
        else:
            transcript = " ".join([item['text'] for item in transcript_list])
            return re.sub(r'\s+', ' ', transcript).strip()
            
    except Exception as e:
        print(f"Error fetching transcript for video ID {video_id}: {e}")
        return None

def extract_video_id(url: str) -> str | None:
    """Extracts the YouTube video ID from a URL."""
    match = re.search(r"(?<=v=)[^&#]+", url) or re.search(r"(?<=be/)[^&#]+", url)
    return match.group(0) if match else None