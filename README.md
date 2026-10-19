# ParentPilot

![ParentPilot logo](assets/parentpilot-logo.png)

**Open-source family screen-time controls for Linux XFCE, with an optional Android companion.**

ParentPilot helps parents manage time on a child's Linux laptop. It creates a separate standard (non-administrator) child account, provides a child-friendly desktop and gives parents a PIN-protected dashboard for controlling screen time from a phone or browser.

> **Development preview — not a hardened parental-control or child-safety product.** Screen locking uses a graphical XFCE/X11 overlay, which a technically experienced user may bypass. Installation and platform compatibility need more testing before a general release.

## Features

| Feature | What it does |
| --- | --- |
| Daily screen time | Set or add time, pause or resume access, end the day or allow unlimited time for a day |
| Parent PIN | Six-digit parent PIN, separate from the child's Linux login password |
| Child-friendly desktop | Simplified XFCE shortcuts for Chromium, YouTube and Files; optional Netflix shortcut |
| Media-aware lock | Covers the desktop when time expires or access is paused; attempts to pause media playback and mute audio |
| Web dashboard | Parent controls from a browser on the same trusted network |
| Native Android app (preview) | Wi-Fi/Tailscale connection, parent PIN sign-in, time controls, screenshot viewer and gallery without opening a browser |
| Optional screen pictures | Parent-requested, child-notified snapshots in the current experimental build; no continuous live stream |
| Saved picture gallery | Explicitly save selected screen pictures, view or download them, or delete them; up to 20 saved pictures |
| Reliable lock interface | A single-instance child supervisor avoids competing lock windows; transient service polling errors no longer dismiss an established lock |

Screen-picture monitoring is **off by default** and requires an administrator to enable it during initial setup. When enabled, a parent must sign in before requesting or saving a picture. The child sees an on-screen notice before each capture. Unsaved pictures expire after two minutes; nothing is automatically recorded.

## Requirements and compatibility

- **Primary target:** Linux Mint XFCE using an X11 desktop session and systemd.
- **Additional test candidates:** Debian-family systems running XFCE/X11, including Xubuntu and Debian XFCE. Passing the compatibility checker is **not proof of full compatibility**.
- **Not currently supported:** Wayland sessions and other desktop environments such as GNOME, Cinnamon, KDE, MATE or LXQt.
- A separate adult administrator account is needed for initial setup. The child account must not have administrator privileges.
- **Optional:** Android phone and local Wi-Fi for discovery; a private VPN such as Tailscale for access across different networks.

For tested-versus-candidate environments and dependencies, see the [Linux installer guide](packaging/README.md).

## Getting started — new installation

ParentPilot is still a test release. **Use a spare machine or disposable virtual machine while evaluating the installer.** Current Debian packages are intended for **fresh setups only**, not upgrades of an existing configured parental-control installation. The installer is designed to refuse an existing setup rather than overwrite accounts, PINs or saved time.

1. Open [Linux DEB builds on GitHub Actions](https://github.com/shrek1802/ParentPilot/actions/workflows/build-linux-deb.yml) and select an appropriate successful build. Preview 6 is available in the [draft development pull request](https://github.com/shrek1802/ParentPilot/pull/7); it is **not a stable release**.
2. Under **Artifacts**, download the Linux DEB artifact (a ZIP containing a `.deb` file). GitHub may require sign-in to download CI artifacts.
3. On an XFCE/X11 laptop, sign into the **adult administrator** account. Open the extracted `.deb` with the system package installer.
4. From the applications menu, open **ParentPilot Family Setup**.
5. Follow the compatibility check and setup wizard: choose a child name and login, child password, **separate parent PIN**, and optional content shortcuts, filtering, auto-login and screen pictures.
6. Confirm the review screen and approve the system administrator prompt. Set up supervised YouTube and Netflix Kids profiles **inside those services** separately.
7. Sign into the child's account and test a short time allowance, expiry, pause, parental PIN and recovery on the test device.

The application will not automatically configure streaming-service maturity restrictions or make menu hiding into operating-system-level security. Chromium filtering policies, if selected, may affect **all users of Chromium on the laptop**, including adults.

## Android companion

The Android app has a **native parent dashboard** with set/add time, pause/resume, unlimited/managed mode, individual screenshots and the saved gallery. It runs these controls directly inside the app instead of opening a browser. It retains the original Android application ID (uk.familycontrol.remote) and has a higher version number. The parent PIN is not stored. Local HTTPS certificate fingerprints must be checked once, and a new APK cannot replace an older APK signed with a different certificate.

- [Android installation and connection guide](ANDROID_INSTALL.md)
- [Android debug APK builds](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml)
- [Android source and build notes](android-app/README.md)

Local discovery depends on the router allowing devices to communicate via mDNS; guest networks and some hotspots block it. For remote use, connect both devices through a **private VPN** and use a private HTTPS endpoint. Do not expose the control service directly to the public internet.

## Security and privacy

- Parent PIN verification uses a salted password hash; browser actions require an authenticated session and anti-CSRF protection.
- Screen previews are requested individually, not captured in the background. Saving a picture is an **explicit parent action**. Saved pictures remain on the laptop until deleted.
- The child is visibly notified when a screen picture is requested. There is no webcam, microphone or continuous screen-video recording.
- The native Android app verifies ordinary HTTPS certificates and requires **explicit SHA-256 certificate fingerprint verification** for self-signed local laptop connections; the parent PIN is not retained on the phone.
- Local account permissions and the graphical lock are **best-effort**, not tamper-resistant protections. Child-device and authentication security need independent review before public production use.
- Do not upload real parent PINs, configuration files, private keys, device tokens or saved screenshots to issues or pull requests.

## Development and testing

This repository includes the Linux desktop service, the graphical setup wizard, Debian package build scripts and the Android companion:

| Path | Contents |
| --- | --- |
| `desktop/` | Screen-time service, child desktop, lock/media helpers and service tests |
| `packaging/` | Linux first-run wizard, compatibility checks and DEB packaging |
| `android-app/` | Native Android parent dashboard and pinned HTTPS client |
| `.github/workflows/` | Automated Linux DEB and Android debug-APK builds |

From the repository root, run:

```bash
python3 desktop/test_server.py
python3 desktop/test_lock_stability.py
python3 desktop/test_supervisor_singleton.py
python3 packaging/test_installer.py
python3 packaging/test_compatibility.py
bash packaging/build-deb.sh
```

The automated tests exercise logic and package contents, but **do not replace testing on real XFCE/X11 desktops**. In particular, the first-run experience, screenshot capture, window stacking, audio behaviour and application restrictions need cross-distribution testing.

## Project status and contributions

ParentPilot is **under active development**. Priorities before a public stable release include broader physical-device testing, clearer installation recovery and upgrade paths, accessibility checks, security review, and a properly signed Android release.

Issues and contributions are welcome through [GitHub](https://github.com/shrek1802/ParentPilot). Please describe the Linux distribution, XFCE version, session type (X11), and relevant app version when reporting a problem, without including family or child identifiers.

Source licensing is described in [LICENSE.txt](LICENSE.txt).
