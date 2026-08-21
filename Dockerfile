FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /code

# Cienka wspólna warstwa: uv plus same manifesty. Zależności instalują się w
# warstwie, która nie widzi kodu, więc edycja pliku .py nie unieważnia cache'u.
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
COPY pyproject.toml uv.lock ./

FROM builder AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM builder AS prod-build
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM base AS prod
COPY --from=prod-build /opt/venv /opt/venv
COPY manage.py ./
RUN useradd --create-home --uid 1000 app && chown -R app:app /code
USER app
