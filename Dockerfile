# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Optional: tools to compile wheels if prebuilt ones are unavailable
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# The bot reads TOKEN, AUTH_GIGA, and optional PROXY_URL from env or .env
# Provide them via --env/--env-file at runtime. No ports need to be exposed for long polling.

CMD ["python", "bot.py"]


