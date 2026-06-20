ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG CODEX_CLI_VERSION=latest
ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv \
    && python3 -m venv /opt/contextforge-helper-venv \
    && /opt/contextforge-helper-venv/bin/python -m pip install --no-cache-dir \
      "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}" \
    && npm install -g "@openai/codex@${CODEX_CLI_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm cache clean --force
COPY --chown=agent:agent entrypoint.sh /usr/local/bin/contextforge-codex-entrypoint
COPY --chown=agent:agent contextforge-codex-project-init-hook /usr/local/bin/contextforge-codex-project-init-hook
RUN chmod 0755 /usr/local/bin/contextforge-codex-entrypoint /usr/local/bin/contextforge-codex-project-init-hook
USER agent

ENV CODEX_HOME=/home/agent/.codex
ENV CONTEXTFORGE_HELPER_PYTHON=/opt/contextforge-helper-venv/bin/python
ENV CONTEXTFORGE_HELPER_SCRIPT=/repo/scripts/contextforge_helper_mcp.py
ENV CONTEXTFORGE_CODEX_WRAPPER_PYTHON=/opt/contextforge-helper-venv/bin/python
ENV CONTEXTFORGE_CODEX_WRAPPER_SCRIPT=/repo/scripts/contextforge_mcp_wrapper.py
ENV CONTEXTFORGE_CODEX_WRAPPER_CONFIG_ENV=/config/contextforge/contextforge.env
ENV CONTEXTFORGE_CODEX_WRAPPER_BASE_URL=http://host.docker.internal:4445
ENV CONTEXTFORGE_CODEX_WRAPPER_TOKEN_CACHE=/tmp/contextforge-wrapper-token.local.json

ENTRYPOINT ["/usr/local/bin/contextforge-codex-entrypoint"]
CMD ["codex", "--version"]
