#!/usr/bin/env bash
# Safe Avahi service discovery extension for an existing, working Family Control laptop.
# Does not touch PIN, timer, autostart, login or control_server.py.
set -Eeuo pipefail
(( EUID==0 )) || { echo 'Run using sudo from the adult account.' >&2; exit 1; }
systemctl is-active --quiet max-family-control.service || { echo 'Family Control is not running. No changes made.'; exit 1; }
[[ -f /etc/max-family-control/config.json ]] || { echo 'Family Control configuration missing.'; exit 1; }
if ! command -v avahi-daemon >/dev/null; then
  echo 'Avahi is required to let the Android app find the laptop automatically.'
  read -r -p 'Install the official Mint package avahi-daemon? [y/N]: ' YES
  [[ $YES =~ ^[Yy]$ ]] || { echo 'Cancelled. No change.'; exit 1; }
  apt-get update && apt-get install -y avahi-daemon
fi
DEST=/etc/avahi/services/family-control.service
if [[ -e "$DEST" ]]; then
  if grep -Fq '_maxfamily._tcp' "$DEST"; then
    echo 'Family Control discovery is already configured.'; exit 0
  else
    echo "A different service definition exists at $DEST. Refusing to overwrite it."; exit 1
  fi
fi
install -d /etc/avahi/services
cat > "$DEST" <<'EOF'
<?xml version="1.0" standalone='no'?><!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group><name replace-wildcards="yes">Family Control (%h)</name>
<service><type>_maxfamily._tcp</type><port>8743</port></service></service-group>
EOF
chmod 0644 "$DEST"
systemctl enable --now avahi-daemon.service
echo 'Wi-Fi discovery added. Timer, PIN and remote phone dashboard were not modified.'
echo 'The Android app can now search on the same Wi-Fi (if the router permits multicast discovery).'
