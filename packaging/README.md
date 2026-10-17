# ParentPilot 0.5 Preview 3 — family setup installer

**This is a fresh-install testing preview for Debian-family Linux with XFCE on X11**, not a universal Debian package or an upgrade for a configured Max Family Control installation.

## What happens for parents

1. Download the `.deb` and double-click it to install its required packages.
2. Open **ParentPilot Family Setup** from the applications menu. On a fresh administrator XFCE login, the setup wizard can also offer to start.
3. The first screen checks the operating system, desktop, Chromium, account tools and installed services. Unsupported environments stop **before** creating an account.
4. Enter a child's name, review the suggested login name, choose a child account password and a separate six-digit **parent PIN**.
5. Choose **YouTube Kids** or a supervised YouTube shortcut, optional **Netflix** (Kids profile required), the Chromium family-filter policy, optional **LightDM** auto-login and an **optional one-time screen preview** (OFF by default).
6. Review and confirm; approve the administrator authentication request. Only then will the wizard create the non-admin child account, child's XFCE shortcuts/panel, the timer service, and Avahi discovery for the Android companion.

The timer is paused at first. The parent grants time from the phone or PIN. The child gets a simplified bottom bar with Chromium, YouTube, Files, Netflix if selected, and the clock/status area.

## Compatibility

| Environment | Status |
|---|---|
| Linux Mint XFCE on X11 | Intended primary target; full v0.5 installer not yet tested on a physical laptop |
| Debian 11–13 XFCE on X11 | Candidate; offline checks pass; real installation not yet tested |
| Linux Mint Debian Edition (LMDE) with XFCE/X11 added | Candidate; offline checks pass; real installation not yet tested |
| Raspberry Pi OS with XFCE/X11 and systemd | Candidate architecture/desktop combination; requires physical testing |
| Ubuntu 22.04/24.04/26.04 including Xubuntu with XFCE on X11 | Candidate; offline checks pass; real installation not yet tested |
| MX Linux on XFCE/X11 with systemd | Candidate; distro detected; real installation not yet tested |
| Cinnamon, GNOME, KDE, LXQt, MATE, Wayland | **Not supported by this lock-window implementation** |
| Old distributions with Python below 3.9 | Not supported |

Being Debian-based **does not mean** the screen-time lock works with every desktop. This edition checks XFCE/X11 and refuses an existing `/etc/max-family-control` or `/opt/max-family-control` installation instead of overwriting it.

## Safety and child filtering

- The package's post-installation script creates **no Linux accounts or service settings**. Only the wizard, after explicit confirmation and parent administrator authentication, provisions the child.
- Child launcher hiding is cosmetic, **not application security**. A capable local user can bypass a best-effort X11 overlay. This is not a hardened kiosk.
- The optional Chromium policy affects **every Chromium user on the computer**, including the parent. Verify it in `chrome://policy`. Snap Chromium on Ubuntu may behave differently.
- YouTube maturity settings must be set on the **YouTube Kids/Google account**. Netflix Kids/adult PIN setup must be performed within Netflix. Widevine DRM is not installed or circumvented.
- Avahi `_maxfamily._tcp` announces the laptop locally; the Android app finds it on the same Wi-Fi when the router allows mDNS. Do not expose parental port 8743 directly to the internet.
- **LightDM is optional**; without it, do not select automatic child login. Other display managers are not automatically reconfigured.
- Removing the `.deb` preserves existing child data; a fully guided repair/uninstall wizard is still planned. Failure part-way through provisioning can leave a partially created child account.
- The optional **View Child's Screen** in Preview 3 is a **single parent-authorised picture**, not live video. It is OFF unless an administrator enables the feature during fresh setup. A parent signs in with their PIN and requests a picture. The child sees a **clear on-screen viewing notice before the picture is taken and for 30 seconds afterwards**, but does not need to approve each request. Pictures stay in service memory for at most 30 seconds, are not saved to disk, and are accessible only to a signed-in parent. Requests are limited to one every 45 seconds. No microphone/camera access or background recording is used.
- This feature requires GTK/Gdk on an X11 child session, and must be tested on a disposable XFCE laptop/VM before relying on it. If the child desktop is not running, the request expires without an image. A failure to capture is reported without silently retrying. Each new picture requires a fresh parent request (not a new child approval).

## Build and test

Run from the source repository root:

```bash
python3 desktop/test_server.py
python3 packaging/test_installer.py
python3 packaging/test_compatibility.py
bash packaging/build-deb.sh
```

The preflight tests simulate distro identities and verify that unsupported systems are refused. **No automated test replaces a real disposable XFCE/X11 VM installation. Do not test this on Max's working Dell.**

## Quick start: no Linux knowledge needed

**This is for a spare/new XFCE/X11 installation only. Do not install it over an existing working child's ParentPilot setup.**

1. On the new laptop, sign into an **adult administrator** account.
2. Double-click the ParentPilot `.deb`, choose **Install Package** and approve the usual administrator password. (If the distro cannot install packages on double-click, open it using its graphical software installer.)
3. From the app menu, open **ParentPilot Family Setup**. Read the **Compatibility Check** on the first page. A green pass means the detected setup meets the software requirements, *not* that this exact laptop has been tested.
4. Enter the child's display name and choose a different Linux username and password. The wizard keeps the child a standard, non-admin user.
5. Make a separate six-digit parent PIN; pick **YouTube Kids** or supervised YouTube, optional Netflix, Chromium filtering, optional automatic login, and whether to allow parent-requested single pictures of the screen (OFF by default). Leave automatic login off if the wizard says LightDM is missing.
6. Check the **review page**, then click **Install** and approve the administrator prompt. No child account is created until this step.
7. When setup reports success, sign into the child's account once. Complete YouTube Kids' age selection or supervised account setup and select Netflix Kids / lock adult Netflix profiles separately.
8. Open ParentPilot Android on your phone, while connected to the **same Wi-Fi**, and press **Find nearby laptop**. ParentPilot uses Avahi for discovery; client-isolated guest networks may prevent it.

If the compatibility screen refuses setup, **do not force it using Terminal commands**. The current fullscreen/PIN overlay needs XFCE on X11, and a different desktop requires dedicated support.

**New in Preview 3:** parent-requested one-time screen pictures after an administrator opts in during installation, with a **visible child notification** before each capture. This is an experimental feature, **not continuous remote screen viewing**. Test it on a spare device first, and do not deploy Preview 3 on Max's working laptop.
