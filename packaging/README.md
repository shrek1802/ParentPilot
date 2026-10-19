# ParentPilot Linux installer — Preview 7

ParentPilot provides a guided setup for family screen-time controls on Debian-based Linux desktops using **XFCE on X11**.

> **Developer preview — new installations only.** The Debian package is **not itself a direct replacement installer** for an already configured ParentPilot laptop. Do not install over an existing child's setup. Use a spare laptop or disposable VM for evaluation.

## Install with the graphical wizard

1. Download a successful Linux build from [GitHub Actions](https://github.com/shrek1802/ParentPilot/actions/workflows/build-linux-deb.yml). Preview 7 uses the versioned `parentpilot_0.5.0~preview7_all.deb` file inside an artifact ZIP. Builds on different branches may contain different versions.
2. Sign into a new XFCE/X11 laptop with an **adult administrator** account.
3. Open the DEB in your distro's package manager and approve installation.
4. Open **ParentPilot Family Setup** from the applications menu. The compatibility check runs before child account changes.
5. Choose the child's display name, standard Linux username, child login password and **separate six-digit parent PIN**.
6. Choose supervised YouTube/YouTube Kids shortcuts, optional Netflix, Chromium filtering, optional screen pictures and optional LightDM auto-login where supported.
7. Review the configuration carefully, click **Install ParentPilot**, and approve the administrator authentication prompt.
8. After setup, sign into the child's account and test granting time, expiry, pause and parent PIN access.

No child account, login changes or screen-time service are created by the DEB package installation alone. Setup changes occur only after completing the graphical wizard with administrator approval.

### Supported desktops and environments

| Environment | Current status |
| --- | --- |
| Linux Mint XFCE on X11 with systemd | Primary intended target; full fresh-install workflow needs further independent physical testing |
| Debian 11–13 using XFCE/X11 | Candidate; compatibility checks tested, complete installation not established |
| Xubuntu / Ubuntu family with XFCE/X11 | Candidate; complete installation not established |
| LMDE with XFCE/X11 added | Candidate; complete installation not established |
| MX Linux configured with systemd + XFCE/X11 | Candidate; requires hands-on testing |
| Raspberry Pi OS with systemd + XFCE/X11 | Candidate; hardware testing required |
| GNOME, Cinnamon, KDE, MATE, LXQt, Wayland | Not supported by the current fullscreen overlay |

Passing an automated compatibility check does **not** certify a distribution. A Linux distribution alone does not determine whether its login manager, desktop session, application packages and media controls work correctly.

## Updating after the first installation

Fresh laptops provisioned through the **Preview 7** wizard include a separate, parent-only **ParentPilot Updates** application (Applications → Settings) and an adult-login update notification. Select Stable (default) or Preview, review release notes, then approve a new update with administrator authentication. The child must be signed out.

The updater checks official published GitHub Releases, validates the SHA-256 digest, backs up the PIN, config, state, saved pictures and deployed control files, then installs the DEB without creating accounts or resetting screen time. It attempts service recovery on failure; full Debian-package rollback is not yet guaranteed. This updater **refuses older or manually customised ParentPilot installations** to protect their working setup.

No update notification appears until a newer qualifying GitHub Release is published. See [the update guide](../docs/UPDATES.md) and test the upgrade on a spare laptop before relying on it.

## Child desktop and services

- Setup creates a **non-admin child Linux account**, a simplified XFCE launcher panel and a background timer service.
- Parents can set/add time, pause/resume or end access through a PIN-protected browser dashboard. The child's desktop displays the time status.
- The expired/paused overlay offers a six-digit parent PIN field, **Switch user** and a shutdown option.
- YouTube Kids age bands, a supervised Google account and Netflix Kids profiles or adult profile locks must be configured **inside those services**. ParentPilot cannot configure them for you.
- Chromium policy filtering, if enabled, can affect **every Chromium user** on the machine, including adults.
- Menu shortcut hiding is cosmetic and is not an operating-system app restriction. The screen lock is **best-effort**, not a tamper-proof kiosk.


## Optional screen pictures (Preview 7)

Screen viewing is **off by default**. A parent can enable it during the administrator-led setup wizard. After signing into the parent dashboard, they can:

- Request an individual screenshot. A clear notice appears on the child desktop before capture; the child is not asked to approve every request.
- Tap a picture to enlarge it and zoom.
- Select **Save this picture** to keep a particular image for later discussion. Unsaved pictures expire after two minutes.
- Revisit, download or delete pictures from the private saved gallery (20-picture limit).

This is **not live video, hidden monitoring or automatic recording**. Requests have a 45-second interval. Saved files remain locally on the child laptop until deleted. Browser access requires parent authentication, and save/delete operations require anti-CSRF protection. Screen capture uses GTK/Gdk on X11 and still needs testing across different desktops.

## Lock-screen reliability (Preview 7)

The child's desktop supervisor uses a per-user, single-instance operating-system lock. If multiple login autostarts run, extra supervisors exit instead of opening competing lock windows. A temporarily unavailable status request does not destroy an established pause/expiry overlay; the desktop displays a connection warning and offers adult recovery through **Switch user**. The X11 raise helper reduces repeated Tk window focus changes. These protections are tested in code, but actual window behaviour still needs more physical-device testing.

## Android discovery and remote access

The optional [Android companion](../ANDROID_INSTALL.md) uses local network service discovery to locate the Linux laptop and opens the HTTPS dashboard in a phone browser. It does not store the parent PIN.

- Use the **same trusted Wi-Fi** for local discovery. Guest isolation and some phone hotspots block mDNS.
- Use a **private VPN** such as Tailscale for remote access; configure the private HTTPS endpoint on the laptop.
- **Never forward the parental control port publicly**, disable HTTPS verification, or expose the control panel via a public tunnel to make discovery work.
- Current local certificates are self-signed, so verify the laptop identity before accepting a browser warning.

## Privacy, repair and removal

- Parent PINs are stored using salted hashes. Never share private configuration, certificates, session tokens or saved screen pictures in public issues.
- The fresh-install wizard refuses to overwrite existing settings. A separate update tool upgrades only marked DEB-managed installations; migrations from older customised installations are not supported.
- Removing the DEB does **not** remove the child account, timer data or settings. A fully guided removal tool is still planned.
- If provisioning fails midway, manual cleanup of a partially created child account or configuration may be required. This is one reason to evaluate the installer on a spare machine first.

## Build and test from source

From the repository root, on a suitable development machine:

```bash
python3 desktop/test_server.py
python3 desktop/test_lock_stability.py
python3 desktop/test_supervisor_singleton.py
python3 packaging/test_installer.py
python3 packaging/test_compatibility.py
bash packaging/build-deb.sh
```

CI checks the Python syntax, application logic, mock compatibility scenarios and DEB contents. It **cannot establish that the screen overlay, screenshot capture or installer will behave correctly on every real laptop**.

The project is in a public **testing stage**. Update mechanisms need on-device testing and independent signature verification before a stable public release. Please report results without including child-identifying information. The [project homepage and overview](../README.md) describe the current features and release status.
