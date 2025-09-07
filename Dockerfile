FROM python:3.12.0-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    BAMBULAB_LOG_LEVEL=INFO PORT=8088
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
  CMD python - <<'PY'\nimport os, urllib.request; urllib.request.urlopen(f"http://127.0.0.1:{os.getenv('PORT','8088')}/healthz", timeout=3)\nPY
# Ensure required modules exist before launching the application
CMD ["sh", "-c", "test -f api.py && test -f config.py && test -f state.py && exec python bridge.py"]
