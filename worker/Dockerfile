FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app

# Install only the minimal dependencies needed
COPY requirements.txt .
RUN pip install --no-cache-dir redis[hiredis] httpx 2>/dev/null || true

COPY worker/main.py .

EXPOSE 9000

CMD ["python", "main.py"]
