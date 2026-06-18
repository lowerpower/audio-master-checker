FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update     && apt-get install -y --no-install-recommends ffmpeg libsndfile1     && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt README.md ./
COPY audio_master_checker ./audio_master_checker
COPY audio-master-checker ./audio-master-checker
COPY scripts ./scripts

RUN pip install --no-cache-dir -r requirements.txt     && pip install --no-cache-dir -e .

RUN mkdir -p /data/web-runs

EXPOSE 8000

CMD ["uvicorn", "audio_master_checker.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
