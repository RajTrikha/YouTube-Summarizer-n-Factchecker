from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json
import os
import re
import uuid
import requests
from html import unescape
from urllib.parse import urlencode
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from csgy6613_ai_project.database import SessionLocal, engine

from . import models
from .tasks import run_analysis_pipeline

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Content Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("/tmp/tom_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
    input_mode: str = "url"  # url | text | upload | highlights
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


class UploadResponse(BaseModel):
    upload_id: str
    mime_type: str
    size: int


class ItemUpdateRequest(BaseModel):
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    tags: Optional[list[str]] = None
    collections: Optional[list[str]] = None


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
    item_status: str
    task_id: str | None
    summary: str | None
    key_points: list[str]
    moments: list[dict[str, Any]]


class MemoryQueryRequest(BaseModel):
    query: str
    limit: int = 5
    media_types: list[models.MediaType] | None = None


class MemoryCitation(BaseModel):
    item_id: int
    title: str
    media_type: models.MediaType
    snippet: str
    source_url: str | None


class MemoryQueryResponse(BaseModel):
    answer: str
    citations: list[MemoryCitation]


def _is_valid_youtube_url(url: str) -> bool:
    return "youtube.com/watch?v=" in url or "youtu.be/" in url


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[\\s\\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def _extract_text_from_url(url: str) -> str:
    response = requests.get(url, timeout=12)
    response.raise_for_status()
    text = _strip_html(response.text)
    return text[:24000]


def _extract_pdf_text(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("PDF parsing support is unavailable. Install 'pypdf'.")
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages[:20]:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text)
    return "\n".join(pages)[:24000]


def _extract_upload_text(upload_id: str) -> str:
    path = UPLOAD_DIR / upload_id
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Upload not found")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)

    data = path.read_bytes()
    try:
        return data.decode("utf-8", errors="ignore")[:24000]
    except Exception:
        return ""


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _generate_quick_analysis(text: str) -> tuple[str, list[str], list[dict[str, Any]]]:
    clean = (text or "").strip()
    if not clean:
        return (
            "No readable content was extracted yet. You can still keep this source in your inbox.",
            [],
            [],
        )

    sentences = _split_sentences(clean)
    summary = " ".join(sentences[:3])
    key_points = sentences[:5]
    moments = [
        {
            "label": f"Moment {idx + 1}",
            "text": sentence[:220],
        }
        for idx, sentence in enumerate(sentences[:5])
    ]
    return summary, key_points, moments


def _extract_analysis_from_task_result(result: dict[str, Any]) -> tuple[str | None, list[str], list[dict[str, Any]]]:
    summary = result.get("summary")
    if isinstance(summary, dict):
        summary = summary.get("overall_summary")
    if not isinstance(summary, str):
        summary = None

    key_points: list[str] = []
    moments: list[dict[str, Any]] = []

    chapters = result.get("chapters") or []
    if isinstance(chapters, list):
        for chapter in chapters[:8]:
            if not isinstance(chapter, dict):
                continue
            chapter_points = chapter.get("key_points") or []
            if isinstance(chapter_points, list):
                for point in chapter_points:
                    if isinstance(point, str) and point.strip() and point not in key_points:
                        key_points.append(point.strip())
            label = chapter.get("formatted_time") or chapter.get("start_time") or ""
            text = chapter.get("chapter_summary") or chapter.get("summary") or ""
            if text:
                moments.append({"label": str(label), "text": str(text)[:220]})

    return summary, key_points[:8], moments[:8]


def _task_status_to_item_status(task_status: models.TaskStatus) -> str:
    if task_status == models.TaskStatus.SUCCESS:
        return "ready"
    if task_status in {models.TaskStatus.PENDING, models.TaskStatus.PROCESSING}:
        return "processing"
    return "failed"


def _enrich_item_runtime(item: models.ContentItem, db: Session) -> dict[str, Any]:
    metadata = dict(item.extra_metadata or {})
    task_id = metadata.get("task_id")

    item_status = metadata.get("item_status", "ingested")
    summary = None
    key_points: list[str] = []
    moments: list[dict[str, Any]] = []

    analysis_blob = metadata.get("analysis") if isinstance(metadata.get("analysis"), dict) else {}
    if analysis_blob:
        summary = analysis_blob.get("summary") if isinstance(analysis_blob.get("summary"), str) else None
        key_points = [p for p in analysis_blob.get("key_points", []) if isinstance(p, str)]
        moments = [m for m in analysis_blob.get("moments", []) if isinstance(m, dict)]

    if task_id:
        task = db.query(models.AnalysisTask).filter(models.AnalysisTask.task_id == task_id).first()
        if task:
            item_status = _task_status_to_item_status(task.status)
            if task.status == models.TaskStatus.SUCCESS and isinstance(task.result, dict):
                t_summary, t_points, t_moments = _extract_analysis_from_task_result(task.result)
                summary = t_summary or summary
                key_points = t_points or key_points
                moments = t_moments or moments
            elif task.status == models.TaskStatus.FAILURE:
                err = task.result.get("error") if isinstance(task.result, dict) else "Analysis failed"
                summary = summary or f"Analysis failed: {err}"

    return {
        "item_status": item_status,
        "task_id": task_id,
        "summary": summary,
        "key_points": key_points,
        "moments": moments,
        "metadata": metadata,
    }


def _serialize_content_item(item: models.ContentItem, db: Session) -> dict[str, Any]:
    enriched = _enrich_item_runtime(item, db)
    return {
        "id": item.id,
        "media_type": item.media_type,
        "input_mode": item.input_mode,
        "source_url": item.source_url,
        "title": item.title,
        "author": item.author,
        "consumed_at": item.consumed_at,
        "created_at": item.created_at,
        "metadata": enriched["metadata"],
        "item_status": enriched["item_status"],
        "task_id": enriched["task_id"],
        "summary": enriched["summary"],
        "key_points": enriched["key_points"],
        "moments": enriched["moments"],
    }


def _snippet_for_query(text: str, query_terms: list[str]) -> str:
    if not text:
        return ""
    lower = text.lower()
    start = 0
    for term in query_terms:
        idx = lower.find(term)
        if idx != -1:
            start = max(0, idx - 90)
            break
    snippet = text[start:start + 240].strip()
    return snippet


@app.post("/analyze", response_model=AnalysisResponse, status_code=202)
def analyze_content(request: AnalysisRequest, db: Session = Depends(get_db)):
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


@app.post("/uploads", response_model=UploadResponse, status_code=201)
async def upload_source_file(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Max size is 25MB.")

    suffix = Path(file.filename or "").suffix.lower()
    upload_id = f"{uuid.uuid4().hex}{suffix}"
    path = UPLOAD_DIR / upload_id
    path.write_bytes(content)

    return {
        "upload_id": upload_id,
        "mime_type": file.content_type or "application/octet-stream",
        "size": len(content),
    }


@app.post("/ingest", response_model=IngestResponse, status_code=202)
def ingest_content(request: IngestRequest, db: Session = Depends(get_db)):
    if request.input_mode == "url" and not request.url:
        raise HTTPException(status_code=400, detail="input_mode 'url' requires a url field")
    if request.input_mode in {"text", "highlights"} and not request.raw_text:
        raise HTTPException(status_code=400, detail=f"input_mode '{request.input_mode}' requires raw_text")
    if request.input_mode == "upload" and not (request.metadata or {}).get("upload_id"):
        raise HTTPException(status_code=400, detail="input_mode 'upload' requires metadata.upload_id")

    if request.media_type == models.MediaType.YOUTUBE_VIDEO and request.url and not _is_valid_youtube_url(request.url):
        raise HTTPException(status_code=400, detail="For youtube_video media_type, provide a valid YouTube URL.")

    raw_text = request.raw_text
    metadata = dict(request.metadata or {})

    try:
        if request.input_mode == "upload":
            upload_id = str(metadata.get("upload_id"))
            raw_text = _extract_upload_text(upload_id)
        elif request.input_mode == "url" and request.url and request.media_type != models.MediaType.YOUTUBE_VIDEO:
            raw_text = _extract_text_from_url(request.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not extract content: {str(e)}")

    title = request.title
    if not title and request.url:
        title = request.url

    if request.media_type == models.MediaType.YOUTUBE_VIDEO:
        metadata["item_status"] = "processing"
    else:
        summary, key_points, moments = _generate_quick_analysis(raw_text or "")
        metadata["analysis"] = {
            "summary": summary,
            "key_points": key_points,
            "moments": moments,
        }
        metadata["item_status"] = "ready"

    content_item = models.ContentItem(
        media_type=request.media_type,
        input_mode=request.input_mode,
        source_url=request.url,
        title=title,
        author=request.author,
        raw_text=raw_text,
        extra_metadata=metadata,
        consumed_at=request.consumed_at,
    )

    try:
        db.add(content_item)
        db.commit()
        db.refresh(content_item)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during content ingestion: {str(e)}")

    if request.media_type == models.MediaType.YOUTUBE_VIDEO and request.url:
        task_id = str(uuid.uuid4())
        try:
            db_task = models.AnalysisTask(task_id=task_id, status=models.TaskStatus.PENDING)
            db.add(db_task)
            db.commit()

            updated_metadata = dict(content_item.extra_metadata or {})
            updated_metadata["task_id"] = task_id
            content_item.extra_metadata = updated_metadata
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error during task creation: {str(e)}")

        run_analysis_pipeline.delay(
            task_id=task_id,
            youtube_url=request.url,
            video_title=request.title,
            content_item_id=content_item.id,
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
        "status": "READY",
        "message": "Content ingested and summarized.",
    }


@app.get("/status/{task_id}", response_model=StatusResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db)):
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
    q: str | None = None,
    limit: int = 50,
):
    limit = min(max(limit, 1), 200)
    query = db.query(models.ContentItem)

    if media_type:
        query = query.filter(models.ContentItem.media_type == media_type)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (models.ContentItem.title.ilike(pattern)) |
            (models.ContentItem.raw_text.ilike(pattern)) |
            (models.ContentItem.author.ilike(pattern))
        )

    items = query.order_by(models.ContentItem.created_at.desc()).limit(limit).all()
    return [_serialize_content_item(item, db) for item in items]


@app.get("/items/{item_id}", response_model=ContentItemResponse)
def get_content_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.ContentItem).filter(models.ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    return _serialize_content_item(item, db)


@app.patch("/items/{item_id}", response_model=ContentItemResponse)
def update_content_item(item_id: int, request: ItemUpdateRequest, db: Session = Depends(get_db)):
    item = db.query(models.ContentItem).filter(models.ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    metadata = dict(item.extra_metadata or {})
    if request.pinned is not None:
        metadata["pinned"] = request.pinned
    if request.archived is not None:
        metadata["archived"] = request.archived
    if request.tags is not None:
        metadata["tags"] = [t.strip() for t in request.tags if t and t.strip()]
    if request.collections is not None:
        metadata["collections"] = [c.strip() for c in request.collections if c and c.strip()]

    item.extra_metadata = metadata
    db.commit()
    db.refresh(item)
    return _serialize_content_item(item, db)


@app.post("/memory/query", response_model=MemoryQueryResponse)
def memory_query(request: MemoryQueryRequest, db: Session = Depends(get_db)):
    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="query is required")

    limit = min(max(request.limit, 1), 10)
    query = db.query(models.ContentItem)
    if request.media_types:
        query = query.filter(models.ContentItem.media_type.in_(request.media_types))
    items = query.order_by(models.ContentItem.created_at.desc()).limit(300).all()

    terms = [t for t in re.findall(r"[a-zA-Z0-9]+", query_text.lower()) if len(t) > 2]

    scored: list[tuple[int, models.ContentItem, str, str]] = []
    for item in items:
        enriched = _enrich_item_runtime(item, db)
        source_text = " ".join(
            [
                item.title or "",
                enriched.get("summary") or "",
                item.raw_text or "",
                " ".join(enriched.get("key_points", [])),
            ]
        ).strip()
        if not source_text:
            continue

        lower = source_text.lower()
        score = sum(lower.count(term) for term in terms) if terms else 0
        if score > 0:
            snippet = _snippet_for_query(source_text, terms)
            scored.append((score, item, snippet, enriched.get("summary") or ""))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    if not top:
        return {
            "answer": "I could not find strong matches yet. Add more sources or refine your question.",
            "citations": [],
        }

    citations: list[dict[str, Any]] = []
    answer_lines: list[str] = ["Here is what your personal library says:"]
    for idx, (_, item, snippet, fallback_summary) in enumerate(top, start=1):
        title = item.title or f"Item {item.id}"
        answer_chunk = fallback_summary or snippet or "Relevant information found."
        answer_lines.append(f"{idx}. {title}: {answer_chunk[:220]}")
        citations.append(
            {
                "item_id": item.id,
                "title": title,
                "media_type": item.media_type,
                "snippet": snippet or answer_chunk[:220],
                "source_url": item.source_url,
            }
        )

    return {
        "answer": "\n".join(answer_lines),
        "citations": citations,
    }


@app.get("/", include_in_schema=False)
def read_root():
    return RedirectResponse(url="/connect/youtube")


@app.get("/connect/youtube")
def connect_youtube_account():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": "http://127.0.0.1:8000/auth/youtube/callback",
        "scope": "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/userinfo.email",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_redirect_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(auth_redirect_url)


@app.get("/auth/youtube/callback", response_class=HTMLResponse)
def youtube_auth_callback(code: str, db: Session = Depends(get_db)):
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
        headers={"Authorization": f"Bearer {access_token}"},
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


@app.get("/health")
def health_check():
    return {"status": "healthy"}
