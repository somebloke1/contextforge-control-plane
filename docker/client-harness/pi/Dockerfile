ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG PI_CODING_AGENT_VERSION=latest

USER root
RUN npm install -g "@earendil-works/pi-coding-agent@${PI_CODING_AGENT_VERSION}" \
    && npm cache clean --force
USER agent

ENV PI_CODING_AGENT_DIR=/home/agent/.pi/agent

CMD ["pi", "--version"]
