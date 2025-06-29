# Chat with Your Video Library



---

## Table of Contents
- [Project Overview](#project-overview)
- [Features](#features)
- [Architecture](#architecture)
- [Technologies Used](#technologies-used)
- [Setup Instructions](#setup-instructions)
  - [Dataset Setup](#dataset-setup)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [YouTube Authentication & Daily Digest](#youtube-authentication--daily-digest)
- [Usage](#usage)
- [Environment Variables](#environment-variables)
- [Contribution Guidelines](#contribution-guidelines)
- [License](#license)

---

## Project Overview

**Chat with Your Video Library** is an AI-powered platform that allows users to analyze, summarize, and fact-check YouTube videos using advanced language models. The system provides:
- Automatic topic segmentation and chaptering
- Concise chapter and overall summaries
- Fact-checking of claims in video content
- A user-friendly web interface and API
- Daily digests of newly liked YouTube videos

## Features
- **YouTube Video Analysis**: Input a YouTube URL to receive structured summaries and fact-check reports.
- **Topic Segmentation**: Videos are segmented into logical chapters using LLMs.
- **Summarization**: Each chapter and the overall video are summarized concisely.
- **Fact-Checking**: Claims are extracted and checked for veracity.
- **Daily Digest**: Fetches and analyzes recently liked YouTube videos via OAuth.
- **Web Interface**: React frontend for easy interaction.
- **API Access**: FastAPI backend for programmatic access.
- **Asynchronous Processing**: Celery and Redis for scalable background jobs.

## Architecture

![Workflow Graph](src/csgy6613_ai_project/workflow_graph.png)

- **Frontend**: React app for user interaction.
- **Backend**: FastAPI app for analysis, orchestrating LLMs, and managing tasks.
- **Celery**: Handles background processing of video analysis tasks.
- **Database**: PostgreSQL for task/result storage.
- **Redis**: Celery broker and result backend.
- **YouTube OAuth Service**: Handles user authentication and daily digest fetching.

## Technologies Used
- Python 3.11, FastAPI, Celery, SQLAlchemy, PostgreSQL, Redis
- LangChain, Google Gemini API, Gradio
- React, Create React App
- Docker, Docker Compose

## Setup Instructions

### Dataset Setup
1. Download the `youtube_dataset.tar` dataset from [HuggingFace](https://huggingface.co/datasets/aegean-ai/ai-lectures-spring-24/tree/main).
2. Place the tar file in the `/datasets/` directory.
3. Extract all videos into `/datasets/videos/` as shown in the structure.

### Backend Setup
1. Navigate to `src/csgy6613_ai_project/`.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your `.env` file (see [Environment Variables](#environment-variables)).
4. (Optional) Build and run with Docker:
   ```bash
   docker build -t ai-video-backend .
   docker run --env-file .env -p 8000:8000 ai-video-backend
   ```
5. Or run locally:
   ```bash
   uvicorn api:app --reload --port 8000
   ```
6. Start Celery worker (in a new terminal):
   ```bash
   celery -A tasks worker --loglevel=info
   ```
7. Ensure PostgreSQL and Redis are running (see Docker Compose below).

#### Docker Compose (Recommended for DB/Redis)
From the project root:
```bash
docker-compose up -d
```
This will start PostgreSQL and Redis containers.

### Frontend Setup
1. Navigate to `frontend/`.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm start
   ```
4. The app will be available at [http://localhost:3000](http://localhost:3000).

### YouTube Authentication & Daily Digest
1. Navigate to `youtube_digest_prototype/`.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your Google OAuth credentials in a `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```
4. Start the OAuth backend:
   ```bash
   uvicorn auth_backend:app --reload --port 9000
   ```
5. Visit [http://localhost:9000](http://localhost:9000) and sign in with Google.
6. Copy the refresh token from the terminal and paste it into `fetch_videos.py` as `USER_REFRESH_TOKEN`.
7. Run the daily digest script:
   ```bash
   python fetch_videos.py
   ```

## Usage
- **Web App**: Use the React frontend to input YouTube URLs and view analysis results.
- **API**: Use the FastAPI endpoints:
  - `POST /analyze` with `{ "url": "<YouTube URL>" }` to start analysis
  - `GET /status/{task_id}` to poll for results
- **Gradio App**: (If enabled) Visit [http://localhost:7860](http://localhost:7860) for an interactive UI.

## Environment Variables
Create a `.env` file in the project root with the following:
```env
GEMINI_API_KEY=your_gemini_api_key
SERPER_API_KEY=your_serper_api_key
GRADIO_SERVER_PORT=7860
MONGO_URI=mongodb://admin:admin123@mongo:27017
ME_CONFIG_MONGODB_SERVER=mongo
ME_CONFIG_MONGODB_PORT=27017
ME_CONFIG_MONGODB_ADMINUSERNAME=admin
ME_CONFIG_MONGODB_ADMINPASSWORD=admin123
MONGO_INITDB_ROOT_USERNAME=admin
MONGO_INITDB_ROOT_PASSWORD=admin123
DATABASE_URL=postgresql://user:password@localhost/content_analyzer
REDIS_URL=redis://localhost:6379/0
```
For YouTube OAuth, add in `youtube_digest_prototype/.env`:
```env
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
```

## Contribution Guidelines
- Fork the repository and create a new branch for your feature or bugfix.
- Write clear commit messages and document your code.
- Ensure all tests pass before submitting a pull request.
- For major changes, open an issue first to discuss your proposal.

## License
This project is for educational purposes (CS-GY 6613). For other uses, please contact the authors.

---

### Team Members
| Name       | NetID  |
|------------|--------|
| Raj Trikha | rt2932 |
