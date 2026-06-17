FROM python:3.13-slim

ARG MCP_CONTEXTFORGE_GATEWAY_VERSION=1.0.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/workspace/scripts

WORKDIR /workspace

RUN python -m pip install --no-cache-dir \
    "mcp-contextforge-gateway==${MCP_CONTEXTFORGE_GATEWAY_VERSION}"

COPY scripts/governance_mcp.py scripts/governance_registry.py /workspace/scripts/
COPY DECISIONS.md ABEYANT_INTENTIONS.md OPEN_QUESTIONS.md /workspace/

EXPOSE 9201

CMD ["python", "-m", "mcpgateway.translate", "--stdio", "python scripts/governance_mcp.py", "--expose-sse", "--expose-streamable-http", "--host", "0.0.0.0", "--port", "9201", "--logLevel", "info"]
