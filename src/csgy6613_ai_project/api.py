from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
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
    input_mode: str = "url"  # url | text | upload | highlights | highlights_file | provider_sync
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
    lane: models.LaneType
    source_provider: models.SourceProvider
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


class ItemsLanesResponse(BaseModel):
    lanes: dict[str, list[ContentItemResponse]]
    next_cursor: str | None


class IntegrationProviderResponse(BaseModel):
    provider: models.SourceProvider
    status: str
    supported_media_types: list[models.MediaType]
    ingestion_methods: list[models.IngestionMethod]
    limitations: str


class IntegrationConnectionRequest(BaseModel):
    access_token: str


class IntegrationConnectionResponse(BaseModel):
    connection_id: str
    provider: models.SourceProvider
    status: str


class ReadwiseSyncRequest(BaseModel):
    mode: str = "highlights_export"  # highlights_export | reader_documents
    updated_after: datetime | None = None


class IntegrationSyncStartResponse(BaseModel):
    job_id: str
    status: str


class IntegrationSyncStatusResponse(BaseModel):
    job_id: str
    provider: models.SourceProvider
    mode: str
    status: str
    imported_count: int
    failed_count: int
    last_cursor: str | None
    errors: list[str]


def _is_valid_youtube_url(url: str) -> bool:
    return "youtube.com/watch?v=" in url or "youtu.be/" in url


def _lane_for_media_type(media_type: models.MediaType) -> models.LaneType:
    if media_type == models.MediaType.YOUTUBE_VIDEO:
        return models.LaneType.VIDEO
    if media_type == models.MediaType.PODCAST_EPISODE:
        return models.LaneType.AUDIO
    return models.LaneType.READING


def _default_provider_for_media_type(media_type: models.MediaType) -> models.SourceProvider:
    if media_type == models.MediaType.YOUTUBE_VIDEO:
        return models.SourceProvider.YOUTUBE
    if media_type == models.MediaType.PODCAST_EPISODE:
        return models.SourceProvider.SPOTIFY
    return models.SourceProvider.MANUAL


def _coerce_source_provider(item: models.ContentItem) -> models.SourceProvider:
    metadata = dict(item.extra_metadata or {})
    raw_provider = metadata.get("source_provider")
    if isinstance(raw_provider, str):
        try:
            return models.SourceProvider(raw_provider)
        except Exception:
            pass
    return _default_provider_for_media_type(item.media_type)


