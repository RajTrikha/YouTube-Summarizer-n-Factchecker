from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware  # Add this import
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid
import json

from .database import SessionLocal, engine
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

@app.post("/analyze", response_model=AnalysisResponse, status_code=202)
def analyze_content(request: AnalysisRequest, db: Session = Depends(get_db)):
    """
    This endpoint accepts a URL for analysis, creates a task record in the DB,
    and dispatches the job to the Celery worker queue.
    """
    task_id = str(uuid.uuid4())
    
    db_task = models.AnalysisTask(task_id=task_id, status=models.TaskStatus.PENDING)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    run_analysis_pipeline.delay(task_id=task_id, youtube_url=request.url)

    return {"task_id": task_id, "message": "Analysis has been queued."}

@app.get("/status/{task_id}", response_model=StatusResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """
    This endpoint allows the frontend to poll for the status and result of a task.
    """
    task = db.query(models.AnalysisTask).filter(models.AnalysisTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result_data = None
    if task.result:
        if isinstance(task.result, str):
            result_data = json.loads(task.result)
        else:
            result_data = task.result

    return {"task_id": task.task_id, "status": task.status, "result": result_data}

# Optional: Add a health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}