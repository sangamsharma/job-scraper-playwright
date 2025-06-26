FROM python:3.10-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    wget curl unzip fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 \
    libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
    libxdamage1 libxrandr2 xdg-utils \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy files
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN pip install playwright && playwright install --with-deps

COPY . .

CMD ["python", "main.py"]
