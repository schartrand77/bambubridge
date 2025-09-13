FROM python:3.12.0-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    BAMBULAB_LOG_LEVEL=INFO PORT=8088
# Install runtime dependencies only
WORKDIR /app
COPY pyproject.toml .
RUN python - <<'PY'
import tomllib, subprocess
with open('pyproject.toml', 'rb') as f:
    deps = tomllib.load(f)['project']['dependencies']
subprocess.run(['pip', 'install', '--no-cache-dir', *deps], check=True)
PY
# Ensure application user exists before copying files
RUN id -u appuser >/dev/null 2>&1 || useradd -u 10001 -m appuser
# Copy all Python modules with proper ownership
COPY --chown=appuser:appuser *.py .
USER appuser
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=5 \
  CMD python - <<'PY'\nimport os, urllib.request; urllib.request.urlopen(f"http://127.0.0.1:{os.getenv('PORT','8088')}/healthz", timeout=3)\nPY
# Ensure required modules exist before launching the application
CMD ["sh", "-c", "test -f api.py && test -f config.py && test -f state.py && exec python bridge.py"]
