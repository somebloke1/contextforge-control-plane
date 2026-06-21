FROM ghcr.io/github/github-mcp-server:v1.4.0@sha256:2afb26356481d1a350e14544a6e160f7f7ec1561a1ea309b823665abf0309036 AS github-mcp-server

FROM python:3.13-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV CONTEXTFORGE_TRANSCEIVER_VENV=/opt/contextforge-transceiver-venv

COPY --from=github-mcp-server /server/github-mcp-server /usr/local/bin/github-mcp-server

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && python -m venv "${CONTEXTFORGE_TRANSCEIVER_VENV}" \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 9206

CMD ["/bin/sh", "-c", "test -n \"${GITHUB_PERSONAL_ACCESS_TOKEN:-}\" || { echo 'GITHUB_PERSONAL_ACCESS_TOKEN required for github-transceiver' >&2; exit 64; }; exec /opt/contextforge-transceiver-venv/bin/python -m mcpgateway.translate --stdio 'github-mcp-server stdio' --expose-sse --expose-streamable-http --host 0.0.0.0 --port 9206 --logLevel info"]
