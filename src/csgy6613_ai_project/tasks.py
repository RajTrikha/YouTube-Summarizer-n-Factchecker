import os
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from celery import shared_task, chord
from sqlalchemy.orm import sessionmaker
from langchain_google_genai import ChatGoogleGenerativeAI
import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Local imports
from .database import engine
from .models import AnalysisTask, TaskStatus, User, Base
from .services import youtube_service
from .graph.graph import create_work_graph
from .agents.topic_segmentation_agent import TopicSegmentationAgent

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def initialize_llms():
    """Initialize LLMs with proper timeout settings and rate limiting configuration."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    # Use timeout instead of request_timeout to fix the warning
    flash_model = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest", 
        google_api_key=gemini_api_key, 
        temperature=0.2,
        timeout=60,  # Fixed parameter name
        max_retries=3
    )
    
    pro_model = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest", 
        google_api_key=gemini_api_key, 
        temperature=0.3,
        timeout=60,  # Fixed parameter name
        max_retries=3
    )
    
    return pro_model, flash_model

def update_task_progress(task_id: str, current_step: int, total_steps: int, step_name: str, message: str):
    """Update task progress in the database."""
    db = SessionLocal()
    try:
        task = db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()
        if task:
            progress_data = {
                "current_step": current_step,
                "total_steps": total_steps,
                "current_step_name": step_name,
                "message": message,
                "last_updated": datetime.utcnow().isoformat(),
                "percentage": round((current_step / total_steps) * 100, 1) if total_steps > 0 else 0
            }
            
            task.progress = json.dumps(progress_data)
            
            # Update status based on progress
            if current_step == 0:
                task.status = TaskStatus.PENDING
            elif current_step >= total_steps:
                task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.RUNNING
                
            db.commit()
            print(f"📊 Progress updated: {step_name} ({current_step}/{total_steps})")
        else:
            print(f"⚠️ Task {task_id} not found for progress update")
    except Exception as e:
        print(f"❌ Error updating progress: {e}")
        db.rollback()
    finally:
        db.close()

def update_task_status(task_id: str, status: TaskStatus, result: Dict[str, Any] = None, error_message: str = None):
    """Update task status and result in the database."""
    db = SessionLocal()
    try:
        task = db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()
        if task:
            task.status = status
            if result:
                task.result = json.dumps(result)
            if error_message:
                task.error_message = error_message
            db.commit()
            print(f"✅ Task {task_id} status updated to {status.value}")
        else:
            print(f"⚠️ Task {task_id} not found for status update")
    except Exception as e:
        print(f"❌ Error updating task status: {e}")
        db.rollback()
    finally:
        db.close()

@shared_task(bind=True, max_retries=3, default_retry_delay=300)  # 5 minute retry delay
def run_analysis_pipeline(self, task_id: str, youtube_url: str):
    """
    Main analysis pipeline with rate limiting and progress tracking.
    This task coordinates the entire video analysis workflow.
    """
    print(f"🚀 Starting analysis pipeline for task {task_id}")
    print(f"📹 Video URL: {youtube_url}")
    
    # Initialize progress tracking
    total_steps = 6
    
    try:
        # Step 0: Initialize
        update_task_progress(task_id, 0, total_steps, "Initializing", "Setting up analysis pipeline...")
        
        # Initialize models and services
        print("🔧 Initializing LLMs and services...")
        pro_model, flash_model = initialize_llms()
        segmentation_agent = TopicSegmentationAgent(model=flash_model)
        
        # Create the analysis graph with rate limiting
        app_graph = create_work_graph(
            youtube_service=youtube_service,
            segmentation_agent=segmentation_agent,
            summarizer_model=pro_model,
            claim_extractor_model=flash_model,
            search_query_model=flash_model
        )
        
        # Step 1: Start analysis
        update_task_progress(task_id, 1, total_steps, "Starting Analysis", "Beginning video processing...")
        
        # Run the analysis pipeline
        print(f"🎬 Processing video: {youtube_url}")
        final_state = {}
        
        # Track progress through the analysis steps
        step_mapping = {
            "get_video_info": (2, "Fetching Transcript", "Downloading video transcript..."),
            "segment_transcript_into_chapters": (3, "Segmenting Content", "Identifying chapters and topics..."),
            "generate_chapter_summaries": (4, "Generating Summaries", "Creating chapter summaries (this takes longest)..."),
            "extract_claims": (5, "Extracting Claims", "Identifying verifiable claims..."),
            "search_for_evidence": (6, "Fact Checking", "Verifying claims with web search...")
        }
        
        current_step = 1
        
        # Process the video with the rate-limited pipeline
        async def run_analysis():
            nonlocal final_state, current_step
            
            async for event in app_graph.astream_events({"youtube_url": youtube_url}, version="v1"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                
                # Track progress through different nodes
                if event_type == "on_chain_start":
                    for node_name, (step_num, step_title, step_msg) in step_mapping.items():
                        if node_name in event_name:
                            current_step = step_num
                            update_task_progress(task_id, current_step, total_steps, step_title, step_msg)
                            break
                
                # Capture final result
                elif event_type == "on_chain_end" and event_name == "LangGraph":
                    final_state = event["data"]["output"]
                    print("✅ Analysis pipeline completed successfully")
        
        # Run the async analysis
        asyncio.run(run_analysis())
        
        # Ensure we have a final state
        if isinstance(final_state, list):
            final_state = final_state[-1] if final_state else {}
        
        # Check for errors in the final state
        if final_state.get("error"):
            error_msg = final_state["error"]
            print(f"❌ Analysis failed: {error_msg}")
            update_task_status(task_id, TaskStatus.FAILED, error_message=error_msg)
            return {"error": error_msg}
        
        # Final step: Complete
        update_task_progress(task_id, total_steps, total_steps, "Complete", "Analysis finished successfully!")
        
        # Prepare the final result
        result = {
            "video_url": youtube_url,
            "video_id": final_state.get("video_id", ""),
            "summary": final_state.get("summary", ""),
            "chapters": final_state.get("chapters", []),
            "claims": final_state.get("claims", []),
            "fact_check_results": final_state.get("fact_check_results", []),
            "processing_time": "3-5 minutes (rate limited)",
            "analysis_completed_at": datetime.utcnow().isoformat()
        }
        
        # Update task with final result
        update_task_status(task_id, TaskStatus.COMPLETED, result)
        
        print(f"🎉 Analysis completed successfully for task {task_id}")
        print(f"📊 Generated {len(result.get('chapters', []))} chapters")
        print(f"🔍 Fact-checked {len(result.get('claims', []))} claims")
        
        return result
        
    except Exception as e:
        error_msg = f"Analysis pipeline failed: {str(e)}"
        print(f"❌ {error_msg}")
        
        # Handle specific rate limiting errors
        if "429" in str(e) or "quota" in str(e).lower():
            error_msg = "API rate limit exceeded. Please try again later or upgrade to a paid plan."
            # Retry the task after a delay
            if self.request.retries < self.max_retries:
                print(f"🔄 Retrying task {task_id} due to rate limit (attempt {self.request.retries + 1})")
                raise self.retry(countdown=600, exc=e)  # Retry after 10 minutes
        
        # Update task status
        update_task_status(task_id, TaskStatus.FAILED, error_message=error_msg)
        update_task_progress(task_id, 0, total_steps, "Failed", error_msg)
        
        # Re-raise the exception for Celery
        raise

@shared_task
def fetch_and_queue_videos_for_user(user_email: str):
    """
    Fetch recent videos from a user's YouTube subscriptions and queue them for analysis.
    This is used for the digest email feature.
    """
    print(f"📺 Fetching videos for user: {user_email}")
    
    db = SessionLocal()
    try:
        # Get user from database
        user = db.query(User).filter(User.email == user_email).first()
        if not user or not user.digest_enabled:
            print(f"⚠️ User {user_email} not found or digest disabled")
            return {"status": "skipped", "reason": "User not found or digest disabled"}
        
        if not user.youtube_refresh_token:
            print(f"⚠️ No YouTube token for user {user_email}")
            return {"status": "skipped", "reason": "No YouTube authorization"}
        
        # Get credentials from refresh token
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            print(f"❌ Google OAuth credentials not configured")
            return {"status": "error", "error": "Google OAuth credentials not configured"}
        
        credentials = google.oauth2.credentials.Credentials(
            None,
            refresh_token=user.youtube_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        )
        
        # Fetch recent videos from YouTube
        try:
            youtube = build("youtube", "v3", credentials=credentials)
            channels_response = youtube.channels().list(part="contentDetails", mine=True).execute()
            
            if not channels_response.get("items"):
                print(f"⚠️ No channel data found for user {user_email}")
                return {"status": "error", "error": "No channel data found"}
            
            content_details = channels_response["items"][0].get("contentDetails", {})
            related_playlists = content_details.get("relatedPlaylists", {})
            liked_playlist_id = related_playlists.get("likes")
            
            if not liked_playlist_id:
                print(f"⚠️ No liked playlist found for user {user_email}")
                return {"status": "error", "error": "No liked playlist found"}
                
        except HttpError as e:
            print(f"❌ YouTube API error: {str(e)}")
            return {"status": "error", "error": f"YouTube API error: {str(e)}"}
        
        # Get videos from the last 24 hours
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(days=1)
        videos_to_process = []
        
        try:
            playlist_items = youtube.playlistItems().list(
                part="snippet",
                playlistId=liked_playlist_id,
                maxResults=25  # Check the last 25 liked videos
            ).execute()
            
            for item in playlist_items.get("items", []):
                try:
                    published_at = item["snippet"]["publishedAt"]
                    # Handle both 'Z' and timezone formats
                    if published_at.endswith('Z'):
                        liked_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    else:
                        liked_at = datetime.fromisoformat(published_at)
                    
                    if liked_at >= twenty_four_hours_ago:
                        resource_id = item["snippet"].get("resourceId", {})
                        video_id = resource_id.get("videoId")
                        if video_id:
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            video_title = item["snippet"].get("title", "Unknown")
                            videos_to_process.append({
                                "url": video_url,
                                "title": video_title,
                                "video_id": video_id
                            })
                            print(f"  - Found recent video: {video_title}")
                except (KeyError, ValueError) as e:
                    print(f"⚠️ Error processing video item: {e}")
                    continue
                    
        except HttpError as e:
            print(f"❌ Error fetching playlist items: {str(e)}")
            return {"status": "error", "error": f"Error fetching playlist items: {str(e)}"}
        
        print(f"📊 Found {len(videos_to_process)} new videos for user {user_email}")
        
        # Queue analysis tasks for each video
        if not videos_to_process:
            return {"status": "completed", "videos_queued": 0}
        
        # Create individual tasks for each video
        task_ids = []
        for video in videos_to_process:
            task_id = str(uuid.uuid4())
            run_analysis_pipeline.delay(task_id=task_id, youtube_url=video["url"])
            task_ids.append(task_id)
        
        # Store task IDs for later digest compilation
        user.pending_digest_tasks = json.dumps(task_ids)
        db.commit()
        
        print(f"📋 Queued {len(videos_to_process)} videos for analysis")
        return {"status": "completed", "videos_queued": len(videos_to_process), "task_ids": task_ids}
        
    except Exception as e:
        print(f"❌ Error fetching videos for {user_email}: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()

@shared_task
def compile_and_send_digest(user_email: str):
    """
    Compile analyzed videos into a digest email and send it to the user.
    """
    print(f"📧 Compiling digest for user: {user_email}")
    
    db = SessionLocal()
    try:
        # Get user from database
        user = db.query(User).filter(User.email == user_email).first()
        if not user or not user.digest_enabled:
            print(f"⚠️ User {user_email} not found or digest disabled")
            return {"status": "skipped", "reason": "User not found or digest disabled"}
        
        # Get pending task IDs
        pending_tasks = json.loads(user.pending_digest_tasks or "[]")
        if not pending_tasks:
            print(f"⚠️ No pending tasks for user {user_email}")
            return {"status": "skipped", "reason": "No pending tasks"}
        
        # Gather completed analysis results
        successful_results = []
        for task_id in pending_tasks:
            task = db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()
            if task and task.status == TaskStatus.COMPLETED and task.result:
                try:
                    result_data = json.loads(task.result)
                    successful_results.append(result_data)
                except json.JSONDecodeError:
                    print(f"⚠️ Failed to parse result for task {task_id}")
        
        if not successful_results:
            print(f"⚠️ No successful analysis results for user {user_email}")
            return {"status": "completed", "videos_included": 0}
        
        # Format email content
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
            <h1>Your Daily YouTube Digest</h1>
            <p>{datetime.now().strftime('%B %d, %Y')}</p>
            <hr>
        """
        
        for result in successful_results:
            video_url = result.get("video_url", "#")
            summary = result.get("summary", "Summary not available.")
            chapters = result.get("chapters", [])
            fact_check_results = result.get("fact_check_results", [])
            
            # Extract video title from first line of summary
            title_line = summary.split('\n')[0] if summary else "Video Analysis"
            title = title_line.strip('# ').strip()
            
            email_body += f"""
            <div style="margin-bottom: 30px;">
                <h2><a href="{video_url}" style="color: #1a73e8;">{title}</a></h2>
                <p>{summary}</p>
            """
            
            # Add chapter summaries if available
            if chapters:
                email_body += "<h3>Chapters:</h3><ul>"
                for chapter in chapters[:3]:  # Show first 3 chapters
                    email_body += f"<li><strong>{chapter.get('title', 'Chapter')}</strong>: {chapter.get('chapter_summary', '')[:100]}...</li>"
                email_body += "</ul>"
            
            # Add fact-check results if any issues found
            significant_claims = [fc for fc in fact_check_results if fc.get('false_confidence_score', 0) > 0.5]
            if significant_claims:
                email_body += "<h3>⚠️ Fact Check Alerts:</h3><ul>"
                for claim in significant_claims[:2]:  # Show top 2 claims
                    score = claim.get('false_confidence_score', 0)
                    verdict = "False" if score >= 0.8 else "Possibly False"
                    email_body += f"<li><strong>{verdict}:</strong> {claim.get('claim', '')}</li>"
                email_body += "</ul>"
            
            email_body += "</div><hr>"
        
        email_body += """
            <p style="color: #666; font-size: 14px;">
                This digest was generated by your AI Video Analyzer. 
                <a href="#">Manage preferences</a> | <a href="#">Unsubscribe</a>
            </p>
        </body>
        </html>
        """
        
        # TODO: Implement actual email sending (SendGrid, AWS SES, etc.)
        print("--- EMAIL TO BE SENT ---")
        print(f"To: {user_email}")
        print(f"Subject: Your Daily YouTube Digest - {len(successful_results)} videos analyzed")
        print("Preview: " + email_body[:200] + "...")
        print("-----------------------")
        
        # Update user's last digest sent timestamp
        user.last_digest_sent = datetime.utcnow()
        user.pending_digest_tasks = json.dumps([])  # Clear pending tasks
        db.commit()
        
        print(f"📬 Digest prepared for {user_email} with {len(successful_results)} videos")
        return {"status": "sent", "videos_included": len(successful_results)}
        
    except Exception as e:
        print(f"❌ Error sending digest to {user_email}: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()

# Periodic task setup (if using celery beat)
from celery.schedules import crontab

# Example celery beat schedule (add to your celery config)
CELERY_BEAT_SCHEDULE = {
    'daily-digest': {
        'task': 'compile_and_send_digest',
        'schedule': crontab(hour=8, minute=0),  # Send at 8 AM daily
        'args': ('user@example.com',)  # You'd dynamically get all users
    },
}