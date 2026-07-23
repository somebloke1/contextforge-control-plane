FROM alpine:3.22

ARG OPENCODE_VERSION=latest
ARG USERNAME=agent
ARG USER_UID=1000
ARG USER_GID=1000

ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_AUDIT=false
ENV OPENCODE_CONFIG_DIR=/home/agent/.config/opencode

RUN apk add --no-cache \
      bash \
      ca-certificates \
      curl \
      git \
      jq \
      nodejs \
      npm \
      openssh-client \
      python3 \
      tini \
    && addgroup -g "${USER_GID}" "${USERNAME}" \
    && adduser -D -u "${USER_UID}" -G "${USERNAME}" -s /bin/bash "${USERNAME}" \
    && mkdir -p /workspace /evidence \
    && chown -R "${USERNAME}:${USERNAME}" /workspace /evidence \
    && npm install -g "opencode-ai@${OPENCODE_VERSION}" \
    && npm cache clean --force

COPY --chown=agent:agent opencode-alpine/entrypoint.sh /usr/local/bin/contextforge-opencode-alpine-entrypoint
COPY --chown=agent:agent opencode/render-config.py /usr/local/bin/contextforge-opencode-render-config
RUN chmod 0755 /usr/local/bin/contextforge-opencode-alpine-entrypoint \
      /usr/local/bin/contextforge-opencode-render-config

USER ${USERNAME}
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/contextforge-opencode-alpine-entrypoint"]
CMD ["opencode", "--version"]
