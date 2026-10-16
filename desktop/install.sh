#!/usr/bin/env bash
# Family Control 0.3 developer preview - FRESH Mint XFCE installations only.
# Does not upgrade an existing Max Family Control setup.
set -Eeuo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET=/opt/max-family-control
CFG=/etc/max-family-control
STATE=/var/lib/max-family-control
UNIT=max-family-control.service
AVAHI=/etc/avahi/services/family-control.service
say(){ printf '\n== %s ==\n' "$*"; }
die(){ echo "STOPPED: $*" >&2; exit 1; }
check(){
  echo 'Family Control - compatibility check (no changes)'
  command -v xfce4-session >/dev/null || die 'This installer currently supports Linux Mint XFCE.'
  for bin in python3 openssl systemctl loginctl adduser getent setfacl; do
    command -v "$bin" >/dev/null || die "$bin missing. Install dependency and retry."
  done
  python3 -c 'import tkinter' || die 'Missing python3-tk (sudo apt install python3-tk)'
  [[ -r "$BASE/control_server.py" && -r "$BASE/max_desktop.py" ]] || die 'Extract the whole package first.'
  if [[ -e "$CFG/config.json" || -e "$TARGET/control_server.py" ]]; then
    die 'An existing installation was found. Refusing to overwrite an existing child, PIN or saved time.'
  fi
  echo 'System prerequisites: PASS. Existing Family Control installation: none.'
  echo "Avahi discovery: $(command -v avahi-daemon || echo 'not installed; Android automatic discovery will require avahi-daemon')"
}
make_service(){
  cat > "/etc/systemd/system/$UNIT" <<'EOF'
[Unit]
Description=Family Control parental timer service
After=network.target
Wants=network.target
[Service]
Type=simple
User=maxfamily
Group=maxfamily
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -B /opt/max-family-control/control_server.py
WorkingDirectory=/opt/max-family-control
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/max-family-control
ProtectKernelTunables=true
ProtectControlGroups=true
CapabilityBoundingSet=
LockPersonality=true
RestrictSUIDSGID=true
[Install]
WantedBy=multi-user.target
EOF
}
install_new(){
  (( EUID==0 )) || die 'Run using sudo from the adult admin account.'
  [[ -n ${SUDO_USER:-} && ${SUDO_USER:-} != root ]] || die 'Sign into an adult admin account and run with sudo.'
  check
  say 'New family setup'
  read -r -p 'Child display name (e.g. Max): ' NAME
  [[ $NAME =~ ^[A-Za-z][A-Za-z\ 0-9_-]{0,31}$ ]] || die 'Use a name of 1–32 letters, numbers, spaces, hyphens or underscores.'
  read -r -p 'Child Linux username (e.g. max): ' CHILD
  [[ $CHILD =~ ^[a-z][a-z0-9_-]{0,30}$ ]] || die 'Use lowercase letters, numbers, hyphen or underscore; start with a letter.'
  [[ $CHILD != "$SUDO_USER" && $CHILD != maxfamily && $CHILD != root ]] || die 'Choose a separate child account.'
  CREATE=0
  if id "$CHILD" >/dev/null 2>&1; then
    [[ $(id -u "$CHILD") -ge 1000 ]] || die 'Refusing to use a system account.'
    if id -nG "$CHILD" | tr ' ' '\n' | grep -Eq '^(sudo|wheel|adm)$'; then
      die 'Child is a privileged user. Use a non-admin account.'
    fi
    echo "Will use existing standard account: $CHILD."
  else
    CREATE=1
    echo "Will CREATE a standard account: $CHILD."
  fi
  read -r -s -p 'New 6-digit PARENT PIN: ' P1; echo
  read -r -s -p 'Repeat parent PIN: ' P2; echo
  [[ $P1 =~ ^[0-9]{6}$ && $P1 == "$P2" ]] || die 'PIN must be six matching digits. Nothing changed.'
  [[ $P1 != 000000 && $P1 != 123456 && $P1 != 111111 ]] || die 'Choose a less predictable PIN.'
  echo "Will configure '$NAME' ($CHILD). Existing apps and accounts will not be removed."
  read -r -p 'Type INSTALL to proceed: ' ANSWER
  [[ $ANSWER == INSTALL ]] || die 'Cancelled before changes.'
  if (( CREATE )); then
    adduser --disabled-password --gecos "$NAME,,," "$CHILD"
    echo 'Set a Linux account password for the new child (separate from the 6-digit parental PIN).'
    echo 'The child password is needed if automatic login is disabled or for unlocking their own XFCE screen.'
    passwd "$CHILD" || die 'Child created but password setting failed. Set it using sudo passwd before signing in.' 
  fi
  if ! id -u maxfamily >/dev/null 2>&1; then
    useradd --system --user-group --home-dir "$STATE" --shell /usr/sbin/nologin --no-create-home maxfamily
  fi
  install -d -o root -g root -m 0755 "$TARGET"
  install -d -o root -g root -m 0755 "$TARGET/assets"
  for img in parentpilot-icon.png parentpilot-icon-128.png parentpilot-icon-64.png; do
    install -o root -g root -m 0644 "$BASE/assets/$img" "$TARGET/assets/$img"
  done
  for f in control_server.py max_desktop.py max_desktop_supervisor.py admin.py; do
    install -o root -g root -m 0644 "$BASE/$f" "$TARGET/$f"
  done
  install -d -o root -g maxfamily -m 0750 "$CFG"
  install -d -o maxfamily -g maxfamily -m 0700 "$STATE"
  FAMILY_CHILD="$CHILD" FAMILY_NAME="$NAME" FAMILY_PIN="$P1" PYTHONDONTWRITEBYTECODE=1 python3 - "$TARGET" "$CFG/config.json" <<'PY'
import json, os, sys
sys.path.insert(0, sys.argv[1]); from control_server import atomic_write, hash_password
atomic_write(sys.argv[2], {'child':os.environ['FAMILY_CHILD'], 'display_name':os.environ['FAMILY_NAME'], 'password': hash_password(os.environ['FAMILY_PIN'])})
PY
  unset P1 P2
  chown root:maxfamily "$CFG/config.json"; chmod 0640 "$CFG/config.json"
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 825 \
    -keyout "$CFG/server.key" -out "$CFG/server.crt" -subj '/CN=ParentPilot' \
    -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1' >/dev/null 2>&1
  chown root:maxfamily "$CFG/server.key"; chmod 0640 "$CFG/server.key"
  chmod 0644 "$CFG/server.crt"
  (umask 077; openssl rand -hex 32 > "$CFG/desktop-token")
  chown root:maxfamily "$CFG/desktop-token"; chmod 0640 "$CFG/desktop-token"
  setfacl -m "u:$CHILD:--x" "$CFG"
  setfacl -m "u:$CHILD:r--" "$CFG/desktop-token"
  runuser -u "$CHILD" -- test -r "$CFG/desktop-token" || die 'Child cannot read desktop token.'
  if runuser -u "$CHILD" -- test -r "$CFG/config.json"; then die 'Unsafe permissions for PIN hash.'; fi
  if runuser -u "$CHILD" -- test -r "$CFG/server.key"; then die 'Unsafe permissions for HTTPS key.'; fi
  PYTHONDONTWRITEBYTECODE=1 python3 - "$TARGET" "$STATE/state.json" <<'PY'
import sys
sys.path.insert(0,sys.argv[1]); from control_server import atomic_write,clean_state
atomic_write(sys.argv[2], clean_state())
PY
  chown maxfamily:maxfamily "$STATE/state.json"; chmod 0600 "$STATE/state.json"
  install -d -o "$CHILD" -g "$(id -gn "$CHILD")" -m 0700 "/home/$CHILD/.config/autostart"
  cat > "/home/$CHILD/.config/autostart/family-control.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ParentPilot Timer
Comment=ParentPilot screen-time counter and parent approval
Exec=/usr/bin/python3 -B /opt/max-family-control/max_desktop_supervisor.py
Terminal=false
OnlyShowIn=XFCE;
X-GNOME-Autostart-enabled=true
EOF
  chown "$CHILD:$(id -gn "$CHILD")" "/home/$CHILD/.config/autostart/family-control.desktop"
  chmod 0644 "/home/$CHILD/.config/autostart/family-control.desktop"
  make_service
  systemctl daemon-reload
  systemctl enable --now "$UNIT"
  say 'Service started.'
  if command -v avahi-daemon >/dev/null 2>&1; then
    install -d -m 0755 /etc/avahi/services
    cat > "$AVAHI" <<'EOF'
<?xml version="1.0" standalone='no'?><!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group><name replace-wildcards="yes">Family Control (%h)</name>
<service><type>_maxfamily._tcp</type><port>8743</port></service></service-group>
EOF
    chmod 0644 "$AVAHI"
    systemctl enable --now avahi-daemon.service || echo 'Warning: Avahi did not start. Android discovery may be unavailable.'
    echo 'Android automatic Wi-Fi discovery advertised via Avahi.'
  else
    echo 'Android auto-discovery requires: sudo apt install avahi-daemon'
    echo 'Then re-run: sudo bash install.sh --discovery'
  fi
  if command -v lightdm >/dev/null 2>&1; then
    read -r -p "Automatically sign $CHILD into XFCE on laptop startup? [y/N]: " AUTO
    if [[ $AUTO =~ ^[Yy]$ ]]; then
      install -d /etc/lightdm/lightdm.conf.d
      cat > /etc/lightdm/lightdm.conf.d/96-family-control-autologin.conf <<EOF
[Seat:*]
autologin-user=$CHILD
autologin-user-timeout=0
EOF
      echo 'LightDM autologin configured. Other existing LightDM settings may take precedence.'
    fi
  fi
  say 'Installation complete'
  echo "Child: $NAME ($CHILD). Phone controls: https://<laptop-LAN-IP>:8743"
  echo 'Browser may report a self-signed certificate. Do not publish this port on the internet.'
  echo 'On a different network, use a private Tailscale HTTPS address instead.'
  echo "Service: systemctl status $UNIT"
  echo 'This is an application overlay, not a tamper-proof OS lock.'
}
install_discovery(){
  (( EUID==0 )) || die 'Run with sudo.'
  [[ -f "$CFG/config.json" ]] || die 'Family Control is not installed.'
  command -v avahi-daemon >/dev/null || die 'Install avahi-daemon first.'
  install -d /etc/avahi/services
  cat > "$AVAHI" <<'EOF'
<?xml version="1.0" standalone='no'?><!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group><name replace-wildcards="yes">Family Control (%h)</name><service><type>_maxfamily._tcp</type><port>8743</port></service></service-group>
EOF
  chmod 0644 "$AVAHI"
  systemctl enable --now avahi-daemon.service
  echo 'mDNS discovery enabled.'
}
case "${1:---check}" in
  --check) check;;
  --install) install_new;;
  --discovery) install_discovery;;
  --status) systemctl status "$UNIT" --no-pager;;
  *) echo 'Usage: bash install.sh --check | sudo bash install.sh --install|--discovery|--status'; exit 2;;
esac
