# Avtobus backend (headless FastAPI — PyQt yo'q). Kontent, striming, /api, WS,
# va KioskCloud agenti (cloud_client). Poyezd serverining backend'i, kiosksiz.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ffmpeg — video "faststart" remux uchun (media_tools). Yengil.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Ma'lumot (baza + kontent fayllar) DOIMIY volume'da — /data.
ENV KIOSK_VERTICAL=bus \
    KIOSK_TLS=0 \
    KIOSK_DISCOVERY=0 \
    KIOSK_HOST=0.0.0.0 \
    KIOSK_PORT=8000 \
    KIOSK_DB=/data/data.db \
    KIOSK_CONTENT=/data/content

VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "main.py"]
