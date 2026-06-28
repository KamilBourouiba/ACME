FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY acme ./acme
COPY data/longmemeval ./data/longmemeval
COPY pyproject.toml .

RUN pip install --no-cache-dir ".[demo-ui]" \
    && playwright install --with-deps chromium

EXPOSE 8000

CMD ["uvicorn", "acme.main:app", "--host", "0.0.0.0", "--port", "8000"]
