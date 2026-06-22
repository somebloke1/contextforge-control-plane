FROM node:24-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV NPM_CONFIG_AUDIT=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 tini \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY docker/contextforge-harness/scripts/npm_stdio_host_records.py /opt/contextforge/npm_stdio_host_records.py

VOLUME ["/workspace/server-instances"]

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-lc", "echo npm-stdio-host ready for managed record CRUD; tail -f /dev/null"]
