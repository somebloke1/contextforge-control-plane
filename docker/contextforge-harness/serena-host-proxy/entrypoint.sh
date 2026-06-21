#!/usr/bin/env sh
set -eu

cat >/etc/nginx/conf.d/default.conf <<EOF
server {
    listen ${SERENA_PROXY_BIND}:${SERENA_PROXY_PORT};

    location / {
        proxy_pass http://${SERENA_TARGET_HOST}:${SERENA_TARGET_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host ${SERENA_TARGET_HOST}:${SERENA_TARGET_PORT};
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

exec nginx -g "daemon off;"
