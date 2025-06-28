# Known Issues & Debugging Notes

_Last updated: 2025-06-28_

## Major Issues

### 1. Celery/Redis Connection Refused
- **Error:** `[Errno 61] Connection refused` when submitting analysis tasks.
- **Symptoms:**
  - FastAPI backend works, but Celery tasks are not processed.
  - Error trace from Kombu/Celery about Redis connection.
- **Possible Causes:**
  - Redis is not running or not accessible at `localhost:6379`.
  - Port conflict or firewall issue.
  - Celery worker and/or FastAPI app are not using the correct broker URL.
- **Next Steps:**
  - Ensure Redis is running (`docker-compose up -d` or `redis-server`).
  - Confirm Redis is accessible from the host (`nc -vz localhost 6379`).
  - Check `REDIS_URL` in `celery_app.py` and environment variables.
  - Restart all services after any changes.

### 2. Docker Compose Warnings
- **Warning:** `the attribute 'version' is obsolete` in `docker-compose.yaml`.
- **Impact:** None (just a warning), but consider removing the `version` key for clarity.

### 3. General Debugging To-Do
- [ ] Test Celery task execution after Redis is confirmed running.
- [ ] Add real email sending logic in `tasks.py` (currently simulated with print).
- [ ] Consider using Alembic for DB migrations instead of `create_all` in production.
- [ ] Restrict CORS origins in production for security.
- [ ] Make OAuth redirect URIs configurable for deployment.

## Minor Issues
- Some unused imports and comments in code (clean up for production).
- No automated tests yet—add unit/integration tests for critical paths.

## How to Resume
1. Checkout this branch: `git checkout wip/debug-integration`
2. Review this file and the README for context.
3. Address the issues above, starting with Redis/Celery connectivity.
4. Commit and push as you make progress.

---

_This file is for tracking the current state and next steps. Update as you debug or fix issues!_ 