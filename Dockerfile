# FeedOps Python Pipeline for GCP Cloud Run
# Product data loaded from Supabase - no CSV required in container

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY pyproject.toml .
COPY data/finish-metadata.json /app/data/finish-metadata.json

# Copy Claude Code skills for runtime prompt enrichment
# skill_loader.py looks for .claude/skills/ relative to /app (Cloud Run path)
COPY .claude/skills /app/.claude/skills

# Create placeholder README.md for pyproject.toml (actual file excluded by .gcloudignore)
RUN echo "# FeedOps Pipeline" > README.md

# Install the feedops package (non-editable for production)
RUN pip install --no-cache-dir .

# Set Python path for imports
ENV PYTHONPATH=/app/src

# Cloud Run uses PORT environment variable (default 8080)
ENV PORT=8080

EXPOSE 8080

# Health check for Cloud Run
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run with uvicorn - Cloud Run handles scaling
CMD ["uvicorn", "feedops.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
