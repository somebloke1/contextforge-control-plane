FROM node:24-bookworm-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

ENV DEBIAN_FRONTEND=noninteractive
ENV CONTEXTFORGE_TRANSCEIVER_VENV=/opt/contextforge-transceiver-venv
ENV NPM_CONFIG_AUDIT=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 python3-venv tini \
    && python3 -m venv "${CONTEXTFORGE_TRANSCEIVER_VENV}" \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY docker/contextforge-harness/scripts/npm_stdio_host_records.py /opt/contextforge/npm_stdio_host_records.py
COPY docker/contextforge-harness/scripts/npm_stdio_host_runtime.py /opt/contextforge/npm_stdio_host_runtime.py

VOLUME ["/workspace/server-instances"]

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-lc", "echo npm-stdio-host ready for managed runtime CRUD; tail -f /dev/null"]
