# ANV-022: build dependencies separately; ship no keys, corpus, models or dev tools.
FROM ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 AS uv
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /build
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN groupadd --gid 10001 anvesha && useradd --uid 10001 --gid 10001 --no-create-home anvesha \
    && mkdir /data && chown 10001:10001 /data
COPY --from=build /opt/venv /opt/venv
COPY LICENSE NOTICE /usr/share/doc/anvesha/
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ANVESHA_CONFIG_PATH=/data/server.json ANVESHA_DB_PATH=/data/anvesha.db
WORKDIR /data
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["anvesha"]
CMD ["run-api", "--host", "0.0.0.0"]
