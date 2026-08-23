FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY research/ /app/research/
COPY start.py /app/start.py
COPY requirements.txt /app/requirements.txt

# Expose backend port
EXPOSE 8080

# Run backend
CMD ["python3", "start.py", "8080"]