def _coerce_summary(payload: Any) -> str | None:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("overall_summary", "summary", "final_summary", "executive_summary", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


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
    summary = (
        _coerce_summary(result.get("summary"))
        or _coerce_summary(result.get("overall_summary"))
        or _coerce_summary(result.get("final_summary"))
    )

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

    if not summary:
        if moments:
            summary = " ".join([m.get("text", "") for m in moments[:2]])[:420]
        elif isinstance(result.get("transcript"), str):
            summary = result["transcript"][:320]

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
    lane = _lane_for_media_type(item.media_type)
    source_provider = _coerce_source_provider(item)
    return {
        "id": item.id,
        "media_type": item.media_type,
        "input_mode": item.input_mode,
        "lane": lane,
        "source_provider": source_provider,
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


def _provider_catalog() -> list[dict[str, Any]]:
    return [
        {
            "provider": models.SourceProvider.YOUTUBE,
            "supported_media_types": [models.MediaType.YOUTUBE_VIDEO],
            "ingestion_methods": [models.IngestionMethod.URL, models.IngestionMethod.OAUTH],
            "limitations": "Liked/watch-history sync depends on YouTube OAuth scopes.",
        },
        {
            "provider": models.SourceProvider.SPOTIFY,
            "supported_media_types": [models.MediaType.PODCAST_EPISODE],
            "ingestion_methods": [models.IngestionMethod.URL],
            "limitations": "Podcast recently-played automation is limited; URL/RSS ingestion is reliable.",
        },
        {
            "provider": models.SourceProvider.READWISE,
            "supported_media_types": [models.MediaType.BOOK_HIGHLIGHTS, models.MediaType.WEB_ARTICLE],
            "ingestion_methods": [models.IngestionMethod.API_TOKEN],
            "limitations": "Requires user token; sync is cursor-based and rate-limited.",
        },
        {
            "provider": models.SourceProvider.KINDLE_EXPORT,
            "supported_media_types": [models.MediaType.BOOK_HIGHLIGHTS],
            "ingestion_methods": [models.IngestionMethod.FILE_UPLOAD, models.IngestionMethod.EMAIL_FORWARD],
            "limitations": "Compliant import via My Clippings or export files.",
        },
        {
            "provider": models.SourceProvider.APPLE_BOOKS_EXPORT,
            "supported_media_types": [models.MediaType.BOOK_HIGHLIGHTS],
            "ingestion_methods": [models.IngestionMethod.FILE_UPLOAD, models.IngestionMethod.EMAIL_FORWARD],
            "limitations": "Compliant import via exports; no direct account scraping.",
        },
        {
            "provider": models.SourceProvider.KOBO_EXPORT,
            "supported_media_types": [models.MediaType.BOOK_HIGHLIGHTS],
            "ingestion_methods": [models.IngestionMethod.FILE_UPLOAD],
            "limitations": "Cloud sync availability varies by book/source.",
        },
        {
            "provider": models.SourceProvider.GOOGLE_PLAY_BOOKS_EXPORT,
            "supported_media_types": [models.MediaType.BOOK_HIGHLIGHTS],
            "ingestion_methods": [models.IngestionMethod.FILE_UPLOAD],
            "limitations": "Import through user-exported files.",
        },
        {
            "provider": models.SourceProvider.INSTAPAPER,
            "supported_media_types": [models.MediaType.WEB_ARTICLE],
            "ingestion_methods": [models.IngestionMethod.FILE_UPLOAD, models.IngestionMethod.URL],
            "limitations": "Best effort import through exports/API where available.",
        },
        {
            "provider": models.SourceProvider.FEEDLY,
            "supported_media_types": [models.MediaType.WEB_ARTICLE],
            "ingestion_methods": [models.IngestionMethod.URL],
            "limitations": "Article extraction quality depends on source HTML quality.",
        },
        {
            "provider": models.SourceProvider.MANUAL,
            "supported_media_types": list(models.MediaType),
            "ingestion_methods": [models.IngestionMethod.URL, models.IngestionMethod.FILE_UPLOAD],
            "limitations": "Manual capture path for any source.",
        },
    ]


def _coerce_media_type_from_readwise(category: str) -> models.MediaType:
    normalized = (category or "").strip().lower()
    if "podcast" in normalized:
        return models.MediaType.PODCAST_EPISODE
    if normalized in {"article", "newsletter", "rss"}:
        return models.MediaType.WEB_ARTICLE
    if normalized in {"video", "youtube"}:
        return models.MediaType.YOUTUBE_VIDEO
    if normalized in {"tweet", "thread", "social"}:
        return models.MediaType.SOCIAL_THREAD
    return models.MediaType.BOOK_HIGHLIGHTS


def _build_readwise_payload_document(document: dict[str, Any]) -> tuple[str, list[str], list[dict[str, Any]], str]:
    highlights = document.get("highlights") if isinstance(document.get("highlights"), list) else []
    highlight_texts: list[str] = []
    moments: list[dict[str, Any]] = []

    for idx, h in enumerate(highlights[:20]):
        if not isinstance(h, dict):
            continue
        text = str(h.get("text") or "").strip()
        if text:
            highlight_texts.append(text)
            moments.append(
                {
                    "label": str(h.get("location") or h.get("highlighted_at") or f"H{idx + 1}"),
                    "text": text[:220],
                }
            )

    raw_text = "\n".join(highlight_texts)[:24000]
    summary, key_points, default_moments = _generate_quick_analysis(raw_text)
    if moments:
        default_moments = moments[:8]

    return summary, key_points[:8], default_moments, raw_text


def _run_readwise_sync_job(job_id: str, mode: str, updated_after: datetime | None):
    db = SessionLocal()
    job = db.query(models.IntegrationSyncJob).filter(models.IntegrationSyncJob.job_id == job_id).first()
    if not job:
        db.close()
        return

    connection = (
        db.query(models.IntegrationConnection)
        .filter(models.IntegrationConnection.provider == models.SourceProvider.READWISE)
        .order_by(models.IntegrationConnection.updated_at.desc())
        .first()
    )

    if not connection:
        job.status = "failed"
        job.error = "Readwise connection not found."
        db.commit()
        db.close()
        return

    token = (connection.config or {}).get("access_token")
    if not token:
        job.status = "failed"
        job.error = "Readwise token missing."
        db.commit()
        db.close()
        return

    imported_count = 0
    failed_count = 0
    errors: list[str] = []
    cursor: str | None = None

    try:
        headers = {"Authorization": f"Token {token}"}
        base_url = "https://readwise.io/api/v2/export/"
        params: dict[str, Any] = {"page_size": 50}
        if updated_after:
            params["updatedAfter"] = updated_after.isoformat()

        while imported_count < 500:
            page_params = dict(params)
            if cursor:
                page_params["pageCursor"] = cursor

            response = requests.get(base_url, headers=headers, params=page_params, timeout=18)
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid Readwise token")
            response.raise_for_status()
            payload = response.json() if response.content else {}

            documents = payload.get("results") if isinstance(payload.get("results"), list) else []
            for doc in documents:
                if not isinstance(doc, dict):
                    continue
                try:
                    media_type = _coerce_media_type_from_readwise(str(doc.get("category") or ""))
                    title = str(doc.get("title") or doc.get("source_title") or "Untitled Readwise Item")
                    source_url = str(doc.get("url") or "") or None
                    author = str(doc.get("author") or "") or None
                    provider_item_id = str(doc.get("id") or "")

                    duplicate = (
                        db.query(models.ContentItem)
                        .filter(models.ContentItem.title == title)
                        .filter(models.ContentItem.source_url == source_url)
                        .filter(models.ContentItem.media_type == media_type)
                        .first()
                    )
                    if duplicate:
                        continue

                    summary, key_points, moments, raw_text = _build_readwise_payload_document(doc)
                    metadata = {
                        "source_provider": models.SourceProvider.READWISE.value,
                        "provider_item_id": provider_item_id,
                        "sync_mode": mode,
                        "analysis": {
                            "summary": summary,
                            "key_points": key_points,
                            "moments": moments,
                        },
                        "item_status": "ready",
                    }

                    content_item = models.ContentItem(
                        media_type=media_type,
                        input_mode="provider_sync",
                        source_url=source_url,
                        title=title,
                        author=author,
                        raw_text=raw_text,
                        extra_metadata=metadata,
                        consumed_at=updated_after,
                    )
                    db.add(content_item)
                    imported_count += 1
                except Exception as item_error:
                    failed_count += 1
                    errors.append(str(item_error))

            db.commit()

            cursor = payload.get("nextPageCursor") if isinstance(payload, dict) else None
            if not cursor:
                break

        job.status = "ready"
        job.result = {
            "imported_count": imported_count,
            "failed_count": failed_count,
            "last_cursor": cursor,
            "errors": errors[:20],
        }
        job.error = None
        db.commit()
    except Exception as sync_error:
        db.rollback()
        job = db.query(models.IntegrationSyncJob).filter(models.IntegrationSyncJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(sync_error)
            job.result = {
                "imported_count": imported_count,
                "failed_count": failed_count,
                "last_cursor": cursor,
                "errors": errors[:20],
            }
            db.commit()
    finally:
        db.close()


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
    allowed_input_modes = {"url", "text", "upload", "highlights", "highlights_file", "provider_sync"}
    if request.input_mode not in allowed_input_modes:
        raise HTTPException(status_code=400, detail=f"Unsupported input_mode '{request.input_mode}'")

    if request.input_mode == "url" and not request.url:
        raise HTTPException(status_code=400, detail="input_mode 'url' requires a url field")
    if request.input_mode in {"text", "highlights"} and not request.raw_text:
        raise HTTPException(status_code=400, detail=f"input_mode '{request.input_mode}' requires raw_text")
    if request.input_mode in {"upload", "highlights_file"} and not (request.metadata or {}).get("upload_id"):
        raise HTTPException(status_code=400, detail=f"input_mode '{request.input_mode}' requires metadata.upload_id")

    if request.media_type == models.MediaType.YOUTUBE_VIDEO and request.url and not _is_valid_youtube_url(request.url):
        raise HTTPException(status_code=400, detail="For youtube_video media_type, provide a valid YouTube URL.")

    raw_text = request.raw_text
    metadata = dict(request.metadata or {})
    raw_provider = metadata.get("source_provider")
    if isinstance(raw_provider, str):
        try:
            metadata["source_provider"] = models.SourceProvider(raw_provider).value
        except Exception:
            metadata["source_provider"] = _default_provider_for_media_type(request.media_type).value
    else:
        metadata["source_provider"] = _default_provider_for_media_type(request.media_type).value

    try:
        if request.input_mode in {"upload", "highlights_file"}:
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


@app.get("/items/lanes", response_model=ItemsLanesResponse)
def list_content_item_lanes(
    db: Session = Depends(get_db),
    q: str | None = None,
    limit: int = 60,
    cursor: str | None = None,
):
    limit = min(max(limit, 1), 200)
    query = db.query(models.ContentItem)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (models.ContentItem.title.ilike(pattern)) |
            (models.ContentItem.raw_text.ilike(pattern)) |
            (models.ContentItem.author.ilike(pattern))
        )

    if cursor and cursor.isdigit():
        query = query.filter(models.ContentItem.id < int(cursor))

    items = query.order_by(models.ContentItem.id.desc()).limit(limit).all()
    lanes: dict[str, list[dict[str, Any]]] = {
        models.LaneType.VIDEO.value: [],
        models.LaneType.AUDIO.value: [],
        models.LaneType.READING.value: [],
    }

    for item in items:
        serialized = _serialize_content_item(item, db)
        lane_value = serialized.get("lane")
        if isinstance(lane_value, models.LaneType):
            lane_key = lane_value.value
        else:
            lane_key = str(lane_value or models.LaneType.READING.value)
        if lane_key not in lanes:
            lane_key = models.LaneType.READING.value
        lanes[lane_key].append(serialized)

    next_cursor = str(items[-1].id) if len(items) == limit else None
    return {"lanes": lanes, "next_cursor": next_cursor}


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


@app.get("/integrations/providers", response_model=list[IntegrationProviderResponse])
def list_integration_providers(db: Session = Depends(get_db)):
    connected_providers = {
        conn.provider
        for conn in db.query(models.IntegrationConnection).filter(models.IntegrationConnection.status == "connected").all()
    }

    providers: list[dict[str, Any]] = []
    for spec in _provider_catalog():
        providers.append(
            {
                "provider": spec["provider"],
                "status": "connected" if spec["provider"] in connected_providers else "available",
                "supported_media_types": spec["supported_media_types"],
                "ingestion_methods": spec["ingestion_methods"],
                "limitations": spec["limitations"],
            }
        )
    return providers


@app.post("/integrations/readwise/connect", response_model=IntegrationConnectionResponse, status_code=201)
def connect_readwise(request: IntegrationConnectionRequest, db: Session = Depends(get_db)):
    token = request.access_token.strip()
    if len(token) < 16:
        raise HTTPException(status_code=400, detail="Readwise access token appears invalid.")

    connection = (
        db.query(models.IntegrationConnection)
        .filter(models.IntegrationConnection.provider == models.SourceProvider.READWISE)
        .first()
    )

    if not connection:
        connection = models.IntegrationConnection(
            connection_id=uuid.uuid4().hex,
            provider=models.SourceProvider.READWISE,
            status="connected",
            config={"access_token": token},
        )
        db.add(connection)
    else:
        connection.status = "connected"
        config = dict(connection.config or {})
        config["access_token"] = token
        connection.config = config

    db.commit()
    db.refresh(connection)
    return {
        "connection_id": connection.connection_id,
        "provider": connection.provider,
        "status": connection.status,
    }


@app.post("/integrations/readwise/sync", response_model=IntegrationSyncStartResponse, status_code=202)
def start_readwise_sync(
    request: ReadwiseSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    mode = request.mode.strip()
    if mode not in {"highlights_export", "reader_documents"}:
        raise HTTPException(status_code=400, detail="mode must be one of: highlights_export, reader_documents")

    connection = (
        db.query(models.IntegrationConnection)
        .filter(models.IntegrationConnection.provider == models.SourceProvider.READWISE)
        .filter(models.IntegrationConnection.status == "connected")
        .order_by(models.IntegrationConnection.updated_at.desc())
        .first()
    )
    if not connection:
        raise HTTPException(status_code=400, detail="Connect Readwise before starting sync.")

    job_id = uuid.uuid4().hex
    sync_job = models.IntegrationSyncJob(
        job_id=job_id,
        provider=models.SourceProvider.READWISE,
        mode=mode,
        status="processing",
        request_payload={
            "updated_after": request.updated_after.isoformat() if request.updated_after else None,
        },
        result={"imported_count": 0, "failed_count": 0, "last_cursor": None, "errors": []},
    )
    db.add(sync_job)
    db.commit()

    background_tasks.add_task(_run_readwise_sync_job, job_id, mode, request.updated_after)
    return {"job_id": job_id, "status": "processing"}


@app.get("/integrations/sync-jobs/{job_id}", response_model=IntegrationSyncStatusResponse)
def get_sync_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(models.IntegrationSyncJob).filter(models.IntegrationSyncJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")

    result = dict(job.result or {})
    errors = result.get("errors")
    if not isinstance(errors, list):
        errors = []

    return {
        "job_id": job.job_id,
        "provider": job.provider,
        "mode": job.mode,
        "status": job.status,
        "imported_count": int(result.get("imported_count") or 0),
        "failed_count": int(result.get("failed_count") or 0),
        "last_cursor": result.get("last_cursor"),
        "errors": [str(e) for e in errors],
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
