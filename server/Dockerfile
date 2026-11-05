FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --disable-pip-version-check \
    -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin serveredr_user && \
    mkdir -p /app/evidence /app/database && \
    chown -R serveredr_user:serveredr_user \
        /app/evidence /app/database

USER serveredr_user

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s \
    --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).close()"

CMD ["python", "app.py"]
