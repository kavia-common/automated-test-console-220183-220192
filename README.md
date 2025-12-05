# automated-test-console-220183-220192

This workspace contains two containers:
- robotframework_backend (FastAPI service on port 3001)
- robotframework_frontend (React app on port 3000)

Quick start (local development):

Backend (robotframework_backend)
1) Create automated-test-console-220183-220192/robotframework_backend/.env (already added) with sensible defaults:
   - PORT=3001
   - DATABASE_URL=sqlite:///./app.db
   - LOG_DIR=./logs
   - CONFIG_DIR=./configs
   - ROBOT_PROJECT_ROOT=./robot
   - CORS_ALLOWED_ORIGINS=http://localhost:3000
   - RUN_CONCURRENCY=1
   - USE_SSE=true
   - Optional email vars: EMAIL_SMTP_HOST/PORT/USER/PASS

2) Install dependencies and run:
   - cd automated-test-console-220183-220192/robotframework_backend
   - python -m venv .venv && source .venv/bin/activate
   - pip install -r requirements.txt
   - uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload

Frontend (robotframework_frontend)
1) Create automated-test-console-220183-220193/robotframework_frontend/.env (already added):
   - REACT_APP_API_BASE=http://localhost:3001

2) Install and run:
   - cd automated-test-console-220183-220193/robotframework_frontend
   - npm install
   - npm start

Notes:
- The backend auto-loads .env via python-dotenv.
- SSE CORS: EventSource is supported via GET /logs; CORS is handled via allow_origins in the backend and per-response headers for SSE.
- OpenAPI docs at http://localhost:3001/docs