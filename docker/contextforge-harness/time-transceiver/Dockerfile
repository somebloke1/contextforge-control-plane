FROM python:3.13-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV CONTEXTFORGE_TRANSCEIVER_VENV=/opt/contextforge-transceiver-venv
ENV LOCAL_TIMEZONE=UTC

RUN python -m venv "${CONTEXTFORGE_TRANSCEIVER_VENV}" \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
      mcp-server-time \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip cache purge

EXPOSE 9209

CMD ["sh", "-lc", "exec /opt/contextforge-transceiver-venv/bin/python -m mcpgateway.translate --stdio \"/opt/contextforge-transceiver-venv/bin/mcp-server-time --local-timezone ${LOCAL_TIMEZONE}\" --expose-sse --expose-streamable-http --host 0.0.0.0 --port 9209 --logLevel info"]
