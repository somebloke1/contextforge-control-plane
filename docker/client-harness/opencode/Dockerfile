ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG OPENCODE_VERSION=latest

USER root
RUN npm install -g "opencode-ai@${OPENCODE_VERSION}" \
    && npm cache clean --force
USER agent

ENV OPENCODE_CONFIG_DIR=/home/agent/.config/opencode

CMD ["opencode", "--version"]
