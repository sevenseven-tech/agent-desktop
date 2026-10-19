#!/bin/bash
# MCP layer supervisor. Starts playwright-mcp (attached to the live CDP
# session) behind the auth forwarder, then hands off to the cdp supervisor
# (which handles the CDP_AUTOSTART gate, Singleton cleanup and start.sh).
#
# CDP_AUTOSTART=false => no MCP processes at all: the desktop degrades to a
# plain human desktop (Mirko's daily-driver posture on the 4090).
if [ "${CDP_AUTOSTART:-true}" = "true" ]; then
    (
        # playwright-mcp needs the CDP endpoint up; chromium arrives via XFCE
        # autostart a few seconds after the session starts. Wait up to 120s.
        for i in $(seq 1 60); do
            curl -sf http://127.0.0.1:9222/json/version >/dev/null 2>&1 && break
            sleep 2
        done
        exec playwright-mcp \
            --cdp-endpoint http://127.0.0.1:9222 \
            --port 8930 --host 127.0.0.1 \
            --shared-browser-context
    ) &
    # desktop_actions: X11 tools via xdotool/imagemagick; needs the X socket
    # (display :1 created by Xvnc in start.sh a few seconds into boot).
    (
        for i in $(seq 1 60); do [ -e /tmp/.X11-unix/X1 ] && break; sleep 2; done
        exec /opt/dmcp/bin/python /app/desktop_actions.py
    ) &
    python3 /usr/local/bin/mcp_forward.py &
fi
exec /usr/local/bin/supervise.sh
