from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class TaskStatus(enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), unique=True, index=True, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    result = Column(JSON, nullable=True)  # Store the analysis results as JSON
    progress = Column(JSON, nullable=True)  # Store progress information as JSON
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<AnalysisTask(task_id='{self.task_id}', status='{self.status}')>"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    youtube_refresh_token = Column(Text, nullable=True)  # Store encrypted refresh token
    digest_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_digest_sent = Column(DateTime(timezone=True), nullable=True)  # Track when last digest was sent
    
    def __repr__(self):
        return f"<User(email='{self.email}', digest_enabled={self.digest_enabled})>"

class VideoAnalysis(Base):
    """Optional table to store individual video analysis results for user digests"""
    __tablename__ = "video_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # Link to user if needed
    video_id = Column(String(255), nullable=False)  # YouTube video ID
    video_title = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=False)
    analysis_summary = Column(Text, nullable=True)
    chapters = Column(JSON, nullable=True)  # Store chapter data as JSON
    fact_check_results = Column(JSON, nullable=True)  # Store fact-check results as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<VideoAnalysis(video_id='{self.video_id}', title='{self.video_title}')>"