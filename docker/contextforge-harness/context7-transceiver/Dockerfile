FROM python:3.13-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV CONTEXTFORGE_TRANSCEIVER_VENV=/opt/contextforge-transceiver-venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nodejs npm \
    && python -m venv "${CONTEXTFORGE_TRANSCEIVER_VENV}" \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm cache clean --force

EXPOSE 9203

CMD ["/opt/contextforge-transceiver-venv/bin/python", "-m", "mcpgateway.translate", "--stdio", "npx -y @upstash/context7-mcp@latest", "--expose-sse", "--expose-streamable-http", "--host", "0.0.0.0", "--port", "9203", "--logLevel", "info"]
