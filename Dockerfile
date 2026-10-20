# ANV-022/ANV-027: reviewed runtime; ship no keys, corpus, models or dev tools.
FROM ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 AS uv
FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587 AS base
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PYTHON_PREFERENCE=only-managed UV_LINK_MODE=copy
WORKDIR /build
COPY policies/runtimes/python-downloads.json /build/python-downloads.json
RUN uv python install 3.14.8 --python-downloads-json-url /build/python-downloads.json --no-bin
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --python 3.14.8 \
    && /opt/venv/bin/python -c "from anvesha.sqlite_runtime import require_runtime; require_runtime()"

FROM base
RUN groupadd --gid 10001 anvesha && useradd --uid 10001 --gid 10001 --no-create-home anvesha \
    && mkdir /data && chown 10001:10001 /data
COPY --from=build /opt/python /opt/python
COPY --from=build /opt/venv /opt/venv
COPY LICENSE NOTICE /usr/share/doc/anvesha/
COPY policies/runtimes/python-downloads.json /usr/share/doc/anvesha/python-downloads.json
COPY third_party/python-build-standalone-20261013 /usr/share/doc/anvesha/python-runtime/
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ANVESHA_CONFIG_PATH=/data/server.json ANVESHA_DB_PATH=/data/anvesha.db
WORKDIR /data
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["anvesha"]
CMD ["run-api", "--host", "0.0.0.0"]
