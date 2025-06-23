from typing import TypedDict, List, Dict, Optional

class GraphState(TypedDict):
    """
    Represents the state of our graph.
    """
    youtube_url: str
    video_id: Optional[str]
    transcript: Optional[str]
    timed_transcript: Optional[List[Dict]]
    chapters: Optional[List[Dict]]
    summary: Optional[str]
    claims: Optional[List[str]]
    fact_check_results: Optional[List[Dict]]
    error: Optional[str]
