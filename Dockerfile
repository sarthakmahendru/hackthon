FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Train the ML models at build time so the first start is instant
RUN python -m ml.train
# Hosts such as Render and Railway set $PORT. Locally it falls back to 8000.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
