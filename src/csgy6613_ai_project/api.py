from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
import uuid
import json
import os
import requests
from urllib.parse import urlencode
import asyncio
from datetime import datetime
import traceback

from .database import SessionLocal, engine
from . import models
from .tasks import run_analysis_pipeline

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Content Analyzer API",
    description="AI-powered video content analysis with rate limiting",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AnalysisRequest(BaseModel):
    url: HttpUrl  # Use HttpUrl for automatic URL validation

class AnalysisResponse(BaseModel):
    task_id: str
    message: str
    estimated_completion_time: str

class StatusResponse(BaseModel):
    task_id: str
    status: models.TaskStatus
    result: dict | None
    progress: dict | None
    estimated_time_remaining: str | None

class ProgressUpdate(BaseModel):
    step: str
    current_step: int
    total_steps: int
    message: str
    timestamp: str

@app.get("/", include_in_schema=False)
def read_root():
    """
    Redirects the root URL to the YouTube connection page to start the user flow.
    """
    return RedirectResponse(url="/connect/youtube")

@app.post("/analyze", response_model=AnalysisResponse, status_code=202)
def analyze_content(request: AnalysisRequest, db: Session = Depends(get_db)):
    """
    This endpoint accepts a URL for analysis, creates a task record in the DB,
    and dispatches the job to the Celery worker queue.
    
    Note: Due to API rate limiting, analysis takes approximately 3-5 minutes.
    """
    task_id = str(uuid.uuid4())
    
    try:
        # Create task with initial progress tracking
        initial_progress = {
            "current_step": 0,
            "total_steps": 6,
            "steps": [
                "Queued",
                "Fetching video transcript",
                "Segmenting into chapters", 
                "Generating summaries",
                "Extracting claims",
                "Fact-checking",
                "Complete"
            ],
            "estimated_completion": "3-5 minutes",
            "started_at": datetime.utcnow().isoformat()
        }
        
        # Log the incoming request
        print(f"📥 Received analysis request for URL: {request.url}")
        
        try:
            db_task = models.AnalysisTask(
                task_id=task_id, 
                status=models.TaskStatus.PENDING,
                progress=json.dumps(initial_progress)
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            print(f"✅ Created task {task_id} in database")
        except Exception as db_error:
            print(f"❌ Database error: {db_error}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")

        try:
            # Convert Pydantic HttpUrl to string for Celery task
            youtube_url = str(request.url)
            
            # Dispatch to Celery
            result = run_analysis_pipeline.delay(task_id=task_id, youtube_url=youtube_url)
            print(f"📤 Dispatched task {task_id} to Celery queue")
            
        except Exception as celery_error:
            print(f"❌ Celery error: {celery_error}")
            traceback.print_exc()
            # Update task status to failed
            db_task.status = models.TaskStatus.FAILED
            db_task.error_message = str(celery_error)
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(celery_error)}")

        return {
            "task_id": task_id, 
            "message": "Analysis has been queued. Processing will take 3-5 minutes due to API rate limiting.",
            "estimated_completion_time": "3-5 minutes"
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Unexpected error in /analyze endpoint: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/status/{task_id}", response_model=StatusResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """
    This endpoint allows the frontend to poll for the status and result of a task.
    Includes progress tracking and estimated time remaining.
    """
    task = db.query(models.AnalysisTask).filter(models.AnalysisTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result_data = None
    progress_data = None
    estimated_time = None
    
    # Parse result data
    if task.result:
        try:
            if isinstance(task.result, str):
                result_data = json.loads(task.result)
            else:
                result_data = task.result
        except json.JSONDecodeError:
            result_data = {"raw_result": str(task.result)}
    
    # Parse progress data
    if task.progress:
        try:
            if isinstance(task.progress, str):
                progress_data = json.loads(task.progress)
            else:
                progress_data = task.progress
                
            # Calculate estimated time remaining (check for RUNNING status)
            if progress_data and task.status == models.TaskStatus.RUNNING:
                current_step = progress_data.get("current_step", 0)
                total_steps = progress_data.get("total_steps", 6)
                if current_step < total_steps:
                    remaining_steps = total_steps - current_step
                    avg_time_per_step = 50  # seconds, conservative estimate
                    estimated_seconds = remaining_steps * avg_time_per_step
                    estimated_time = f"{estimated_seconds // 60}m {estimated_seconds % 60}s"
                    
        except json.JSONDecodeError:
            progress_data = None

    return {
        "task_id": task.task_id, 
        "status": task.status, 
        "result": result_data,
        "progress": progress_data,
        "estimated_time_remaining": estimated_time
    }

@app.put("/status/{task_id}/progress")
def update_task_progress(
    task_id: str, 
    progress: ProgressUpdate, 
    db: Session = Depends(get_db)
):
    """
    Internal endpoint for Celery workers to update task progress.
    """
    task = db.query(models.AnalysisTask).filter(models.AnalysisTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        # Update progress data
        progress_data = {
            "current_step": progress.current_step,
            "total_steps": progress.total_steps,
            "current_step_name": progress.step,
            "message": progress.message,
            "last_updated": progress.timestamp
        }
        
        task.progress = json.dumps(progress_data)
        
        # Update status if needed (using correct enum values)
        if progress.current_step == 0:
            task.status = models.TaskStatus.PENDING
        elif progress.current_step > 0 and progress.current_step < progress.total_steps:
            task.status = models.TaskStatus.RUNNING
        elif progress.current_step >= progress.total_steps:
            task.status = models.TaskStatus.COMPLETED
            
        db.commit()
        return {"status": "success", "message": "Progress updated"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update progress: {str(e)}")

@app.get("/test-db")
def test_database(db: Session = Depends(get_db)):
    """Test database connection and show task status values"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        
        # Get enum values from database
        result = db.execute("SELECT unnest(enum_range(NULL::taskstatus))")
        db_enum_values = [row[0] for row in result]
        
        # Test if tables exist
        task_count = db.query(models.AnalysisTask).count()
        user_count = db.query(models.User).count()
        
        # Get Python enum values
        python_enum_values = [status.value for status in models.TaskStatus]
        
        return {
            "status": "connected",
            "tasks": task_count,
            "users": user_count,
            "database_enum_values": db_enum_values,
            "python_enum_values": python_enum_values,
            "enum_match": set(db_enum_values) == set(python_enum_values)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/connect/youtube")
def connect_youtube_account():
    """
    Step 1 of OAuth: Redirects the user to Google's consent screen.
    """
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    if not client_id:
        raise HTTPException(status_code=500, detail="Google Client ID not configured")
    
    # Add profile scope to access user info
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": "http://127.0.0.1:8000/auth/youtube/callback",
        "scope": "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
        "access_type": "offline",
        "prompt": "consent"  # Important to get a refresh token every time
    }
    
    auth_redirect_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(auth_redirect_url)

@app.get("/auth/youtube/callback")
def youtube_auth_callback(code: str, db: Session = Depends(get_db)):
    """
    Step 2 of OAuth: Google redirects here after user gives consent.
    We exchange the code for tokens and save them.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth credentials not configured")
    
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "http://127.0.0.1:8000/auth/youtube/callback",
        "grant_type": "authorization_code",
    }
    
    try:
        response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
        response.raise_for_status()
        token_info = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange code for tokens: {str(e)}")

    if "error" in token_info:
        raise HTTPException(status_code=400, detail=token_info.get("error_description", "OAuth error"))

    # Get user profile information to identify the user
    access_token = token_info.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received")
    
    # Method 1: Try using the v3 userinfo endpoint
    try:
        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
    except requests.RequestException as e:
        # Fallback Method 2: Try decoding the ID token if available
        id_token = token_info.get("id_token")
        if id_token:
            try:
                import base64
                import json
                
                # Decode the ID token (skip signature verification for simplicity)
                # Note: In production, you should verify the signature
                token_parts = id_token.split('.')
                if len(token_parts) >= 2:
                    # Add padding if needed
                    payload = token_parts[1]
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += '=' * padding
                    
                    decoded_payload = base64.urlsafe_b64decode(payload)
                    user_info = json.loads(decoded_payload)
                else:
                    raise ValueError("Invalid ID token format")
            except (ValueError, json.JSONDecodeError) as decode_error:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to get user info from userinfo endpoint and ID token: {str(e)}, {str(decode_error)}"
                )
        else:
            raise HTTPException(status_code=500, detail=f"Failed to get user info: {str(e)}")
    
    user_email = user_info.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="Could not retrieve user email from user info")

    # Create or update the user record based on email
    try:
        user = db.query(models.User).filter(models.User.email == user_email).first()
        if not user:
            user = models.User(email=user_email)
            db.add(user)
        
        user.youtube_refresh_token = token_info.get("refresh_token")
        user.digest_enabled = True
        db.commit()
        
        # Return a success page with rate limiting information
        success_html = f"""
        <html>
        <head><title>YouTube Connected Successfully</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h1 style="color: #4CAF50;">✅ Successfully Connected!</h1>
            <p><strong>Account:</strong> {user_email}</p>
            <p>Your YouTube account has been successfully connected to the AI Content Analyzer.</p>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>⚠️ Important Rate Limiting Information:</h3>
                <ul>
                    <li>Video analysis now takes <strong>3-5 minutes</strong> per video</li>
                    <li>This is due to API quota restrictions on the free tier</li>
                    <li>The system automatically manages rate limits for reliable processing</li>
                    <li>Daily digest emails will continue to work normally</li>
                </ul>
            </div>
            
            <p><strong>✅ Digest emails:</strong> Enabled</p>
            <p>You will receive daily video digest emails with AI-powered summaries.</p>
            
            <p style="margin-top: 30px;">
                <a href="/health" style="color: #007bff;">Check API Health</a> | 
                <a href="/docs" style="color: #007bff;">View API Documentation</a>
            </p>
        </body>
        </html>
        """
        
        return HTMLResponse(content=success_html)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/users/{user_email}/toggle-digest")
def toggle_digest_setting(user_email: str, enabled: bool, db: Session = Depends(get_db)):
    """
    Allows users to enable/disable their digest emails.
    """
    user = db.query(models.User).filter(models.User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        user.digest_enabled = enabled
        db.commit()
        
        status_text = "enabled" if enabled else "disabled"
        return {
            "status": "success", 
            "message": f"Digest emails {status_text} for {user_email}",
            "note": "Analysis is rate-limited to 3-5 minutes per video on free tier"
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update digest setting: {str(e)}")

@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    """
    try:
        # Test database connection
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Check environment variables
        env_status = {
            "gemini_api_key": "✅" if os.getenv("GEMINI_API_KEY") else "❌",
            "serper_api_key": "✅" if os.getenv("SERPER_API_KEY") else "❌",
            "google_oauth": "✅" if (os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")) else "❌"
        }
        
        return {
            "status": "healthy",
            "database": "connected",
            "service": "Content Analyzer API v2.0",
            "rate_limiting": "active",
            "processing_time": "3-5 minutes per video",
            "environment": env_status,
            "api_quotas": {
                "gemini": "Free tier - 50 requests/day",
                "note": "Upgrade to paid tier for faster processing"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "unhealthy", 
                "database": "disconnected",
                "error": str(e)
            }
        )

@app.get("/api-usage")
def get_api_usage_info():
    """
    Provides information about current API usage and rate limiting.
    """
    return {
        "current_tier": "Free",
        "rate_limits": {
            "gemini_flash": "15 requests/minute",
            "gemini_pro": "10 requests/minute", 
            "serper_search": "Limited to 2 queries per claim"
        },
        "processing_time": {
            "estimated": "3-5 minutes",
            "factors": [
                "API rate limiting",
                "Queue processing delays",
                "Video length and complexity"
            ]
        },
        "optimization_tips": [
            "Upgrade to paid Gemini API for faster processing",
            "Use shorter videos for quicker analysis",
            "Process videos during off-peak hours"
        ]
    }