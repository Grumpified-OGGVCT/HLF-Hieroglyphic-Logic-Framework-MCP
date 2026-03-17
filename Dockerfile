# HLF MCP Server — official image
# Build:  docker build -t hlf-mcp .
# Run:    docker run -e HLF_TRANSPORT=sse -p 8000:8000 hlf-mcp
#
# With hot tier (Valkey):
#   docker compose --profile hot up
#
# With full tier (Valkey + runtime extras):
#   docker compose --profile full up

FROM python:3.12-slim

LABEL org.opencontainers.image.title="HLF MCP Server"
LABEL org.opencontainers.image.description="Hieroglyphic Logic Framework — MCP server for deterministic agent orchestration"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# System deps — only what Lark/tiktoken/cryptography need
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition first (layer-cache friendly)
COPY pyproject.toml README.md ./

# Install package in editable mode without dev extras;
# add [hot] when HLF_INSTALL_EXTRAS contains "hot"
ARG HLF_INSTALL_EXTRAS=""
COPY hlf_mcp/ ./hlf_mcp/
COPY governance/ ./governance/
COPY fixtures/ ./fixtures/

RUN if [ -n "$HLF_INSTALL_EXTRAS" ]; then \
            pip install --no-cache-dir -e ".[${HLF_INSTALL_EXTRAS}]"; \
        else \
            pip install --no-cache-dir -e .; \
        fi

ENV HLF_TRANSPORT=sse
ENV HLF_HOST=0.0.0.0
ENV HLF_PORT=8000
ENV HLF_STRICT=1
ENV HLF_HOT_TIER=none

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["hlf-mcp"]
