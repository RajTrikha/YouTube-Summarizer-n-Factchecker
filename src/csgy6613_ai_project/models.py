from sqlalchemy import Column, String, JSON, Integer, Enum, Boolean, DateTime, Text
from sqlalchemy.sql import func
from .database import Base
import enum

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class MediaType(str, enum.Enum):
    YOUTUBE_VIDEO = "youtube_video"
    PODCAST_EPISODE = "podcast_episode"
    WEB_ARTICLE = "web_article"
    PDF_DOCUMENT = "pdf_document"
    BOOK_HIGHLIGHTS = "book_highlights"
    SOCIAL_THREAD = "social_thread"


class SourceProvider(str, enum.Enum):
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    RSS = "rss"
    READWISE = "readwise"
    KINDLE_EXPORT = "kindle_export"
    APPLE_BOOKS_EXPORT = "apple_books_export"
    KOBO_EXPORT = "kobo_export"
    GOOGLE_PLAY_BOOKS_EXPORT = "google_play_books_export"
    INSTAPAPER = "instapaper"
    FEEDLY = "feedly"
    MANUAL = "manual"


class IngestionMethod(str, enum.Enum):
    OAUTH = "oauth"
    API_TOKEN = "api_token"
    FILE_UPLOAD = "file_upload"
    EMAIL_FORWARD = "email_forward"
    URL = "url"


class LaneType(str, enum.Enum):
    VIDEO = "video"
    AUDIO = "audio"
    READING = "reading"

class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    result = Column(JSON, nullable=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # In a real app, this should always be encrypted.
    youtube_refresh_token = Column(String, nullable=True)
    digest_enabled = Column(Boolean, default=False)


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(Integer, primary_key=True, index=True)
    media_type = Column(Enum(MediaType), nullable=False, index=True)
    input_mode = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(String, unique=True, index=True, nullable=False)
    provider = Column(Enum(SourceProvider), index=True, nullable=False)
    status = Column(String, nullable=False, default="connected")
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class IntegrationSyncJob(Base):
    __tablename__ = "integration_sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True, nullable=False)
    provider = Column(Enum(SourceProvider), index=True, nullable=False)
    mode = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    request_payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
