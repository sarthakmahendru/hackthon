@echo off
REM One-command start (Windows). Open http://localhost:8000
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
