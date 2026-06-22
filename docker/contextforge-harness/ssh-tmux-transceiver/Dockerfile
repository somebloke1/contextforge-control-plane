FROM python:3.13-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3
ARG MCP_SSH_TMUX_VERSION=0.2.8

ENV PYTHONDONTWRITEBYTECODE=1
ENV CONTEXTFORGE_TRANSCEIVER_VENV=/opt/contextforge-transceiver-venv
ENV UV_CACHE_DIR=/var/cache/uv
ENV PATH="/root/.local/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates openssh-client sshpass tmux \
    && python -m venv "${CONTEXTFORGE_TRANSCEIVER_VENV}" \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/python" -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
      uv \
    && "${CONTEXTFORGE_TRANSCEIVER_VENV}/bin/uv" tool install "mcp-ssh-tmux==${MCP_SSH_TMUX_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY docker/contextforge-harness/ssh-tmux-transceiver/contextforge-ssh-wrapper.sh /root/.local/bin/ssh
RUN chmod 0755 /root/.local/bin/ssh

EXPOSE 9202

CMD ["/opt/contextforge-transceiver-venv/bin/python", "-m", "mcpgateway.translate", "--stdio", "/root/.local/bin/mcp-ssh-tmux", "--expose-sse", "--expose-streamable-http", "--host", "0.0.0.0", "--port", "9202", "--logLevel", "info"]
