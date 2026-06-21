FROM python:3.13-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV CONTEXTFORGE_TRANSCEIVER_VENV=/opt/contextforge-transceiver-venv

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nodejs npm \
    && python -m venv "${CONTEXTFORGE_TRANSCEIVER_VENV}" \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm cache clean --force

WORKDIR /workspace/web_search

COPY --from=web_search package.json package-lock.json tsconfig.mcp.json ./
COPY --from=web_search *.ts ./

RUN npm ci \
    && npm run build \
    && npm prune --omit=dev \
    && npm cache clean --force

WORKDIR /workspace

EXPOSE 9207

CMD ["/opt/contextforge-transceiver-venv/bin/python", "-m", "mcpgateway.translate", "--stdio", "node /workspace/web_search/dist/mcp-server.js", "--expose-sse", "--expose-streamable-http", "--host", "0.0.0.0", "--port", "9207", "--logLevel", "info"]
