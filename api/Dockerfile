# syntax=docker/dockerfile:1
# astrolabio-api. Base images are pinned by digest (Dependabot bumps them) and every
# Python dependency comes from uv.lock with its hash checked (`--locked`). The project
# itself is not built as a wheel: its source runs from /app/src, so no build backend
# outside the lock is ever downloaded.

FROM ghcr.io/astral-sh/uv:0.11.22@sha256:16b63af0e7342dd372da9ca989ea9fa542fc68f4640972d59a8450a5240fe42e AS uv

FROM python:3.13-slim@sha256:cf50a4f6ac4f026458b08d5222023d700ac806410dff5e9ca8728fa44f2b850f AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY src ./src
# Bytecode is compiled here: at runtime the root filesystem is read-only.
RUN python -m compileall -q src

FROM python:3.13-slim@sha256:cf50a4f6ac4f026458b08d5222023d700ac806410dff5e9ca8728fa44f2b850f
# pip is not needed at runtime, and its vendored copies of certifi, urllib3, msgpack and
# setuptools lag behind (Trivy flags them), so it goes.
RUN groupadd --system --gid 10001 astrolabio \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin astrolabio \
    && rm -rf /usr/local/lib/python3.13/site-packages/pip /usr/local/lib/python3.13/site-packages/pip-*.dist-info /usr/local/bin/pip*
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "astrolabio_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
