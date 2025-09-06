FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
# Install runtime dependencies only
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy all Python modules into the container
COPY *.py .
RUN useradd -u 10001 -m appuser
USER appuser
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=5 \
  CMD python - <<'PY'\nimport urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/healthz', timeout=3)\nPY
# Ensure required modules exist before launching Uvicorn
CMD ["sh", "-c", "test -f api.py && test -f config.py && test -f state.py && exec python -m uvicorn bridge:app --host 0.0.0.0 --port 8088"]
