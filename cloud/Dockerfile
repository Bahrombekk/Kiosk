# KioskCloud — markaziy admin paneli. Yengil Python image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Avval faqat requirements — Docker qatlam keshi (kod o'zgarsa qayta o'rnatmaydi)
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Kod (backend/) + frontend (web/)
COPY . .

# Ma'lumot (baza, ombor, imzo kaliti) DOIMIY volume'da — /data.
# (Konteyner qayta qurilса ham imzo kaliti saqlanadi; aks holda serverlar
#  buyruqlarni rad etardi.)
ENV CLOUD_DB=/data/cloud.db \
    CLOUD_STORAGE=/data/storage \
    CLOUD_SIGNING_KEY=/data/cloud_signing_key.pem \
    CLOUD_HOST=0.0.0.0 \
    CLOUD_PORT=9000

VOLUME ["/data"]
EXPOSE 9000

CMD ["python", "backend/main.py"]
