FROM alpine:3.22

ARG PI_CODING_AGENT_VERSION=0.81.1
ARG USERNAME=agent
ARG USER_UID=1000
ARG USER_GID=1000

ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_AUDIT=false
ENV PI_CODING_AGENT_DIR=/home/agent/.pi/agent
ENV CONTEXTFORGE_PI_REAL_BIN=/usr/local/bin/contextforge-pi-real

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
    && npm install -g "@earendil-works/pi-coding-agent@${PI_CODING_AGENT_VERSION}" \
    && installed_pi="$(command -v pi)" \
    && [ "${installed_pi}" = /usr/local/bin/pi ] \
    && mv "${installed_pi}" /usr/local/bin/contextforge-pi-real \
    && test -f /usr/local/bin/contextforge-pi-real \
    && test -x /usr/local/bin/contextforge-pi-real \
    && npm cache clean --force

COPY --chown=agent:agent pi/contextforge-pi-bootstrap.sh /usr/local/bin/contextforge-pi-bootstrap
COPY --chown=agent:agent pi/pi-wrapper.sh /usr/local/bin/pi
COPY --chown=agent:agent pi/render-config.py /usr/local/lib/contextforge-pi-render-config.py
RUN test -f /usr/local/bin/contextforge-pi-real \
    && test -x /usr/local/bin/contextforge-pi-real \
    && ! test /usr/local/bin/contextforge-pi-real -ef /usr/local/bin/pi \
    && chmod 0755 /usr/local/bin/contextforge-pi-bootstrap /usr/local/bin/pi

USER ${USERNAME}
WORKDIR /workspace

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["pi", "--version"]
