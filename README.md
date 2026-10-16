# ParentPilot — Family Screen Time Control

![ParentPilot logo](assets/parentpilot-logo.png)

**Linux Mint XFCE + Android** · Branded developer preview

ParentPilot is a parental screen-time timer for a **Linux Mint XFCE** laptop, with a mobile-friendly parent dashboard and an Android companion that can **find laptops on the same Wi-Fi** automatically. The project started as a personalised setup for Max but this repository's fresh-install branch allows a parent to choose **any child display name and Linux username**.

> **Important:** This is a developer preview, not a certified or tamper-resistant parental-control product. A technically knowledgeable user can bypass the XFCE popup. Use supervision and appropriate Linux permissions. No remote public port forwarding is necessary or recommended.

## Branding

The app uses the generated **ParentPilot family-and-clock emblem** in its Linux fullscreen parental approval page, parent web login/dashboard, Android launcher icon and Android discovery screen. `assets/` contains the original transparent wordmark and icon; `desktop/assets/` contains the runtime copies. Internal legacy file/service names are intentionally kept for upgrades.

## Who installs what?

| Component | Location | What it does |
| --- | --- | --- |
| `desktop/install.sh` | Linux Mint XFCE computer | Sets up account, background timer, local PIN and web dashboard |
| `desktop/enable-discovery-existing.sh` | Existing *working* ParentPilot computer | Adds Avahi/mDNS Wi-Fi discovery only; does not touch timer or PIN |
| `android-app/` | Android Studio project | Discovers nearby laptop via mDNS, then opens its HTTPS control panel in the **phone's browser** |
| `desktop/remote-setup.sh` | Laptop (optional) | Tailscale Serve: private HTTPS address for use outside the local Wi-Fi |

**What the Android app does today:** finds and remembers the laptop address, opens the existing PIN-protected web dashboard. It is a native *companion/launcher*, not a fully native dashboard. It doesn't save the PIN. Native Pause/Resume buttons can be added after safe pairing and device-authentication design.

### Using it at the caravan

- If **Mum, the laptop and phone are on the same caravan Wi-Fi or hotspot**, press **Find nearby laptop**. Discovery requires the network to permit multicast/mDNS between devices. Some guest networks and hotspots isolate clients.
- If **Mum is somewhere else and the laptop is on another network**, local auto-scanning cannot find it. Install Tailscale on both devices, sign into the same private tailnet and set up Tailscale Serve on the laptop. Save the private `https://...ts.net` address in the Android app. Mum can then open it anywhere the laptop is online.
- Never forward TCP 8743 publicly, enable Tailscale Funnel, or disable the firewall to force connectivity.

## New: branded Linux Mint .deb installer

