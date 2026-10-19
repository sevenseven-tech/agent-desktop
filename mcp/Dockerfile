# Agent Desktop - MCP layer
# Exposes the live desktop session over the Model Context Protocol:
#   - playwright-mcp attaches to the running Chromium via CDP and serves
#     Streamable HTTP on 127.0.0.1:8930 (no auth of its own)
#   - desktop_actions.py (Python mcp SDK) serves desktop actions
#     (screenshot/click/type/key/scroll/windows/open_url) on 127.0.0.1:8932
#   - mcp_forward.py is the security boundary: bearer token + Origin
#     allowlist, pod-facing on 8931; routes /mcp -> 8930, /desktop -> 8932
#
# SECURITY: never publish 8931 outside the cluster / node-local. The MCP
# session drives a LOGGED-IN browser AND the whole desktop. See docs/security.md.
ARG BASE_IMAGE=agent-desktop-cdp
FROM ${BASE_IMAGE}

# Debian stable nodejs (20.x) satisfies @playwright/mcp (>=18). Version is
# pinned: tool schemas must not change under a running fleet.
# xdotool + imagemagick drive/observe the X11 display; python venv isolates
# the mcp SDK from Debian's system python (PEP 668).
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
        xdotool imagemagick python3-venv \
    && npm install -g @playwright/mcp@0.0.83 \
    && python3 -m venv /opt/dmcp \
    && /opt/dmcp/bin/pip install --no-cache-dir "mcp~=1.30.0" \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY mcp_forward.py /usr/local/bin/mcp_forward.py
COPY supervise_mcp.sh /usr/local/bin/supervise_mcp.sh
COPY desktop_actions.py /app/desktop_actions.py
COPY tests/ /app/tests/
RUN chmod +x /usr/local/bin/supervise_mcp.sh /usr/local/bin/mcp_forward.py \
    && /opt/dmcp/bin/python -m unittest /app/tests/test_desktop_actions.py

# MCP_TOKEN (from secret/mcp-auth) is REQUIRED when CDP_AUTOSTART=true:
# the forwarder refuses to start open-access (fail-loud, same philosophy as
# the vncpasswd guard in start.sh).
CMD ["/usr/local/bin/supervise_mcp.sh"]
