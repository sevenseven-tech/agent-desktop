# Agent Desktop

A real, logged-in desktop in a container that **both a human and an AI agent can use at the same time**.

Human connects over noVNC (browser), logs in wherever needed like a normal person.
Agent connects over CDP (Chrome DevTools Protocol) and drives the *same* browser
session - same tabs, same cookies, same logged-in state. No bot walls, because
the login was a human's; no headless fingerprint tells, because it is a real
headed Chromium on a real X display.

```
Browser (human) ──HTTPS/WebSocket──> noVNC ──> TigerVNC ──> XFCE on :1
                                                      │
Agent (CDP) ──ClusterIP/localhost──> cdp_forward ──> Chromium --remote-debugging-port=9222
```

## Why

Headless browser automation gets blocked, smells like a bot, and cannot do
2FA/CAPTCHA handoffs. Full VNC-only automation forces your agent to push pixels.
Agent Desktop splits the difference:

- **Human-grade login, machine-grade driving.** Log in once over noVNC; the
  agent then works the session over CDP (structured DOM, not screenshots).
- **Persistent profile.** Browser state lives on a PVC/volume and survives
  restarts and image upgrades.
- **Composable layers.** `base/` is a lean XFCE + TigerVNC + noVNC desktop.
  `cdp/` adds the agent side-door. An `mcp/` layer (planned) exposes both as
  [Model Context Protocol](https://modelcontextprotocol.io) servers for any
  MCP client (Claude Desktop, Cursor, Hermes, ...).
- **Self-hosted.** Your sessions, your hardware, your network policy.

## Layers

| Layer | Image | What it adds |
|---|---|---|
| `base/` | `agent-desktop-base` | Debian stable-slim, XFCE session, TigerVNC, noVNC 1.7 (HTTPS, auto-resize), Firefox ESR + Chromium, Nimbus Sans UI font |
| `cdp/` | `agent-desktop-cdp` | Chromium autostart with `--remote-debugging-port` (baked, gated by `CDP_AUTOSTART`), stdlib CDP forwarder (0.0.0.0:9223 -> 127.0.0.1:9222) |
| `mcp/` | `agent-desktop-mcp` | [playwright-mcp](https://github.com/microsoft/playwright-mcp) attached to the live CDP session (25 browser tools via accessibility snapshots) + stdlib auth proxy (bearer token + Origin allowlist) on 8931 |

## Quickstart (Docker)

```bash
# 1. base image
docker build -t agent-desktop-base base/

# 2. run it (open access - see Environment variables before exposing anything)
docker run -d -p 6080:6080 -e VNC_PASSWORD="$(openssl rand -base64 18)" agent-desktop-base

# 3. open https://localhost:6080  (self-signed cert: accept the warning once)
```

With the agent side-door:

```bash
docker build -t agent-desktop-cdp --build-arg BASE_IMAGE=agent-desktop-base cdp/
docker run -d -p 6080:6080 -p 127.0.0.1:9222:9223 \
  -v "$PWD/profile:/root/browser-profile" \
  -e VNC_PASSWORD="$(openssl rand -base64 18)" \
  --hostname desktop \
  agent-desktop-cdp
# agent drives: http://127.0.0.1:9222 (CDP)  |  human drives: https://localhost:6080 (noVNC)
```

Notes:
- `--hostname desktop` and the volume-mounted profile dir are what make the
  browser profile portable across restarts.
- Chromium refuses `--remote-debugging-port` on the default profile, hence the
  dedicated `--user-data-dir=/root/browser-profile` (baked into the autostart entry).

## MCP (Model Context Protocol)

The `mcp/` layer exposes the live, logged-in browser session as MCP tools over
Streamable HTTP - any MCP client (Claude Desktop, Cursor, Hermes, inspector,
your own SDK code) can drive it:

```bash
openssl rand -base64 18 > /tmp/mcp.token   # keep it out of git
docker run -d -p 6080:6080 -p 127.0.0.1:8931:8931 \
  -e VNC_PASSWORD="$(openssl rand -base64 18)" \
  -e MCP_TOKEN="$(cat /tmp/mcp.token)" \
  -v "$PWD/profile:/root/browser-profile" --hostname desktop \
  agent-desktop-mcp
```

Endpoint (browser tools): `http://127.0.0.1:8931/mcp` with `Authorization: Bearer $MCP_TOKEN`.
Endpoint (desktop actions): `http://127.0.0.1:8931/desktop` - same token, one auth
proxy, one audit stream, path-routed. Tools: `screenshot`, `click`, `type_text`,
`key`, `scroll`, `list_windows`, `activate_window`, `open_url` (X11 via
xdotool/imagemagick on display :1).
The auth proxy enforces the token per request, validates `Origin` when a
browser-context client sends one, rewrites `Host` for the upstream's
DNS-rebinding protection, and logs one JSON audit line per request to stdout.

Example client config (generic MCP / Hermes style):

```yaml
mcp_servers:
  desktop-browser:
    url: http://127.0.0.1:8931/mcp
    headers:
      Authorization: Bearer <token>
```

Verified against three independent clients: raw HTTP, `@modelcontextprotocol/inspector`
CLI, and the Python `mcp` SDK. A desktop-actions MCP server (screenshot/click/type
outside the browser) is tracked in issue #11.

## Kubernetes

Reference manifests in `manifests/` (secret-free by design):

```bash
./scripts/create-secrets.sh desktop            # pipes the VNC password from stdin, never a file
microk8s kubectl apply -f manifests/
```

Network policy guidance: publish **only** noVNC (NodePort/Ingress behind auth).
CDP (9223) and the planned MCP ports must stay cluster-internal - see
[`docs/security.md`](docs/security.md).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VNC_RESOLUTION` | `1920x1080` | Initial desktop size (browser resize events follow after) |
| `VNC_DEPTH` | `24` | Color depth |
| `VNC_PASSWORD` | (unset) | If set, VNC requires a password. If unset, **open access** - set it on any non-localhost bind |
| `BROWSER` | `/usr/bin/chromium` | Default browser for the desktop (firefox-esr also installed; use it for human daily-driver boxes) |
| `CDP_AUTOSTART` | `true` | cdp/mcp layers: `false` disables Chromium CDP autostart, the forwarder and MCP - desktop behaves like the plain base image |
| `MCP_TOKEN` | (unset) | mcp layer only: bearer token required by the auth proxy. **Required** when the MCP layer runs - the proxy refuses to start without it |

## Security model (short version)

- The desktop holds **logged-in sessions** - treat it as a crown jewel.
- noVNC is TLS with a runtime-generated self-signed cert (the private key
  never ships in an image layer). Raw VNC (5901) has no TLS - never publish it.
- CDP has **no authentication** (Chrome's design). Anyone who can reach the
  port owns the browser. Keep it node-local/cluster-internal, always.
- Full threat model and MUST-level rules: [`docs/security.md`](docs/security.md).

## Roadmap

See the [project board](https://github.com/orgs/sevenseven-tech/projects) and
open issues. Headlines: MCP browser tools, MCP desktop-actions server, audit
logging, hardened auth forwarder.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Secrets in PRs are an instant reject -
CI runs gitleaks on every push.

## License

MIT - see [`LICENSE`](LICENSE).
