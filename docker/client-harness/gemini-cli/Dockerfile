ARG BASE_IMAGE=contextforge-client-base:bookworm
FROM ${BASE_IMAGE}

ARG GEMINI_CLI_VERSION=latest

USER root
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
      | gpg --dearmor -o /etc/apt/keyrings/google-cloud-cli.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/google-cloud-cli.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-cloud-cli \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g "@google/gemini-cli@${GEMINI_CLI_VERSION}" \
    && npm cache clean --force
USER agent

CMD ["gemini", "--version"]
