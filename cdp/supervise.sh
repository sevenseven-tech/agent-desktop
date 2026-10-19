#!/bin/bash
# CDP side-door supervisor. CDP_AUTOSTART (default "true") gates the agent
# entry point: when "false", the baked-in chromium autostart entry is removed
# and the CDP forwarder is not started, so the desktop behaves exactly like
# the plain base image (e.g. a human daily-driver box).
if [ "${CDP_AUTOSTART:-true}" = "true" ]; then
    # Singleton* cleanup REQUIRED with fixed hostname + profile volume:
    # chromium refuses a profile locked by a stale SingletonLock.
    rm -f /root/browser-profile/Singleton*
    python3 /usr/local/bin/cdp_forward.py &
else
    rm -f /etc/xdg/autostart/chromium.desktop
fi
exec /start.sh
