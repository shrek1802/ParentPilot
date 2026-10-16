# ParentPilot Linux Mint XFCE .deb

A fresh-install **developer preview** package for Linux Mint 22.x XFCE.

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

## CI verification

The GitHub workflow runs the local timer, PIN API, installer validation, package inspection, and publishes a downloadable `.deb` artifact. It cannot verify login-session integration on a physical Mint XFCE machine.
