#!/usr/bin/env bash
# Optional secure remote setup using official Tailscale Serve (NOT Funnel).
set -Eeuo pipefail
say(){ printf '\n%s\n' "$*"; }
die(){ say "ERROR: $*" >&2; exit 1; }
(( EUID==0 )) || die 'Run as sudo on Ash account.'
[[ -n ${SUDO_USER:-} && ${SUDO_USER:-} != root ]] || die 'Run this from the adult admin account.'
CHILD="$(python3 -c 'import json; print(json.load(open("/etc/max-family-control/config.json"))["child"])')"
[[ ${SUDO_USER:-} != "$CHILD" ]] || die 'Do not run this from the child account.' 
systemctl is-active --quiet max-family-control.service || die 'Family Control is not running.'

say 'FAMILY CONTROL — AWAY-FROM-HOME PHONE ACCESS'
say 'This connects the laptop and parent phones through your private Tailscale network.'
say 'It will not configure router port forwarding or use public Tailscale Funnel.'
if ! command -v tailscale >/dev/null 2>&1; then
  say 'Tailscale is not installed. Official Linux instructions: https://tailscale.com/docs/install/linux'
  say 'I can download the official Tailscale installer from https://tailscale.com/install.sh and run it.'
  read -r -p 'Install Tailscale from its official website? [y/N]: ' yes
  [[ "$yes" =~ ^[Yy]$ ]] || die 'Cancelled. Existing Family Control remains unchanged.'
  command -v curl >/dev/null || die 'curl not installed. Please install Tailscale manually from its official site.'
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT
  curl --fail --show-error --silent --location --max-time 35 https://tailscale.com/install.sh -o "$tmp" || die 'Could not download installer. Nothing changed.'
  [[ -s "$tmp" ]] || die 'Downloaded installer is empty.'
  say 'Running the downloaded official Tailscale installer...'
  sh "$tmp"
fi
command -v tailscale >/dev/null || die 'Tailscale installation was unsuccessful.'
if ! tailscale status --json 2>/dev/null | python3 -c 'import json,sys; s=json.load(sys.stdin); sys.exit(0 if s.get("BackendState")=="Running" else 1)'; then
  say 'Now connect this laptop to YOUR Tailscale account (for Mum/Dad).'
  say 'A browser sign-in link may appear. Complete it, then run this script again.'
  tailscale up
  if ! tailscale status --json 2>/dev/null | python3 -c 'import json,sys; s=json.load(sys.stdin); sys.exit(0 if s.get("BackendState")=="Running" else 1)'; then
    die 'Finish signing in to Tailscale, then re-run this setup.'
  fi
fi
say 'Confirming the private proxy is not overwriting a different existing Serve configuration...'
SERVE="$(tailscale serve status --json 2>/dev/null || true)"
if [[ -n "$SERVE" ]] && ! python3 - "$SERVE" <<'PY'
import json,sys
try: s=json.loads(sys.argv[1])
except Exception: sys.exit(0)
# Empty dict / empty web / no TCP maps means unconfigured.
occupied = bool(s.get('Web') or s.get('TCP') or s.get('Services'))
sys.exit(1 if occupied else 0)
PY
then
  say 'An existing Tailscale Serve configuration was found. Not replacing it.'
  say 'Check first with: sudo tailscale serve status'
  exit 0
fi
say 'Starting private HTTPS address. May ask you to enable HTTPS certificates in Tailscale admin.'
tailscale serve --bg --https=443 https+insecure://127.0.0.1:8743 || die 'Tailscale Serve did not start. Parent LAN page still works.'
say 'Tailscale Serve status:'
tailscale serve status
say 'Install Tailscale on Mum’s and Dad’s phones and sign in to the SAME private tailnet.'
say 'Save the private https://...ts.net URL shown above as “Max Controls” on each phone.'
say 'Never use Tailscale Funnel or forward port 8743 on the home router.'
say 'To stop remote access later (does not stop the laptop timer): sudo tailscale serve --https=443 off'
