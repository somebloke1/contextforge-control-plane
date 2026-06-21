FROM mcr.microsoft.com/playwright:v1.54.2-noble

ENV NODE_ENV=production
ENV PLAYWRIGHT_MCP_PACKAGE=@playwright/mcp@latest

RUN npx -y "${PLAYWRIGHT_MCP_PACKAGE}" install-browser chrome-for-testing

EXPOSE 9204

CMD ["sh", "-lc", "exec npx -y \"$PLAYWRIGHT_MCP_PACKAGE\" --browser=chromium --headless --isolated --shared-browser-context --host 0.0.0.0 --port 9204 --allowed-hosts localhost:9204,127.0.0.1:9204,playwright-transceiver:9204"]
