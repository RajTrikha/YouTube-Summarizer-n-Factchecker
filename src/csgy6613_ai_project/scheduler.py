import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import User
from .tasks import fetch_and_queue_videos_for_user


def trigger_daily_digests():
    """
    The main function for the scheduled job. It finds all subscribed users
    and queues a video-fetching task for each one.
    """
    print("--- SCHEDULER: Starting daily digest job for all users ---")
    
    # Load environment variables - use absolute path or current directory
    load_dotenv()  # This will look for .env in current directory and parent directories
    
    db: Session = SessionLocal()
    
    try:
        # Find all users who have enabled the digest feature
        subscribed_users = db.query(User).filter(User.digest_enabled == True).all()
        print(f"Found {len(subscribed_users)} subscribed users.")
        
        if not subscribed_users:
            print("No subscribed users found. Exiting.")
            return
        
        # Queue tasks for each user
        queued_count = 0
        for user in subscribed_users:
            try:
                print(f" -> Queuing video fetch for user: {user.email}")
                fetch_and_queue_videos_for_user.delay(user_id=user.id)
                queued_count += 1
            except Exception as e:
                print(f" -> ERROR: Failed to queue task for user {user.email}: {str(e)}")
                continue
        
        print(f"--- SCHEDULER: {queued_count}/{len(subscribed_users)} user tasks have been queued ---")
        
    except Exception as e:
        print(f"ERROR: Database query failed: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        trigger_daily_digests()
    except Exception as e:
        print(f"CRITICAL ERROR: Scheduler failed: {str(e)}")
        exit(1)
