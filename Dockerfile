FROM python:3.11-slim

# Security: run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create data directory for SQLite persistence
RUN mkdir -p /data && chown appuser:appgroup /data

USER appuser

ENV FLASK_ENV=production
ENV KECHAFA_DB=/data/kechafa.db

EXPOSE 5000

# Gunicorn: 2 workers, production-grade
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:application"]
