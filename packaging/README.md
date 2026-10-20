# ParentPilot Linux installer — Preview 15

ParentPilot provides a guided setup for family screen-time controls on Debian-based Linux desktops using **XFCE on X11**.

> **Developer preview — new installations only.** The Debian package is **not itself a direct replacement installer** for an already configured ParentPilot laptop. Do not install over an existing child's setup. Use a spare laptop or disposable VM for evaluation.

## Install with the graphical wizard

1. Download a successful Linux build from [GitHub Actions](https://github.com/shrek1802/ParentPilot/actions/workflows/build-linux-deb.yml). Preview 7 uses the versioned `parentpilot_0.5.0~preview7_all.deb` file inside an artifact ZIP. Builds on different branches may contain different versions.
2. Sign into a new XFCE/X11 laptop with an **adult administrator** account.
3. Open the DEB in your distro's package manager and approve installation.
4. Open **ParentPilot Family Setup** from the applications menu. The compatibility check runs before child account changes.
5. Choose the child's display name, standard Linux username, child login password and **separate six-digit parent PIN**.
6. Choose supervised YouTube/YouTube Kids shortcuts, optional Netflix, Chromium filtering and optional LightDM auto-login. Screen-picture requests are included with a child-visible notification.
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


## On-demand screen pictures (Preview 23)

Screen pictures are **available by default** to an **authenticated parent**, including on existing DEB-managed installations upgraded through the administrator-approved ParentPilot updater. No additional laptop-wide on/off setting is needed. The upgrade changes only the existing screen-picture permission flag and keeps the account, parent PIN, timer, token, and saved pictures unchanged.

This does **not** mean continuous surveillance: a parent must request each picture from the signed-in ParentPilot phone app or web panel, and the child's desktop shows a clear notification before each picture. There is no background stream or automatic recording. A preview expires unless the parent explicitly chooses to save it. The private gallery has a fixed retention count, and the parent can delete saved pictures.

If a managed upgrade cannot safely update the configuration or the service fails to restart, the permission migration is rolled back and the updater reports the error. Do **not** rerun Family Setup on an existing laptop. This release deliberately changes the default permission; review this behaviour before approving the update.

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

## Updates for the adult account

**ParentPilot Updates** is available in the adult administrator's applications menu after installing the Preview 8 DEB. It also checks once at adult desktop login and displays a notification when a published release is available.

1. Open **ParentPilot Updates** while signed in as an adult Linux administrator.
2. Select **Stable** (recommended for later public releases) or **Preview** (test releases), then click **Check for updates**.
3. Read the release notes and **sign the child out completely** before proceeding.
4. Click **Install update**, approve the administrator password prompt, and wait for the installation and service check.
5. The updater downloads only published GitHub Releases, checks the SHA-256 digest and package metadata, and saves a protected local backup of the existing program, PIN/configuration, timer data, saved screenshots, and service definition before upgrading.
6. If the service cannot restart correctly, the updater attempts to restore the previous deployed program and backed-up data. A failed APT package operation may still require manual package-version repair; the GUI reports this clearly.

**Do not use the first-run wizard as an update tool** or install arbitrary GitHub Actions artifacts over a working child machine. This upgrade system still requires physical-laptop testing. Upgrades are deliberately blocked when the child is signed in or the installation predates the managed-install marker.

## Build and test from source

From the repository root, on a suitable development machine:

```bash
python3 desktop/test_server.py
python3 desktop/test_lock_stability.py
python3 desktop/test_supervisor_singleton.py
python3 packaging/test_installer.py
python3 packaging/test_compatibility.py
python3 packaging/test_updates.py
bash packaging/build-deb.sh
```

CI checks the Python syntax, application logic, mock compatibility scenarios and DEB contents. It **cannot establish that the screen overlay, screenshot capture or installer will behave correctly on every real laptop**.

The project is in a public **testing stage**. Update mechanisms need on-device testing and independent signature verification before a stable public release. Please report results without including child-identifying information. The [project homepage and overview](../README.md) describe the current features and release status.

## Optional free Games & Learning (Preview 15)

ParentPilot includes a catalogue of **eight optional free games** available through Debian/Ubuntu/Mint APT repositories. It makes no Flatpak, AppImage or untrusted downloads. No games are selected by default.

| Game | APT package | Purpose |
| --- | --- | --- |
| GCompris | `gcompris-qt` | Reading, counting, memory and problem-solving activities. Larger package. |
| Tux Maths | `tuxmath` | Arcade arithmetic |
| Tux Typing | `tuxtype` | Keyboard skills |
| Tux Paint | `tuxpaint` | Drawing and creativity |
| Pingus | `pingus` | Lemmings-style reasoning puzzles |
| SuperTux | `supertux` | Lightweight 2D platforming |
| Frozen Bubble | `frozen-bubble` | Colour-matching puzzles |
| GNOME Sudoku | `gnome-sudoku` | Number logic |

The Dell Inspiron N5110 i3/6GB class of laptops should run most of these comfortably, although driver age and 2D/Qt rendering matter. Game selection does not remove Office, VLC, XFCE utilities, or other normal learning software.

**New installations:** Choose individual games on the wizard's **Parental controls & apps** step. On confirmation, ParentPilot provisions the child account and timer first. It then asks APT to install only the selected games, each from the OS's configured repositories. An offline repository error does not prevent the child account/timer setup from completing; the installer reports the failed games.

**Already configured laptop:** From the **adult administrator** account, open **ParentPilot Games & Learning** in Applications → Settings or run `parentpilot-games`. Select games and approve the administrator password prompt. This does **not** rerun Family Setup or change passwords, accounts, PIN, allowance, or screenshots. Already-installed games are shown as such and are never reinstalled or removed by this utility.

APT installs the selected packages **system-wide**, as normal desktop programs. They appear in the child's standard XFCE Applications menu (usually Games or Education), and the parent can run them too. Game play counts towards the normal ParentPilot screen-time allowance. Updates to these games are managed through Mint's normal package manager.

**Important:** APT requires an internet connection and enabled distro repositories. Some optional titles may be unavailable on unusual Debian-based distributions; failed games are reported individually. Menu hiding of alternative web browsers is a cosmetic convenience, not a kernel-level restriction.


## ParentPilot Control Centre (Preview 24)

On an already configured laptop, **Applications → Settings → ParentPilot Control Centre** is the single adult management interface. Tabs provide **Home** (installed version and service state), **Updates** (the existing verified/backup installer), **Games & Media** (existing APT install with live per-app progress), **Security** (change the parent PIN or the configured child's Linux password), and **Help**. The original update and games commands remain available for compatibility and update notification autostart; their separate Applications-menu launchers are replaced by the unified Control Centre.

Security updates need Linux administrator approval. Changing the parent PIN requires the **current six-digit PIN** plus the Linux administrator password, stores a fresh salted PBKDF2 hash, and restarts the parent service to revoke old sessions. To change the child login password, enter and confirm a new password of at least eight characters; the privileged helper updates only the child account already in ParentPilot's private configuration. Passwords are passed on a one-use stdin pipe, not as command arguments or in activity logs. No new users are created, and the parent PIN, timer allowance and saved pictures remain unchanged when changing the child login password.

**Pinned Kodi/taskbar icons:** Preview 24 fixes the previous panel repair procedure that regenerated the full child XFCE panel on upgrades. The update now preserves the family's current panel XML, plugin IDs, launcher order and pinned apps instead of recreating the dock or forcing a panel restart. If a launcher was already removed by an earlier update, the family needs to pin it again once; future managed upgrades will not remove it. The one-time Family Setup wizard remains available separately on a fresh installation, and must never be rerun on an existing account.


## Extra optional games (Preview 25)

The adult **ParentPilot Control Centre → Games & Media** now offers **15** official-distribution APT game choices (the original eight plus seven new choices). New additions: KGeography (geography/countries), Blinken (memory), KTuberling (creative stamp game), SuperTuxKart (3D racer), Extreme Tux Racer (3D sliding game), Minetest (older official Ubuntu package of the voxel sandbox now branded Luanti), and Hedgewars (turn-based strategy).

These are **opt-in only**. Neither a software upgrade nor Family Setup installs the seven extras without an adult ticking them. APT fetches only the chosen allowlisted packages, with no third-party repositories, scripts, addons or automatic uninstall. Some educational KDE games may pull in additional KDE libraries; SuperTuxKart, Minetest and the other 3D games may perform poorly on old Dell/Intel integrated graphics, so start with low graphics options. Minetest can be used in offline/local worlds rather than joining public servers. Existing Kodi and VLC options, game detection, live install-progress bars, and screen-time restrictions are unchanged. No blanket Edubuntu metapackage, old Scratch 1.4 or games requiring unofficial sources are included.

### Chromium keyring prompts

On XFCE with automatic login, Chromium may ask to **Unlock Login Keyring** because automatic login does not unlock the encrypted password store. That prompt is not the parent PIN. ParentPilot does **not** erase the keyring, disable the child's Linux login password, force unsafe plain-text Chromium password storage, or turn off parent authentication during upgrades. Ask the adult to identify the exact dialog before choosing a keyring solution; no automatic security downgrade is made.


## Trial: newer Kodi alongside the existing APT Kodi (Preview 26)

To test on an older laptop, an adult can open **ParentPilot Control Centre → Games & Media**, scroll to **New Kodi — Separate Test**, and explicitly select **Install newer Kodi for testing**. The Linux administrator-password prompt approves a system-wide Flatpak installation; the child account can then launch **Kodi (New Version Test)** from its normal Applications → Multimedia menu. The installer uses ONLY the signed official **Flathub** remote and the stable `tv.kodi.Kodi` package. If Flatpak itself is missing, the same approved operation installs the `flatpak` manager through the distro's ordinary APT. Both steps may download hundreds of megabytes, and the indeterminate progress indicator shows activity rather than an invented download percentage. The version installed is displayed from `flatpak info --system --show-version tv.kodi.Kodi`; it may differ from Kodi 21.3 as upstream releases change.

This optional trial does not uninstall, replace, update or pin the original `kodi` APT package. The user's old settings stay in `~/.kodi` and the Flatpak keeps its data under `~/.var/app/tv.kodi.Kodi`; data is not imported or copied automatically. The existing taskbar icon continues to launch classic Kodi. The new test launcher's explicit name is **Kodi (New Version Test)**. Testing **menus, 720p/1080p H.264 video and audio** must be done physically on the laptop; the CPU and old Intel graphics may limit performance, especially with HEVC/4K. No automatic change to the default Kodi, no Flatpak installation during ordinary ParentPilot updates, and no unapproved third-party Kodi PPA.


## Kodi trial version verification bug fixed (Preview 27)

Preview 26 incorrectly ran `flatpak info --system --show-version tv.kodi.Kodi`, but `--show-version` is **not** a valid Flatpak info option on Linux Mint. The installer consequently displayed **Kodi Flatpak test was not installed** even when the actual download and installation had completed. Preview 27 verifies the system-wide stable Kodi app by its installed reference (`flatpak info --system --show-ref tv.kodi.Kodi`) and source remote (`--show-origin`), then reads the optional human-readable Version field from `flatpak info --system tv.kodi.Kodi`. If no version text is available, the installation still counts as verified. An earlier completed Flathub Kodi is recognised immediately and the missing **Kodi (New Version Test)** launcher is restored, without a second Flatpak download. Classic Kodi APT, existing profiles, taskbar pins, family accounts, PINs, screen-time allowances and screenshots remain untouched.
