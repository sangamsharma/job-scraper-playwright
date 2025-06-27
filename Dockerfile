FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    libpq-dev \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install playwright psycopg2-binary && \
    playwright install --with-deps

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.local/bin:$PATH"

CMD ["python", "main.py"]
