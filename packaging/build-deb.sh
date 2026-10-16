#!/usr/bin/env bash
# Build self-contained ParentPilot source .deb (native dependency resolution via APT).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=0.4.0~preview1
OUT="${1:-$ROOT/dist}"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
mkdir -p "$STAGING/DEBIAN" "$STAGING/usr/lib/parentpilot/desktop/assets" "$STAGING/usr/lib/parentpilot/icons" "$STAGING/usr/share/applications" "$STAGING/etc/xdg/autostart" "$STAGING/usr/bin" "$STAGING/usr/share/pixmaps"
cat > "$STAGING/DEBIAN/control" <<EOF
Package: parentpilot
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: \${misc:Depends}, python3, python3-tk, python3-gi, openssl, acl, chromium, avahi-daemon, xfce4-session, xfce4-panel, lightdm, pkexec, playerctl, pulseaudio-utils, dbus-x11
Maintainer: ParentPilot Project <parentpilot@example.invalid>
Description: ParentPilot family screen-time setup for Linux Mint XFCE
 Guided graphical setup creates a non-admin child account, parent PIN,
 screen-time timer, local phone controls, and a curated child desktop.
 Installs no child account or timer until an administrator finishes the wizard.
EOF
# Debian control files cannot expand misc Depends without debhelper.
sed -i 's/Depends: ${misc:Depends}, /Depends: /' "$STAGING/DEBIAN/control"
for f in control_server.py max_desktop.py max_desktop_supervisor.py parentpilot_lock_media.py admin.py; do
    install -m 0644 "$ROOT/desktop/$f" "$STAGING/usr/lib/parentpilot/desktop/$f"
done
for f in parentpilot-icon.png parentpilot-icon-128.png parentpilot-icon-64.png; do
    install -m 0644 "$ROOT/desktop/assets/$f" "$STAGING/usr/lib/parentpilot/desktop/assets/$f"
done
install -m 0644 "$ROOT/desktop/assets/parentpilot-icon-128.png" "$STAGING/usr/share/pixmaps/parentpilot.png"
install -m 0644 "$ROOT/packaging/parentpilot/youtube.svg" "$STAGING/usr/lib/parentpilot/icons/youtube.svg"
install -m 0644 "$ROOT/packaging/parentpilot/netflix.svg" "$STAGING/usr/lib/parentpilot/icons/netflix.svg"
install -m 0644 "$ROOT/packaging/parentpilot/wizard.py" "$STAGING/usr/lib/parentpilot/wizard.py"
install -m 0755 "$ROOT/packaging/parentpilot/setup_root.py" "$STAGING/usr/lib/parentpilot/setup-root"
cat > "$STAGING/usr/bin/parentpilot-setup" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/parentpilot/wizard.py "$@"
EOF
chmod 0755 "$STAGING/usr/bin/parentpilot-setup"
cat > "$STAGING/usr/share/applications/parentpilot-setup.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ParentPilot Family Setup
Comment=Set up a child account, parental controls and family apps
Exec=parentpilot-setup
Icon=parentpilot
Categories=Settings;System;
Terminal=false
StartupNotify=true
EOF
cat > "$STAGING/etc/xdg/autostart/parentpilot-setup-first-run.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ParentPilot First Run
Comment=First-time ParentPilot family setup; admin users only
Exec=parentpilot-setup --autostart
OnlyShowIn=XFCE;
Terminal=false
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
cat > "$STAGING/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
# NEVER provision the child from dpkg's root, non-graphical context.
# The wizard gets explicit consent and PolicyKit auth instead.
if [ "$1" = configure ]; then
    echo 'ParentPilot installed. Open "ParentPilot Family Setup" in the Mint menu to create a child account.'
fi
exit 0
EOF
chmod 0755 "$STAGING/DEBIAN/postinst"
cat > "$STAGING/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
# Deliberately preserve existing child accounts, timers, PINs and data on removal.
exit 0
EOF
chmod 0755 "$STAGING/DEBIAN/prerm"
find "$STAGING" -type d -exec chmod 0755 {} +
mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$STAGING" "$OUT/parentpilot_${VERSION}_all.deb"
echo "Created $OUT/parentpilot_${VERSION}_all.deb"
