FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \ 
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       wget \
       gnupg \
       chromium \
       chromium-driver \
       fonts-liberation \
       libnss3 \
       libatk1.0-0 \
       libatk-bridge2.0-0 \
       libx11-xcb1 \
       libxss1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home appuser || true
WORKDIR /home/appuser/app
COPY . /home/appuser/app
RUN chown -R appuser:appuser /home/appuser/app
USER appuser

ENV PYTHONUNBUFFERED=1
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:APP", "--host", "0.0.0.0", "--port", "8000", "--loop", "auto"]
