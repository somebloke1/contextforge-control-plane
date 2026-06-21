FROM nginx:1.29-alpine

COPY docker/contextforge-harness/serena-host-proxy/entrypoint.sh /usr/local/bin/serena-host-proxy-entrypoint

ENV SERENA_PROXY_BIND=172.17.0.1
ENV SERENA_PROXY_PORT=9208
ENV SERENA_TARGET_HOST=127.0.0.1
ENV SERENA_TARGET_PORT=9108

RUN chmod 0755 /usr/local/bin/serena-host-proxy-entrypoint

CMD ["/usr/local/bin/serena-host-proxy-entrypoint"]
