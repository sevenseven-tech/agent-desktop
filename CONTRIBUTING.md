# Contributing to Agent Desktop

Thanks for thinking about contributing.

## Ground rules

- **Never commit secrets.** No passwords, tokens, or private keys in code,
  manifests, examples, or commit messages. Secrets are created at deploy time
  (`scripts/create-secrets.sh` pipes from stdin). CI runs gitleaks; findings
  block merge.
- **Layers stay composable.** `base/` must not depend on `cdp/` or `mcp/`.
  New capabilities go in a new layer or a ConfigMap, not into `start.sh`
  unless they belong to the plain desktop.
- **Verify what you claim.** PR descriptions state what was actually run and
  observed (build output, curl codes, `kubectl` readbacks). "Should work" is
  not a test result.

## Development loop

```bash
git clone https://github.com/sevenseven-tech/agent-desktop && cd agent-desktop
docker build -t agent-desktop-base base/
docker build -t agent-desktop-cdp --build-arg BASE_IMAGE=agent-desktop-base cdp/
docker run -d --name ad-dev -p 6080:6080 -e VNC_PASSWORD=devonly agent-desktop-cdp
# iterate; boot-test means: container healthy, https://localhost:6080 -> 200,
# CDP /json/version answers, and you actually looked at the desktop
docker rm -f ad-dev
```

Pitfalls that will bite you (all earned the hard way):

- `--no-install-recommends` drops Recommends-only packages silently:
  `ca-certificates`, `tigervnc-tools`, `xdg-utils`, and **fonts**
  (without `fonts-dejavu-core`, fontconfig resolves generic `Sans` to
  Liberation Mono and the whole desktop renders monospaced).
- TigerVNC flag is `-AlwaysShared`, not `-shared`, on Debian stable.
- noVNC >= 1.5 has no `launch.sh`; run `python3 -m websockify` with
  `PYTHONPATH` exported on its own line.
- X lock files (`/tmp/.X1-lock`, `/tmp/.X11-unix/X1`) must be cleaned on start
  or restarts die with "Server is already active for display 1".

## Style

- Shell: `set -euo pipefail` where feasible; keep `start.sh` POSIX-sh-safe.
- Python: stdlib-only for forwarders/supervisors (they run as PID-1 parents).
- Commits: imperative subject, explain the *why* in the body.
