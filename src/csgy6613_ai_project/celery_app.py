import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# The name of the celery app, 'tasks', should match the file where the tasks are defined.
# The `main` argument is also changed to match the filename.
celery = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['csgy6613_ai_project.tasks']
)

celery.conf.update(
    task_track_started=True,
)

