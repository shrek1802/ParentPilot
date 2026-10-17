# ParentPilot Debian-family XFCE/X11 .deb (v0.5 preview)

A fresh-install **developer preview** for XFCE on X11 on Linux Mint, Debian and Ubuntu-based Linux. It is not yet a universal Debian-family parental-control app.

## What happens

1. Install the `.deb` through Mint's package installer (APT resolves dependencies).
2. Launch **ParentPilot Family Setup** from the Mint app menu. The wizard also offers to open when an administrator next logs into XFCE; it does not run for non-admin users.
3. Fill in the child name, separate Linux username/password, six-digit parent PIN, YouTube Kids vs supervised YouTube, Netflix shortcut, auto login and optional Chromium policy.
4. Authenticate with your normal administrator password when asked by PolicyKit. The separate setup helper creates the non-admin account and configures the child environment. No administrator password is stored by ParentPilot.
5. The child account starts with the ParentPilot screen-time limit **paused** until the parent grants time through the HTTPS dashboard. Avahi broadcasts `_maxfamily._tcp` so the Android companion can discover it on the same Wi-Fi.

## Child desktop

- Curated bottom XFCE panel (Files, child Chromium, YouTube Kids/supervised YouTube and optional Netflix, plus clock and status icons)
- Dedicated Chromium app-style launchers for YouTube and Netflix
- Family-oriented Chromium enterprise policies: family Cloudflare DoH, Google SafeSearch, YouTube Restricted Mode; Kids choice additionally blocks normal YouTube domains
- Hides a shortlist of advanced package-management, terminal and other-browser **menu icons in the CHILD account only**; does not delete applications or alter the parent's XFCE panel
- Uses existing, tested single-window ParentPilot PIN screen + audio mute and media pause helper for X11

**Important:** The family-filter Chromium policy is system-wide for the Chromium application (not Google Chrome). Hiding icons is cosmetic and does **not** prevent a technically capable child from running software, using alternative browsers or bypassing an X11 overlay. YouTube maturity levels must be set up separately with YouTube Kids or Family Link. Netflix needs a Kids profile and adult PINs configured on Netflix itself, and DRM playback may need Widevine or a different supported browser. ParentPilot does not bypass Netflix or Widevine licensing.

## Safety

The package's post-install script creates **no accounts** and never overwrites `/opt/max-family-control` or `/etc/max-family-control`. The wizard's privileged helper refuses to run if an existing ParentPilot/Max Family Control installation is found. **Do not install this fresh-setup package on Max's currently working laptop**, even though package installation itself won't overwrite the configured files. Until tested on a separate computer/VM, treat this as a development preview.

Uninstalling the package does **not** remove a child account, PIN state, autologin, Chromium policy or the running timer service: it intentionally preserves user data. A future explicit uninstall/repair wizard is required for complete cleanup.

## Build from source

From the repository root: `bash packaging/build-deb.sh`. Requires `dpkg-deb` (provided by `dpkg`). Run `python3 desktop/test_server.py` and `python3 packaging/test_installer.py` for smoke tests.

## Wider Debian compatibility (v0.5)

The installer has an **automatic platform check on its Welcome page** before it requests passwords. The parent sees the detected Linux distribution, desktop/display session and understandable blockers before creating a child account. The elevated setup helper repeats the package/system checks; it never blindly installs on a different distribution.

| Environment | Status |
| --- | --- |
| Linux Mint 21/22 XFCE **on X11** | Target; previously validated on one Dell with local v0.2 patches; v0.5 fresh install not device-tested |
| Debian 12/13 **XFCE on X11, systemd** | Installer detects compatible components; live install **not yet tested** |
| Xubuntu / Ubuntu **XFCE on X11, systemd** | Installer detects compatible components; live install **not yet tested** |
| Other Debian-based XFCE/X11 desktops | Experimental; wizard warns if the distribution is not in the main three |
| Debian 11 or older / Python 3.9 or older | **Not supported** by this build |
| GNOME, KDE, Cinnamon, MATE, LXQt | **Not supported** by the current XFCE overlay/panel integration |
| Wayland sessions | **Not supported**: X11 stacking and window controls may not work |
| Distros without systemd | **Not supported**: the service setup uses systemd |

The package installs core requirements; it recommends Chromium and audio helpers. It **does not silently change the system's desktop or display manager**. If XFCE, Chromium, Polkit/`pkexec`, or (when selecting automatic login) LightDM are missing, the wizard explains that setup is not ready. A real cross-desktop version would need separate lock/panel integrations and testing for GNOME/KDE/Wayland.

## Important for parents

1. Install on a **spare, newly set-up** XFCE/X11 machine first, not a laptop whose ParentPilot timer already works.
2. Open **ParentPilot Family Setup** from the application menu; the wizard checks compatibility on the first page.
3. Choose a child name and separate Linux login details, followed by the private parent PIN. Finish with normal administrator authorisation.
4. Once the child desktop opens, configure the real YouTube Kids maturity level, Family Link supervision (if selected), and Netflix Kids profile yourself. Shortcuts or browser filters alone don't make content automatically age-appropriate.
5. On the same Wi-Fi, open the ParentPilot Android app and tap **Find nearby laptop**. The setup automatically enables Avahi `_maxfamily._tcp` discovery on port 8743.

No unattended child account is created by installing the `.deb`. The optional screen-viewing feature discussed for a later release is **not implemented in this package**; it would need an authenticated, child-visible opt-in design.