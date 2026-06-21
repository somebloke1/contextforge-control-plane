FROM python:3.13-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV CONTEXTFORGE_TRANSCEIVER_VENV=/opt/contextforge-transceiver-venv

WORKDIR /workspace

RUN python -m venv "${CONTEXTFORGE_TRANSCEIVER_VENV}" \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
      httpx \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip cache purge

COPY server-instances/exa-search/server.py /workspace/server-instances/exa-search/server.py

EXPOSE 9205

CMD ["/opt/contextforge-transceiver-venv/bin/python", "-m", "mcpgateway.translate", "--stdio", "/opt/contextforge-transceiver-venv/bin/python /workspace/server-instances/exa-search/server.py", "--expose-sse", "--expose-streamable-http", "--host", "0.0.0.0", "--port", "9205", "--logLevel", "info"]
