# ── Why this base image? ───────────────────────────────────────────────────
# python:3.12-slim = small (faster pulls, smaller attack surface) but still
# has apt available if you ever need to add OS packages.
FROM python:3.12-slim

# Don't write .pyc files and flush stdout immediately so logs show up live
# in `kubectl logs` without buffering delay.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements FIRST, install, THEN copy code.
# Why: Docker caches layers. If only main.py changes, this `pip install`
# layer is reused from cache instead of re-running — much faster rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Document the port the app listens on (informational; doesn't actually
# publish it — that's done in the K8s Service/Deployment).
EXPOSE 8000

# Run with uvicorn. host 0.0.0.0 is required so traffic from outside the
# container (i.e. from the Kubernetes network) can reach it — 127.0.0.1
# would only accept connections from inside the container itself.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]