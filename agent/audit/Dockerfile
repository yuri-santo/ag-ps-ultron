FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
COPY uv /usr/local/bin/uv
WORKDIR /app
COPY source/ /app/
RUN uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python
ENV PATH="/app/.venv/bin:$PATH" HOME=/tmp PYTHONDONTWRITEBYTECODE=1 LANGCHAIN_TRACING_V2=false
USER 65534:65534
WORKDIR /scan
ENTRYPOINT ["skillspector"]
