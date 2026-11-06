FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
RUN mkdir -p /app/state /app/logs && useradd --create-home --uid 10001 collector \
    && chown -R collector:collector /app
USER collector
CMD ["python", "-m", "app.main"]
