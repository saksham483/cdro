FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DEMOAPP_PORT=5001
ENV DEMOAPP_DB_PATH=/app/data/demoapp.db
EXPOSE 5001

CMD ["python", "app.py"]
