# SwarmGlass MCP Server — official image
LABEL org.opencontainers.image.title="SwarmGlass Governance Framework MCP Server"
LABEL org.opencontainers.image.description="SwarmGlass — governed execution and coordination framework for agentic systems (HLF language engine included)"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# System deps — only what Lark/tiktoken/cryptography need.
# On Windows Docker Desktop the build VM sometimes can't reach apt repos,
# so tolerate failure — most packages ship pre-built wheels for 3.12.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    || echo "apt-get failed; relying on pre-built wheels"

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
ENV HLF_STRICT=1
ENV HLF_HOT_TIER=none

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.environ['HLF_PORT'] + '/health')" || exit 1

CMD ["hlf-mcp"]
