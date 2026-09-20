#!/usr/bin/env bash
# One-command start (Linux / macOS). Open http://localhost:8000
set -e
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
