ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3
ARG PI_CODING_AGENT_VERSION=latest

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv \
    && python3 -m venv /opt/contextforge-wrapper-venv \
    && /opt/contextforge-wrapper-venv/bin/python -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
    && npm install -g "@earendil-works/pi-coding-agent@${PI_CODING_AGENT_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm cache clean --force
COPY --chown=agent:agent contextforge-pi-bootstrap.sh /usr/local/bin/contextforge-pi-bootstrap
COPY --chown=agent:agent pi-wrapper.sh /usr/local/bin/pi
RUN chmod 0755 /usr/local/bin/contextforge-pi-bootstrap /usr/local/bin/pi
USER agent

ENV PI_CODING_AGENT_DIR=/home/agent/.pi/agent
ENV CONTEXTFORGE_PI_SHIM_PYTHON=/opt/contextforge-wrapper-venv/bin/python
ENV CONTEXTFORGE_PI_REAL_BIN=/usr/bin/pi

CMD ["pi", "--version"]
