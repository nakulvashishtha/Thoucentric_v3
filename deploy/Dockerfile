# Template. Claude Code: adapt paths to the backend you build (backend/ with requirements.txt, app.main:app).
# The front end is already compiled in frontend/dist, so there is NO Node build stage.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 DATA_DIR=/app/data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY frontend/dist frontend/dist
RUN mkdir -p /app/data
EXPOSE 8000
# The app must bind 0.0.0.0:$PORT, serve frontend/dist at / (single-page fallback for non-/api paths), and answer GET /healthz.
CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
