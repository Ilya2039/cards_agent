# syntax=docker/dockerfile:1.17.0

############################
# Base
############################
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

############################
# Builder: ставим зависимости через PDM в .venv
############################
FROM base AS builder

# Пакеты для сборки колёс (если есть C-расширения)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# PDM
RUN pip install --no-cache-dir -U pip setuptools wheel pdm

WORKDIR /app

# Для кэшируемой сборки копируем манифесты зависимостей
COPY pyproject.toml pdm.lock ./

# PDM — в локальное .venv
ENV PDM_HOME=/opt/pdm \
    PDM_USE_VENV=true \
    PDM_VENV_IN_PROJECT=true

# Устанавливаем только prod-зависимости (используем кэши BuildKit)
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/pdm \
    pdm install --prod --no-editable --frozen-lockfile

############################
# Runtime: минимальный слой с готовым .venv и кодом
############################
FROM base AS runtime
WORKDIR /app

# Переносим готовое виртуальное окружение
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Копируем приложение
COPY . .

# Бот читает TOKEN, AUTH_GIGA и (опционально) PROXY_URL из env (--env/--env-file)
CMD ["python", "bot.py"]