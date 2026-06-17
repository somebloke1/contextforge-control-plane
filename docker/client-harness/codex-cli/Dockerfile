ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG CODEX_CLI_VERSION=latest

USER root
RUN npm install -g "@openai/codex@${CODEX_CLI_VERSION}" \
    && npm cache clean --force
USER agent

CMD ["codex", "--version"]
