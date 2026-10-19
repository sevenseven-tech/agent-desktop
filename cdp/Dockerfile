# Agent Desktop - CDP layer
# Adds the agent side-door: Chromium autostart with a remote-debugging port
# (installed via the desktop-autostart ConfigMap, see manifests/) plus a
# stdlib TCP forwarder that exposes CDP pod-facing on 9223 -> 127.0.0.1:9222.
#
# SECURITY: CDP has no authentication. 9223 must stay cluster-internal /
# node-local. Never publish it. See docs/security.md.
ARG BASE_IMAGE=agent-desktop-base
FROM ${BASE_IMAGE}

COPY cdp_forward.py /usr/local/bin/cdp_forward.py
COPY supervise.sh /usr/local/bin/supervise.sh
RUN chmod +x /usr/local/bin/supervise.sh

# Singleton* cleanup is REQUIRED together with a fixed pod hostname and the
# profile volume: Chromium ties profile state to hostname and refuses a
# profile locked by a stale SingletonLock after an unclean restart.
CMD ["/usr/local/bin/supervise.sh"]
