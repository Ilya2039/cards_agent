FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

FROM base AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -U pip setuptools wheel pdm
WORKDIR /app

# Копируем манифесты зависимостей (lock — опционально)
COPY pyproject.toml ./
COPY pdm.lock* ./

ENV PDM_HOME=/opt/pdm \
    PDM_USE_VENV=true \
    PDM_VENV_IN_PROJECT=true

# Если есть pdm.lock — используем его, иначе ставим по pyproject.toml
RUN if [ -f pdm.lock ]; then \
      pdm install --prod --no-editable --frozen-lockfile; \
    else \
      pdm install --prod --no-editable; \
    fi

FROM base AS runtime
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY . .

# TOKEN, AUTH_GIGA и (опц.) PROXY_URL передавай через --env/--env-file
CMD ["python", "bot.py"]