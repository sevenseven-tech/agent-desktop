#!/usr/bin/env bash
# Create cluster Secrets without ever writing secret values to files or git.
#
# Usage:
#   pass show my/vnc-password | ./scripts/create-secrets.sh vnc desktop
#   openssl rand -base64 24   | ./scripts/create-secrets.sh mcp desktop
#
#   $1 = which secret (vnc|mcp)   $2 = namespace   KUBECTL env to override binary
set -euo pipefail

WHICH="${1:?usage: create-secrets.sh <vnc|mcp> <namespace>}"
NS="${2:?usage: create-secrets.sh <vnc|mcp> <namespace>}"
KUBECTL="${KUBECTL:-kubectl}"

VALUE="$(cat)"
[ -n "$VALUE" ] || { echo "ERROR: empty value on stdin" >&2; exit 1; }

case "$WHICH" in
  vnc) NAME=vnc-password KEY=password ;;
  mcp) NAME=mcp-auth     KEY=token    ;;
  *) echo "ERROR: unknown secret '$WHICH' (use vnc or mcp)" >&2; exit 1 ;;
esac

printf '%s' "$VALUE" | "$KUBECTL" -n "$NS" create secret generic "$NAME" \
  --from-file="$KEY=/dev/stdin" --dry-run=client -o yaml | "$KUBECTL" apply -f -
echo "applied secret/$NAME in namespace/$NS (value never touched disk)"
