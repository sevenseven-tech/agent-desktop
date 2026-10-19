# Agent Desktop - Security Model & Operational Rules

> The desktop holds **logged-in human sessions** (Google, banks, SaaS consoles).
> Every component that can drive it is a path to those sessions. Treat CDP and
> MCP endpoints like root shells, not like debug ports.

## Components and exposure

| Component | Port | Auth | Allowed exposure |
|---|---|---|---|
| noVNC (websockify) | 6080 | TLS + optional VNC password | NodePort/Ingress behind your auth proxy. TLS cert is generated at first start - never baked into an image |
| Raw VNC | 5901 | password only, **no TLS** | Never published. Container-internal only |
| CDP (Chromium) | 9222 (internal) / 9223 (forwarded) | **None** (Chrome design) | Cluster-internal / 127.0.0.1 host bind only. Never NodePort, never Ingress |
| MCP browser tools (planned) | 8931 | Bearer token + Origin allowlist | Cluster-internal; same rules as CDP |
| MCP desktop actions (planned) | 8932 | Bearer token + Origin allowlist | Cluster-internal; same rules as CDP |

## MUST rules

1. **No secrets in git, ever.** Passwords live in a password store (`pass`,
   Vault, SOPS) and enter the cluster via `scripts/create-secrets.sh` piping
   from stdin. Manifests reference Secrets by name only. CI runs gitleaks on
   every push; a planted-secret test keeps the gate honest.
2. **CDP/MCP stay node-local.** A CDP port reachable by anyone who can route to
   it is a full browser takeover - no password will save you. Bind services
   ClusterIP, forward host ports to `127.0.0.1` only, and use NetworkPolicies
   to pin which namespaces can reach them.
3. **MCP endpoints require bearer tokens + Origin validation** (MCP spec
   2026-07-28 marks Origin validation MUST on Streamable HTTP). Tokens are
   generated per deployment, stored as k8s Secrets, rotated like any credential.
4. **Audit every agent action.** Every MCP tool call logs one JSON line to
   stdout; `kubectl logs` is the audit trail. Keep it.
5. **The human keeps an eye open.** The noVNC session stays visible to the
   human while agents work. This is a deliberate control, not a demo feature:
   prompt injection from a hostile webpage can otherwise drive the whole
   desktop. If you automate untrusted sites, watch the session or isolate the
   profile.

## Threat model summary

- **Attacker on the network**: blocked by TLS on 6080, node-local binds,
  NetworkPolicies, and never publishing 5901.
- **Prompt injection via browsed content**: mitigated by human visibility,
  audit log, and (future) per-tool confirmation gates. Accepted residual risk:
  anything the agent can see, a hostile page can try to make it do.
- **Stolen MCP/CDP token/port**: equals session hijack - rotate tokens,
  pin source namespaces, keep the basic-auth proxy in front of noVNC only.
- **Image supply**: TLS cert private keys never ship in layers; runtime
  generation means a leaked image is not a leaked key.

## Known tradeoffs (accepted, documented)

- Single-user design: one human, one agent, one desktop. No multi-tenant isolation.
- Self-signed noVNC cert: one-time browser warning; bring your own cert if you
  front it with a real one.
- `--no-sandbox` Chromium: required in-container; the container is the sandbox.
