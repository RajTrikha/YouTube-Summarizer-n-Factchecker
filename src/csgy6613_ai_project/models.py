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
