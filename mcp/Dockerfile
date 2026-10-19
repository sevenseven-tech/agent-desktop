# Agent Desktop - MCP layer
# Exposes the live desktop session over the Model Context Protocol:
#   - playwright-mcp attaches to the running Chromium via CDP and serves
#     Streamable HTTP on 127.0.0.1:8930 (no auth of its own)
#   - mcp_forward.py is the security boundary: bearer token + Origin
#     allowlist, pod-facing on 8931
#
# SECURITY: never publish 8931 outside the cluster / node-local. The MCP
# session drives a LOGGED-IN browser. See docs/security.md.
ARG BASE_IMAGE=agent-desktop-cdp
FROM ${BASE_IMAGE}

# Debian stable nodejs (20.x) satisfies @playwright/mcp (>=18). Version is
# pinned: tool schemas must not change under a running fleet.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g @playwright/mcp@0.0.83 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY mcp_forward.py /usr/local/bin/mcp_forward.py
COPY supervise_mcp.sh /usr/local/bin/supervise_mcp.sh
RUN chmod +x /usr/local/bin/supervise_mcp.sh /usr/local/bin/mcp_forward.py

# MCP_TOKEN (from secret/mcp-auth) is REQUIRED when CDP_AUTOSTART=true:
# the forwarder refuses to start open-access (fail-loud, same philosophy as
# the vncpasswd guard in start.sh).
CMD ["/usr/local/bin/supervise_mcp.sh"]
