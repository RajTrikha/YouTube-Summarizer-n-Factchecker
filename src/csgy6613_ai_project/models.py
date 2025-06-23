from sqlalchemy import Column, String, JSON, Integer, Enum
from .database import Base
import enum

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING" # New status to indicate work has started
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    result = Column(JSON, nullable=True)