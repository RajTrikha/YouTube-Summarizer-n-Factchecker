from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid
import json
import os
import requests
from urllib.parse import urlencode
from datetime import datetime
from typing import Any, Optional
from csgy6613_ai_project.database import SessionLocal, engine

from . import models
from .tasks import run_analysis_pipeline

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Content Analyzer API")

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
    url: str

class AnalysisResponse(BaseModel):
    task_id: str
    message: str

class StatusResponse(BaseModel):
    task_id: str
    status: models.TaskStatus
    result: dict | None


class IngestRequest(BaseModel):
    media_type: models.MediaType
    input_mode: str = "url"
    url: Optional[str] = None
    raw_text: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    consumed_at: Optional[datetime] = None
    metadata: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    item_id: int
    task_id: str | None
    status: str
    message: str


class ContentItemResponse(BaseModel):
    id: int
    media_type: models.MediaType
    input_mode: str
    source_url: str | None
    title: str | None
    author: str | None
    consumed_at: datetime | None
    created_at: datetime | None
    metadata: dict[str, Any] | None


def _is_valid_youtube_url(url: str) -> bool:
    return "youtube.com/watch?v=" in url or "youtu.be/" in url


def _serialize_content_item(item: models.ContentItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "media_type": item.media_type,
        "input_mode": item.input_mode,
        "source_url": item.source_url,
        "title": item.title,
        "author": item.author,
        "consumed_at": item.consumed_at,
        "created_at": item.created_at,
        "metadata": item.extra_metadata,
    }

@app.post("/analyze", response_model=AnalysisResponse, status_code=202)
def analyze_content(request: AnalysisRequest, db: Session = Depends(get_db)):
    """
    This endpoint accepts a URL for analysis, creates a task record in the DB,
    and dispatches the job to the Celery worker queue.
    """
    task_id = str(uuid.uuid4())
    try:
        db_task = models.AnalysisTask(task_id=task_id, status=models.TaskStatus.PENDING)
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during task creation: {str(e)}")

    run_analysis_pipeline.delay(task_id=task_id, youtube_url=request.url)

    return {"task_id": task_id, "message": "Analysis has been queued."}


@app.post("/ingest", response_model=IngestResponse, status_code=202)
def ingest_content(request: IngestRequest, db: Session = Depends(get_db)):
    """
    Cross-media ingestion endpoint.
    In this slice, only YouTube media_type is queued for analysis.
    Other media types are stored for the upcoming generalized pipeline.
    """
    if request.input_mode == "url" and not request.url:
        raise HTTPException(status_code=400, detail="input_mode 'url' requires a url field")
    if request.input_mode in {"text", "highlights"} and not request.raw_text:
        raise HTTPException(status_code=400, detail=f"input_mode '{request.input_mode}' requires raw_text")

    if request.media_type == models.MediaType.YOUTUBE_VIDEO and request.url and not _is_valid_youtube_url(request.url):
        raise HTTPException(status_code=400, detail="For youtube_video media_type, provide a valid YouTube URL.")

    content_item = models.ContentItem(
        media_type=request.media_type,
        input_mode=request.input_mode,
        source_url=request.url,
        title=request.title,
        author=request.author,
        raw_text=request.raw_text,
        extra_metadata=request.metadata or {},
        consumed_at=request.consumed_at,
    )

    try:
        db.add(content_item)
        db.commit()
        db.refresh(content_item)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during content ingestion: {str(e)}")

    # Queue current pipeline only for YouTube in this non-breaking foundation slice.
    if request.media_type == models.MediaType.YOUTUBE_VIDEO and request.url:
        task_id = str(uuid.uuid4())
        try:
            db_task = models.AnalysisTask(task_id=task_id, status=models.TaskStatus.PENDING)
            db.add(db_task)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error during task creation: {str(e)}")

        run_analysis_pipeline.delay(
            task_id=task_id,
            youtube_url=request.url,
            video_title=request.title
        )

        return {
            "item_id": content_item.id,
            "task_id": task_id,
            "status": "QUEUED",
            "message": "Content ingested and analysis has been queued.",
        }

    return {
        "item_id": content_item.id,
        "task_id": None,
        "status": "INGESTED_ONLY",
        "message": "Content ingested. Analysis queueing for this media type will be added in the next slice.",
    }

@app.get("/status/{task_id}", response_model=StatusResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """
    This endpoint allows the frontend to poll for the status and result of a task.
    """
    task = db.query(models.AnalysisTask).filter(models.AnalysisTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result_data = None
    if bool(task.result):
        if isinstance(task.result, str):
            result_data = json.loads(task.result)
        else:
            result_data = task.result

    return {"task_id": task.task_id, "status": task.status, "result": result_data}


@app.get("/items", response_model=list[ContentItemResponse])
def list_content_items(
    db: Session = Depends(get_db),
    media_type: models.MediaType | None = None,
    limit: int = 50,
):
    limit = min(max(limit, 1), 200)
    query = db.query(models.ContentItem)
    if media_type:
        query = query.filter(models.ContentItem.media_type == media_type)
    items = query.order_by(models.ContentItem.created_at.desc()).limit(limit).all()
    return [_serialize_content_item(item) for item in items]


@app.get("/items/{item_id}", response_model=ContentItemResponse)
def get_content_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.ContentItem).filter(models.ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    return _serialize_content_item(item)

@app.get("/", include_in_schema=False)
def read_root():
    """Redirects the root URL to the YouTube connection page."""
    return RedirectResponse(url="/connect/youtube")

@app.get("/connect/youtube")
def connect_youtube_account():
    """Step 1 of OAuth: Redirects the user to Google's consent screen."""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": "http://127.0.0.1:8000/auth/youtube/callback",
        "scope": "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/userinfo.email",
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_redirect_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(auth_redirect_url)

@app.get("/auth/youtube/callback", response_class=HTMLResponse)
def youtube_auth_callback(code: str, db: Session = Depends(get_db)):
    """Step 2 of OAuth: Exchanges the code for tokens and saves them."""
    token_data = {
        "code": code,
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": "http://127.0.0.1:8000/auth/youtube/callback",
        "grant_type": "authorization_code",
    }
    response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
    token_info = response.json()

    if "error" in token_info:
        raise HTTPException(status_code=400, detail=token_info.get("error_description"))

    access_token = token_info.get("access_token")
    user_info_response = requests.get(
        "https://www.googleapis.com/oauth2/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_email = user_info_response.json().get("email")

    if not user_email:
        raise HTTPException(status_code=400, detail="Could not get user email.")

    try:
        user = db.query(models.User).filter(models.User.email == user_email).first()
        if not user:
            user = models.User(email=user_email)
            db.add(user)
        setattr(user, "digest_enabled", True)
        user.youtube_refresh_token = token_info.get("refresh_token")
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during OAuth callback: {str(e)}")
    
    return f"<h1>✅ Success!</h1><p>YouTube account for {user_email} has been connected. You can now close this window.</p>"

# Optional: Add a health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}
