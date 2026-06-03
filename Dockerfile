FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build
RUN .venv/bin/python manage.py collectstatic --noinput

ENV DJANGO_SETTINGS_MODULE=looplink.project.settings
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["gunicorn", "looplink.project.wsgi:application", "--bind", "0.0.0.0:8000"]
