FROM python:3.12-slim

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

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m serveredr_user
RUN mkdir -p /app/evidence /app/database && \
    chown -R serveredr_user:serveredr_user /app/evidence /app/database
USER serveredr_user

EXPOSE 5000

CMD ["python", "app.py"]