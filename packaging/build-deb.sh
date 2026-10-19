#!/usr/bin/env bash
# Build self-contained ParentPilot source .deb (native dependency resolution via APT).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=0.5.0~preview7
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
Depends: \${misc:Depends}, python3, python3-tk, python3-gi, gir1.2-gtk-3.0, gir1.2-gdkpixbuf-2.0, openssl, acl, chromium | chromium-browser, avahi-daemon, xfce4-session, xfce4-panel, pkexec, libnotify-bin, ca-certificates, playerctl, pulseaudio-utils, dbus-x11, libx11-6
Suggests: lightdm
Maintainer: ParentPilot Project <47456335+shrek1802@users.noreply.github.com>
Homepage: https://github.com/shrek1802/ParentPilot
Description: ParentPilot family screen-time setup for Debian-family XFCE/X11
 Guided graphical setup creates a non-admin child account, parent PIN,
 screen-time timer, local phone controls, and a curated child desktop.
 Optional parent-requested screen pictures and private saved gallery are off by default.
 Installs no child account or timer until an administrator finishes the wizard.
EOF
# Debian control files cannot expand misc Depends without debhelper.
sed -i 's/Depends: ${misc:Depends}, /Depends: /' "$STAGING/DEBIAN/control"
for f in control_server.py max_desktop.py max_desktop_supervisor.py parentpilot_lock_media.py admin.py screen_view.py parentpilot_screen_parent.js; do
    install -m 0644 "$ROOT/desktop/$f" "$STAGING/usr/lib/parentpilot/desktop/$f"
done
for f in parentpilot-icon.png parentpilot-icon-128.png parentpilot-icon-64.png; do
    install -m 0644 "$ROOT/desktop/assets/$f" "$STAGING/usr/lib/parentpilot/desktop/assets/$f"
done
install -m 0644 "$ROOT/desktop/assets/parentpilot-icon-128.png" "$STAGING/usr/share/pixmaps/parentpilot.png"
# Recognisable app icon in desktop menus and software centres.
mkdir -p "$STAGING/usr/share/icons/hicolor/64x64/apps" "$STAGING/usr/share/icons/hicolor/128x128/apps" "$STAGING/usr/share/metainfo"
install -m 0644 "$ROOT/desktop/assets/parentpilot-icon-64.png" "$STAGING/usr/share/icons/hicolor/64x64/apps/parentpilot.png"
install -m 0644 "$ROOT/desktop/assets/parentpilot-icon-128.png" "$STAGING/usr/share/icons/hicolor/128x128/apps/parentpilot.png"
cat > "$STAGING/usr/share/metainfo/uk.parentpilot.ParentPilot.metainfo.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>uk.parentpilot.ParentPilot</id>
  <name>ParentPilot Family Setup</name>
  <summary>Friendly family screen-time setup for XFCE/X11 Linux laptops</summary>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>MIT</project_license>
  <description>
    <p>Set up a separate child account, screen-time rules and child-friendly
    shortcuts with a guided parent wizard. Fresh Debian-family XFCE/X11
    installations only. Existing family settings are never automatically changed.</p>
  </description>
  <launchable type="desktop-id">parentpilot-setup.desktop</launchable>
  <url type="homepage">https://github.com/shrek1802/ParentPilot</url>
</component>
EOF
install -m 0644 "$ROOT/packaging/parentpilot/youtube.svg" "$STAGING/usr/lib/parentpilot/icons/youtube.svg"
install -m 0644 "$ROOT/packaging/parentpilot/netflix.svg" "$STAGING/usr/lib/parentpilot/icons/netflix.svg"
install -m 0644 "$ROOT/packaging/parentpilot/wizard.py" "$STAGING/usr/lib/parentpilot/wizard.py"
install -m 0644 "$ROOT/packaging/parentpilot/preflight.py" "$STAGING/usr/lib/parentpilot/preflight.py"
# Parent-only updater: read-only version checks, privileged verified DEB upgrades.
install -m 0644 "$ROOT/packaging/parentpilot/update_release.py" "$STAGING/usr/lib/parentpilot/update_release.py"
install -m 0644 "$ROOT/packaging/parentpilot/updates_gui.py" "$STAGING/usr/lib/parentpilot/updates_gui.py"
install -m 0755 "$ROOT/packaging/parentpilot/update_install.py" "$STAGING/usr/lib/parentpilot/update_install.py"
cat > "$STAGING/usr/bin/parentpilot-updates" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/parentpilot/updates_gui.py "$@"
EOF
chmod 0755 "$STAGING/usr/bin/parentpilot-updates"
cat > "$STAGING/usr/share/applications/parentpilot-updates.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ParentPilot Updates
Comment=Check for ParentPilot updates and review what has changed
Exec=parentpilot-updates
Icon=parentpilot
Categories=Settings;System;
Terminal=false
StartupNotify=true
EOF
cat > "$STAGING/etc/xdg/autostart/parentpilot-update-check.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ParentPilot Update Check
Comment=Show update notifications in adult administrator XFCE sessions only
Exec=parentpilot-updates --notify
OnlyShowIn=XFCE;
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
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
    if [ -n "${2:-}" ]; then
        echo 'ParentPilot package upgraded. Existing child settings were preserved. Use ParentPilot Updates to deploy verified program files to configured laptops.'
    else
        echo 'ParentPilot installed. Open "ParentPilot Family Setup" from the applications menu to create a child account.'
    fi
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