A fresh-install **ParentPilot v0.4.0 Preview 1** Debian package now builds from source using [GitHub Actions](https://github.com/shrek1802/ParentPilot/actions/workflows/build-linux-deb.yml). Open the most recent successful run and download the **ParentPilot-Linux-Mint-DEB** artifact, then extract the `.deb` file.

Install with Linux Mint's package installer (or `sudo apt install ./parentpilot_0.4.0~preview1_all.deb`), then open **ParentPilot Family Setup** from the Mint application menu. The branded four-step wizard guides the parent through the child's display name, new Linux user/password, separate six-digit parent PIN, YouTube Kids or supervised mode, optional Netflix, Chromium family filtering and automatic login. The child gets a curated XFCE bottom panel and ParentPilot's tested single-window X11 lock, video-window covering and audio mute. The laptop advertises itself over Avahi for Android phone discovery.

**This package is for a NEW child account on a fresh Mint XFCE installation, not an in-place update. Do not try it on Max's existing working laptop.** It refuses to overwrite an existing ParentPilot/Max Family Control installation. Installation and offline tests pass, but complete provisioning and DRM playback have not yet been tested on a separate real Mint machine. ParentPilot does not select YouTube Kids maturity bands or Netflix Kids profiles for you; a parent must configure those inside the services. Menu hiding is cosmetic and the X11 overlay is not tamper-proof. Details and source: [packaging/README.md](packaging/README.md).

## Fresh laptop setup

**DO NOT RUN `--install` on Max's working laptop.** It is designed for first installs and deliberately refuses to overwrite an existing `/etc/max-family-control/config.json` or `/opt/max-family-control/control_server.py`.

On Linux Mint XFCE, install prerequisites via Mint's Software Manager or:

```bash
sudo apt update
sudo apt install python3 python3-tk openssl acl avahi-daemon
```

Then from the extracted `desktop` directory:

```bash
bash install.sh --check
sudo bash install.sh --install
```

The installer asks for:

1. Child's display name (for example, `Ellie`).
2. Standard Linux username (for example, `ellie`) — reuse an existing non-admin user or create one.
3. A **six-digit parent PIN**, separate from the child Linux password.
4. Optional LightDM autologin for that child.

The services and files use their legacy internal `max-family-control` names to retain compatibility; the user-facing project is **ParentPilot**. A new child account has its own Linux password and is **not** made an administrator. An installer is a privileged script: review it and use it only on systems you control.

### Existing working laptop: add Wi-Fi discovery only

```bash
sudo bash desktop/enable-discovery-existing.sh
```

This creates an Avahi `_maxfamily._tcp` record for port 8743. It does **not** reinstall the timer, change the PIN, reset allowances or alter logins. It is the only included script intended for the current working Max laptop.

## Android app (debug APK available)

The Android companion now **compiles successfully** in GitHub Actions. Download the installable test APK from the latest successful [Android build](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml) under **Artifacts → ParentPilot-Android-debug-APK**. Extract the artifact ZIP to get `app-debug.apk`. See [ANDROID_INSTALL.md](ANDROID_INSTALL.md) for installation and device setup. This is a debug build, not a Play Store/release-signed version; real-device testing on Android 14–16 and varied Wi-Fi routers is still required.

The app uses `NsdManager` service discovery for `_maxfamily._tcp.` on local networks. Tapping a result opens the default browser at the discovered laptop's `https://<IP>:8743/`. The current local server uses a self-signed TLS certificate, so the browser may display a warning. Check that you have selected **your own laptop** before trusting a local certificate. The app does not disable HTTPS certificate verification. For Tailscale, use the private `.ts.net` HTTPS hostname with a publicly trusted Tailscale Serve certificate.

## Safety, security and privacy

- Six-digit PIN is salted and hashed in a root/service-owned config file; do not upload any real config, private keys, tokens or timer state to GitHub.
- Desktop API requires a separate local desktop token, but that token is readable by the child's own Linux account, so a capable local user could bypass the graphical restrictions.
- Parent web operations require a PIN-authenticated session and CSRF token; five failed attempts temporarily block new attempts.
- Device discovery is unauthenticated mDNS. It locates an **advertised** laptop; it does not prove the broadcaster is trustworthy. HTTPS and parent PIN still matter.
- The app works over home Wi-Fi; across networks it requires a VPN such as Tailscale. **There is no public internet server in this project.**
- A parent device joining the same Tailscale account can reach other allowed tailnet devices; review Tailscale device approvals and permissions.
- The app should be audited before any public or Play Store release; do not treat this prototype as a commercial child-safety product.

## What isn't done yet?

- Android device verification (debug APK compilation succeeded; production signing and real-device tests pending)
- A proper signed device pairing flow and native dashboard controls
- Production-grade OS-enforced lockout
- Installer testing on clean Mint laptops, and automatic upgrade support for the currently customised Max installation

## Publishing

This source can be placed in **one GitHub repository** containing `desktop/` and `android-app/`. The `LICENSE.txt` currently uses MIT. Before releasing publicly, review licensing/attribution, perform security testing and consider publishing prebuilt signed APKs via GitHub Releases (not by committing a signing key).
