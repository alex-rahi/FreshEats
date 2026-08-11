FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python scripts/download_model.py || true

EXPOSE 8001

CMD ["uvicorn", "app.http_server:app", "--host", "0.0.0.0", "--port", "8001"]
