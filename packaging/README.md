# ParentPilot Linux installer — Preview 2

ParentPilot provides a guided setup for family screen-time controls on Debian-based Linux desktops using **XFCE on X11**.

> **Developer preview — new installations only.** The Debian package is **not an in-place updater** for an already configured ParentPilot laptop. Do not install over an existing child's setup. Use a spare laptop or disposable VM for evaluation.

## Install with the graphical wizard

1. Download a successful Linux build from [GitHub Actions](https://github.com/shrek1802/ParentPilot/actions/workflows/build-linux-deb.yml). Preview 2 uses the versioned `parentpilot_0.5.0~preview2_all.deb` file inside an artifact ZIP. Builds on different branches may contain different versions.
2. Sign into a new XFCE/X11 laptop with an **adult administrator** account.
3. Open the DEB in your distro's package manager and approve installation.
4. Open **ParentPilot Family Setup** from the applications menu. The compatibility check runs before child account changes.
5. Choose the child's display name, standard Linux username, child login password and **separate six-digit parent PIN**.
6. Choose supervised YouTube/YouTube Kids shortcuts, optional Netflix, Chromium filtering and optional LightDM auto-login where supported.
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

## Child desktop and services

- Setup creates a **non-admin child Linux account**, a simplified XFCE launcher panel and a background timer service.
- Parents can set/add time, pause/resume or end access through a PIN-protected browser dashboard. The child's desktop displays the time status.
- The expired/paused overlay offers a six-digit parent PIN field, **Switch user** and a shutdown option.
- YouTube Kids age bands, a supervised Google account and Netflix Kids profiles or adult profile locks must be configured **inside those services**. ParentPilot cannot configure them for you.
- Chromium policy filtering, if enabled, can affect **every Chromium user** on the machine, including adults.
- Menu shortcut hiding is cosmetic and is not an operating-system app restriction. The screen lock is **best-effort**, not a tamper-proof kiosk.


> This version predates the experimental screenshot gallery and single-instance supervisor refinements available in the Preview 6 development branch. See the draft pull request for that work. Screenshots and saved-picture features should not be assumed present in this Preview 2 package.

## Android discovery and remote access

The optional [Android companion](../ANDROID_INSTALL.md) uses local network service discovery to locate the Linux laptop and opens the HTTPS dashboard in a phone browser. It does not store the parent PIN.

- Use the **same trusted Wi-Fi** for local discovery. Guest isolation and some phone hotspots block mDNS.
- Use a **private VPN** such as Tailscale for remote access; configure the private HTTPS endpoint on the laptop.
- **Never forward the parental control port publicly**, disable HTTPS verification, or expose the control panel via a public tunnel to make discovery work.
- Current local certificates are self-signed, so verify the laptop identity before accepting a browser warning.

## Privacy, repair and removal

- Parent PINs are stored using salted hashes. Never share private configuration, certificates, session tokens or saved screen pictures in public issues.
- The installer refuses to overwrite an already configured setup. An automatic repair, migration and upgrade path is not available yet.
- Removing the DEB does **not** remove the child account, timer data or settings. A fully guided removal tool is still planned.
- If provisioning fails midway, manual cleanup of a partially created child account or configuration may be required. This is one reason to evaluate the installer on a spare machine first.

## Build and test from source

From the repository root, on a suitable development machine:

```bash
python3 desktop/test_server.py
python3 packaging/test_installer.py
python3 packaging/test_compatibility.py
bash packaging/build-deb.sh
```

CI checks the Python syntax, application logic, mock compatibility scenarios and DEB contents. It **cannot establish that the screen overlay, screenshot capture or installer will behave correctly on every real laptop**.

The project is in a public **testing stage**. Please report results without including child-identifying information. The [project homepage and overview](../README.md) describe the current features and release status.
