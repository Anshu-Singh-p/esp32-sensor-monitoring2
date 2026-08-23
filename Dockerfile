FROM python:3.11-slim

WORKDIR /app

# Environment defaults
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Copy application files
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY research/ /app/research/
COPY start.py /app/start.py
COPY requirements.txt /app/requirements.txt
COPY Procfile /app/Procfile

# Expose port
EXPOSE 8080

# Execute server
CMD ["python3", "start.py"]
