ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG CLAUDE_CODE_VERSION=latest

USER root
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force
USER agent

CMD ["claude", "--version"]
