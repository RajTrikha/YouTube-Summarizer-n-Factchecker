import os
import asyncio
import json
import traceback
import time
from typing import Any
from .celery_app import celery
from .models import AnalysisTask, TaskStatus, User, ContentItem
from .services import youtube_service
from .graph.graph import create_work_graph
from .agents.topic_segmentation_agent import TopicSegmentationAgent
from langchain_openai import ChatOpenAI
from datetime import datetime, timedelta, timezone
from celery import chord
from pydantic.v1.types import SecretStr
import google.oauth2.credentials
from googleapiclient.discovery import build
from .services.email_service import EmailDigestService
from jinja2 import Environment, FileSystemLoader, select_autoescape
from typing import Optional

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)

def initialize_llms():
    """Initializes and returns LangChain LLM instances with rate limiting."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    flash_model = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=SecretStr(openai_api_key) if openai_api_key else None
    )
    # Return flash_model for both to avoid Pro rate limits
    return flash_model, flash_model


def _coerce_summary(payload: Any) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("overall_summary", "summary", "final_summary", "executive_summary", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _extract_item_analysis(final_state: dict[str, Any]) -> dict[str, Any]:
    summary = (
        _coerce_summary(final_state.get("summary"))
        or _coerce_summary(final_state.get("overall_summary"))
        or _coerce_summary(final_state.get("final_summary"))
    )

    key_points: list[str] = []
    moments: list[dict[str, Any]] = []
    chapters = final_state.get("chapters") or []

    if isinstance(chapters, list):
        for chapter in chapters[:8]:
            if not isinstance(chapter, dict):
                continue
            chapter_points = chapter.get("key_points") or []
            if isinstance(chapter_points, list):
                for point in chapter_points:
                    if isinstance(point, str) and point.strip() and point not in key_points:
                        key_points.append(point.strip())
            chapter_summary = chapter.get("chapter_summary") or chapter.get("summary")
            if chapter_summary:
                moments.append(
                    {
                        "label": str(chapter.get("formatted_time") or chapter.get("start_time") or ""),
                        "text": str(chapter_summary)[:220],
                    }
                )

    if not summary:
        chapter_summaries = [m.get("text", "") for m in moments if isinstance(m, dict)]
        if chapter_summaries:
            summary = " ".join(chapter_summaries[:2])[:420]
        elif isinstance(final_state.get("transcript"), str):
            summary = final_state["transcript"][:320]
        else:
            summary = "Summary unavailable."

    return {
        "summary": summary,
        "key_points": key_points[:8],
        "moments": moments[:8],
    }

@celery.task(name="run_analysis_pipeline", bind=True, max_retries=3)
def run_analysis_pipeline(
    self,
    task_id: str,
    youtube_url: str,
    video_title: Optional[str] = None,
    content_item_id: Optional[int] = None,
):
    from csgy6613_ai_project.celery_app import SessionLocal
    db = SessionLocal()  # Create a new session for this task
    try:
        task = db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()
        if task:
            task.status = TaskStatus.PROCESSING.value  # type: ignore
            db.commit()
        pro_model, flash_model = initialize_llms()
        segmentation_agent = TopicSegmentationAgent(model=flash_model)
        app_graph = create_work_graph(
            youtube_service=youtube_service,
            segmentation_agent=segmentation_agent,
            summarizer_model=flash_model,  # Changed from pro_model to flash_model
            claim_extractor_model=flash_model,
            search_query_model=flash_model
        )
        # Add delay before processing to avoid rate limits
        print(f"Starting analysis for task {task_id}. Adding 2-second delay...")
        time.sleep(2)
        safe_title = video_title if video_title is not None else "Video Analysis"
        initial_state = {"youtube_url": youtube_url, "video_title": safe_title}
        final_state = asyncio.run(app_graph.ainvoke(initial_state))
        if isinstance(final_state, list):
            final_state = final_state[-1]
        final_state["video_title"] = safe_title
        if final_state.get("error"):
            raise Exception(final_state["error"])
        if task:
            task.status = TaskStatus.SUCCESS.value  # type: ignore
            task.result = final_state  # type: ignore
        if content_item_id:
            content_item = db.query(ContentItem).filter(ContentItem.id == content_item_id).first()
            if content_item:
                metadata = dict(content_item.extra_metadata or {})
                metadata["item_status"] = "ready"
                metadata["task_id"] = task_id
                metadata["analysis"] = _extract_item_analysis(final_state)
                content_item.extra_metadata = metadata
        db.commit()
        return {"status": "SUCCESS", "result": final_state}
    except Exception as e:
        error_message = str(e)
        if "429" in error_message or "quota" in error_message.lower():
            print(f"Rate limit hit for task {task_id}. Retrying in 60 seconds...")
            if self.request.retries < self.max_retries:
                if task:
                    task.status = TaskStatus.PROCESSING.value  # type: ignore
                    task.result = {"status": "retrying", "retry_count": self.request.retries + 1}  # type: ignore
                    db.commit()
                countdown = 60 * (2 ** self.request.retries)
                raise self.retry(countdown=countdown)
        full_error_message = f"An unexpected error occurred: {error_message}"
        print(f"Error during task execution for {task_id}: {full_error_message}")
        traceback.print_exc()
        if task:
            task.status = TaskStatus.FAILURE.value  # type: ignore
            task.result = {"error": full_error_message}  # type: ignore
        if content_item_id:
            content_item = db.query(ContentItem).filter(ContentItem.id == content_item_id).first()
            if content_item:
                metadata = dict(content_item.extra_metadata or {})
                metadata["item_status"] = "failed"
                metadata["analysis"] = {
                    "summary": f"Analysis failed: {full_error_message}",
                    "key_points": [],
                    "moments": [],
                }
                content_item.extra_metadata = metadata
        db.commit()
        return {"status": "FAILURE", "task_id": task_id, "error": full_error_message}
    finally:
        db.close()  # Always close the session!

@celery.task(name="fetch_and_queue_videos_for_user")
def fetch_and_queue_videos_for_user(user_id: int):
    from csgy6613_ai_project.celery_app import SessionLocal
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.youtube_refresh_token is None:
        db.close()
        return f"User {user_id} not found or has no YouTube token."
    try:
        credentials = google.oauth2.credentials.Credentials(
            None,
            refresh_token=user.youtube_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        )
    except Exception as e:
        print(f"Error creating credentials for user {user.email}: {e}")
        db.close()
        return f"Invalid credentials for user {user_id}. Please re-authenticate."
    youtube = build("youtube", "v3", credentials=credentials)
    channels_response = youtube.channels().list(part="contentDetails", mine=True).execute()
    liked_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["likes"]
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(days=1)
    videos_to_process = []
    playlist_items = youtube.playlistItems().list(
        part="snippet", playlistId=liked_playlist_id, maxResults=25
    ).execute()
    for item in playlist_items.get("items", []):
        liked_at = datetime.fromisoformat(item["snippet"]["publishedAt"].replace("Z", "+00:00"))
        if liked_at >= twenty_four_hours_ago:
            video_url = f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"
            videos_to_process.append(video_url)
    print(f"Found {len(videos_to_process)} new videos for user {user.email}.")
    if not videos_to_process:
        db.close()
        return "No new videos to process."
    # Create analysis tasks in the DB first to get their primary task_ids
    task_records = []
    for video_url in videos_to_process:
        db_task = AnalysisTask(status=TaskStatus.PENDING.value)  # type: ignore
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        task_records.append({"task_id": db_task.task_id, "url": video_url})
    # Create a Celery Chord
    analysis_tasks = [
        run_analysis_pipeline.s(task_id=rec['task_id'], youtube_url=rec['url'], video_title=rec.get('title', None))
        for rec in task_records
    ]
    callback = compile_and_send_digest.s(user_id=user.id)
    chord(analysis_tasks)(callback)
    db.close()
    return f"Queued {len(videos_to_process)} videos for user {user.email}."

@celery.task(name="compile_and_send_digest")
def compile_and_send_digest(analysis_results: list, user_id: int):
    from csgy6613_ai_project.celery_app import SessionLocal
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        db.close()
        return
    print(f"Compiling digest for user {user.email}...")
    
    # Build videos list for template
    videos = []
    successful_analyses = [res for res in analysis_results if isinstance(res, dict) and res.get('status') == 'SUCCESS']
    
    for analysis in successful_analyses:
        result = analysis.get("result", {})
        if not isinstance(result, dict):
            print(f"[WARNING] Skipping analysis with non-dict result: {type(result)} - {result}")
            continue  # Skip if result is not a dict
        
        # Fix: Handle summary extraction more safely
        summary_data = result.get("summary", {})
        if isinstance(summary_data, dict):
            overall_summary = summary_data.get("overall_summary", "Summary could not be generated.")
        elif isinstance(summary_data, str):
            overall_summary = summary_data
        else:
            overall_summary = "Summary could not be generated."
        
        video_title = result.get("video_title", "Video Analysis")
        video_id = result.get("video_id", "")
        youtube_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else "#"
        
        # Extract video metadata including duration
        metadata = result.get("metadata", {})
        duration = metadata.get("duration", "N/A")
        if duration != "N/A" and isinstance(duration, (int, float)):
            # Format duration from seconds to readable format
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration = f"{minutes}:{seconds:02d}"
        
        # Fact-check highlights
        fact_check_html = ""
        fact_checks = result.get("fact_check_results", [])
        for fc in fact_checks:
            verdict = fc.get("verdict", "N/A")
            explanation = fc.get("explanation", "")
            claim = fc.get("claim", "")
            confidence = fc.get("confidence_score", 0.0)
            confidence_percent = int(confidence * 100) if confidence else 0
            
            fact_check_html += f"<li><strong>{verdict}</strong> ({confidence_percent}% confidence): <em>{claim}</em><br>{explanation}</li>"
        
        chapters = result.get("chapters", [])
        # Sort chapters by start_time to ensure correct chronological order
        sorted_chapters = sorted(chapters, key=lambda x: x.get("start_time", 0))
        
        chapter_summaries = [
            {
                "title": ch.get("title", ""),
                "summary": ch.get("chapter_summary", ""),
                "start_time": ch.get("start_time", 0),
                "formatted_time": ch.get("formatted_time", "0:00"),
                "video_id": video_id
            }
            for ch in sorted_chapters
        ]
        
        videos.append({
            "title": video_title,
            "youtube_url": youtube_url,
            "video_id": video_id,
            "duration": duration,  # Add duration for email template
            "chapter_count": len(chapter_summaries),  # Add chapter count
            "summary": overall_summary,
            "fact_check_html": fact_check_html,
            "chapter_summaries": chapter_summaries
        })
    
    template = env.get_template("daily_digest.html")
    email_body = template.render(
        date=datetime.now().strftime('%B %d, %Y'),
        videos=videos
    )
    
    email_service = EmailDigestService()
    email_service.send_email(email_body, str(user.email))
    db.close()
    return f"Digest sent successfully to {user.email}."
