import os
import asyncio
import json
import traceback
import time
from .celery_app import celery 
from .database import SessionLocal, engine
from .models import AnalysisTask, TaskStatus, Base
from sqlalchemy.orm import Session
from .services import youtube_service
from .graph.graph import create_work_graph
from .agents.topic_segmentation_agent import TopicSegmentationAgent
from langchain_google_genai import ChatGoogleGenerativeAI

def initialize_llms():
    """Initializes and returns LangChain LLM instances with rate limiting."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    # Use Flash model only with conservative rate limiting
    flash_model = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest",
        google_api_key=gemini_api_key,
        temperature=0.2,
        # Add request timeout
        request_timeout=60
    )
    
    # Return flash_model for both to avoid Pro rate limits
    return flash_model, flash_model

Base.metadata.create_all(bind=engine)

@celery.task(name="run_analysis_pipeline", bind=True, max_retries=3)
def run_analysis_pipeline(self, task_id: str, youtube_url: str):
    """
    The Celery task that executes the full LangGraph analysis pipeline with retry logic.
    """
    db: Session = SessionLocal()
    task = db.query(AnalysisTask).filter(AnalysisTask.task_id == task_id).first()
    
    try:
        # Update task status to processing
        if task:
            task.status = TaskStatus.PROCESSING
            db.commit()
        
        pro_model, flash_model = initialize_llms()
        
        segmentation_agent = TopicSegmentationAgent(model=flash_model)

        app_graph = create_work_graph(
            youtube_service=youtube_service,
            segmentation_agent=segmentation_agent,
            summarizer_model=flash_model,  # Changed from pro_model to flash_model
            claim_extractor_model=flash_model,
            search_query_model=flash_model
        )

        # Add delay before processing to avoid rate limits
        print(f"Starting analysis for task {task_id}. Adding 2-second delay...")
        time.sleep(2)

        final_state = asyncio.run(app_graph.ainvoke({"youtube_url": youtube_url}))

        if isinstance(final_state, list):
            final_state = final_state[-1]
            
        if final_state.get("error"):
            raise Exception(final_state["error"])

        if task:
            task.status = TaskStatus.SUCCESS
            task.result = json.dumps(final_state) 
            db.commit()
        
        return {"status": "SUCCESS", "task_id": task_id}

    except Exception as e:
        error_message = str(e)
        
        # Check if it's a rate limit error and retry
        if "429" in error_message or "quota" in error_message.lower():
            print(f"Rate limit hit for task {task_id}. Retrying in 60 seconds...")
            if self.request.retries < self.max_retries:
                # Update task status to indicate retry
                if task:
                    task.status = TaskStatus.PROCESSING
                    task.result = json.dumps({"status": "retrying", "retry_count": self.request.retries + 1})
                    db.commit()
                    
                # Retry with exponential backoff
                countdown = 60 * (2 ** self.request.retries)  # 60, 120, 240 seconds
                raise self.retry(countdown=countdown)
        
        # Handle other errors
        full_error_message = f"An unexpected error occurred: {error_message}"
        print(f"Error during task execution for {task_id}: {full_error_message}")
        traceback.print_exc()
        
        if task:
            task.status = TaskStatus.FAILURE
            task.result = json.dumps({"error": full_error_message})
            db.commit()
            
        return {"status": "FAILURE", "task_id": task_id, "error": full_error_message}
        
    finally:
        db.close()
