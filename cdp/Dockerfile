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
COPY autostart/chromium.desktop /etc/xdg/autostart/chromium.desktop
RUN chmod +x /usr/local/bin/supervise.sh

# Autostart is baked system-wide (/etc/xdg/autostart) and gated at runtime by
# the CDP_AUTOSTART env var (default "true"; "false" removes the entry before
# XFCE starts - see supervise.sh). No ConfigMap needed; works identically in
# plain docker and k8s.
#
# SECURITY: CDP has no authentication. 9223 must stay cluster-internal /
# node-local. Never publish it. See docs/security.md.
CMD ["/usr/local/bin/supervise.sh"]
