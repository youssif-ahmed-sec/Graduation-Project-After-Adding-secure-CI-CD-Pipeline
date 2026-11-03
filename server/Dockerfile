FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m serveredr_user
RUN mkdir -p /app/evidence /app/database && \
    chown -R serveredr_user:serveredr_user /app/evidence /app/database
USER serveredr_user

EXPOSE 5000

CMD ["python", "app.py"]