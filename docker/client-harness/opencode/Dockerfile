ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3
ARG OPENCODE_VERSION=latest

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv \
    && python3 -m venv /opt/contextforge-helper-venv \
    && /opt/contextforge-helper-venv/bin/python -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
    && npm install -g "opencode-ai@${OPENCODE_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm cache clean --force
COPY --chown=agent:agent entrypoint.sh /usr/local/bin/contextforge-opencode-entrypoint
COPY --chown=agent:agent render-config.py /usr/local/bin/contextforge-opencode-render-config
RUN chmod 0755 /usr/local/bin/contextforge-opencode-entrypoint \
      /usr/local/bin/contextforge-opencode-render-config
USER agent

ENV OPENCODE_CONFIG_DIR=/home/agent/.config/opencode
ENV CONTEXTFORGE_HELPER_PYTHON=/opt/contextforge-helper-venv/bin/python
ENV CONTEXTFORGE_OPENCODE_WRAPPER_PYTHON=/opt/contextforge-helper-venv/bin/python
ENV CONTEXTFORGE_OPENCODE_WRAPPER_SCRIPT=/repo/scripts/contextforge_mcp_wrapper.py
ENV CONTEXTFORGE_OPENCODE_WRAPPER_TOKEN_CACHE=/tmp/contextforge-wrapper-token.local.json

ENTRYPOINT ["/usr/local/bin/contextforge-opencode-entrypoint"]
CMD ["opencode", "--version"]
