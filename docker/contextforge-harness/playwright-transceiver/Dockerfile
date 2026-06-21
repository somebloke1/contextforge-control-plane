FROM mcr.microsoft.com/playwright:v1.54.2-noble

ENV NODE_ENV=production
ENV PLAYWRIGHT_MCP_PACKAGE=@playwright/mcp@0.0.76

RUN npm install -g "${PLAYWRIGHT_MCP_PACKAGE}" \
    && playwright-mcp install-browser chrome-for-testing \
    && npm cache clean --force

EXPOSE 9204

CMD ["playwright-mcp", "--browser=chromium", "--headless", "--isolated", "--shared-browser-context", "--host", "0.0.0.0", "--port", "9204", "--allowed-hosts", "localhost:9204,127.0.0.1:9204,playwright-transceiver:9204"]
