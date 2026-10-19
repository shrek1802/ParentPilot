# ParentPilot — native Android parental controls

ParentPilot Android is a **native Kotlin app** for controlling a ParentPilot Linux laptop. It uses Android screens and HTTPS requests directly; **it does not launch Chrome or embed a WebView**.

## In-app features

- Discover a laptop over the same Wi-Fi, connect by private IPv4 address, or use a trusted private Tailscale `.ts.net` address.
- Sign in using the existing **six-digit parent PIN** (not saved on the phone).
- View remaining/used screen time and child activity status.
- Set or add minutes; pause, resume, end time, set unlimited time or return to managed time.
- Request an individual screenshot (child-visible notification), view a picture in the app with pinch-to-zoom, and explicitly save the image to the laptop gallery.
- View, download to the phone and delete up to 20 saved screenshots using the system Save picker.

Screenshot viewing must already be enabled on the child laptop. Native mode uses the existing authenticated ParentPilot actions; **an existing working laptop does not need to be reinstalled**. Newer laptop services also provide a typed JSON status endpoint; the app automatically falls back to the existing browser-dashboard-compatible service for older installations.

## Automatic update notices

On login, ParentPilot checks published GitHub Releases and shows a notice on Home if a newer Android version is available. Open **More → Software updates** to read the release notes, manually check, review a published stable update, and install with Android's own approval dialog. Debug and preview releases are not automatically offered.

Downloads are checked against the published SHA-256 digest and verified for the exact Android app ID, newer version code and **matching installed signing certificate**. Releases from temporary GitHub Actions artifacts do not qualify. The app never installs without Android and parent approval. See [the update guide](../docs/UPDATES.md).

## One-time security check for local HTTPS

ParentPilot's local HTTPS certificate is self-signed. Before sending the PIN, the app shows its **SHA-256 certificate fingerprint**. On the Linux laptop, open an adult administrator terminal and compare it with:

```bash
sudo openssl x509 -in /etc/max-family-control/server.crt -noout -fingerprint -sha256
```

Only choose **I verified it matches** when the fingerprint is identical. The app then pins that specific certificate for that laptop address; an unexpected certificate change blocks future connections. Unlike a browser that allows a click-through warning, the native app does **not** silently disable HTTPS verification. Tailscale `.ts.net` addresses use Android's normal trusted HTTPS certificate verification.

## Current verified installation

**[Download ParentPilot-Android-v7.apk (permanently signed)](https://github.com/shrek1802/ParentPilot/releases/download/v0.5.0-preview8/ParentPilot-Android-v7.apk)** from the [Preview 8 release](https://github.com/shrek1802/ParentPilot/releases/tag/v0.5.0-preview8). This is the first APK for friends and family to install, *not* the superseded temporary debug build.

The official release includes the verified Linux Preview 8 DEB as well, with a joint `SHA256SUMS.txt`. GitHub Actions verified the Android package ID, version code 7 and permanent signing certificate. Stable in-app upgrades will become available when a newer **stable** signed Android release is published; the existing Preview 8 release is deliberately marked as a prerelease.

## Same application ID and permanent release signing

**Android package ID:** `uk.familycontrol.remote` (unchanged). **Current version:** code 7, `0.4.2-updates-preview`.

Android permits in-place updates only if the new APK has the **same package ID, the same release signing certificate, and a higher version code**. The older GitHub Actions debug APKs use temporary signing certificates and cannot reliably update each other.

### One-time permanent signing setup — repository administrator

On **your own trusted adult Linux computer**, install the GitHub CLI, Java keytool and OpenSSL:

```bash
sudo apt update && sudo apt install gh openjdk-17-jdk-headless openssl
```

Download [the one-time signing script](../scripts/setup-android-signing.sh), inspect it, then run it as your normal adult user (not root):

```bash
bash setup-android-signing.sh
```

The script asks you to sign in to GitHub using your browser if needed, creates or reuses a private RSA signing key in `~/.local/share/parentpilot/signing/`, and uploads **five encrypted Actions secrets** directly to GitHub. It checks for an existing secret before generating a new key so you don't accidentally replace the release signing identity.

**Back up both the private JKS and its password file to encrypted offline storage.** Never share them in a chat, upload them to the public repo or put them in a release.

### Build an APK your friend's phone can keep updating

After setting the secrets, open the [ParentPilot Android build workflow](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml), select **Run workflow** and choose the development branch. This manual workflow now:

1. Requires the permanent signing secrets.
2. Builds the Android release APK (not the temporary debug package).
3. Verifies the app ID and version.
4. Confirms the APK's signing certificate SHA-256 exactly matches the original permanent fingerprint.
5. Uploads `ParentPilot-Android-v7-PERMANENTLY-SIGNED` with an APK and checksum.

**Do not install an old `ParentPilot-Android-v7-DEBUG.apk` on a new phone.** Install the permanently signed build once; subsequent versions signed by that same keystore, with higher version codes, can update without uninstalling. A public release can be published later using the gated [release workflow](../.github/workflows/publish-parentpilot-release.yml). Manual test artifacts are not automatically shown by the in-app updater; that updater looks at official stable GitHub Releases.

If an old debug build is already installed, Android may require uninstalling **only the phone app once** before the first permanent-signed installation. The child's Linux laptop is unaffected.

## Build and limitations

Use [Android GitHub Actions](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml) to build the app. It uses Gradle 8.9, Android SDK 35, Kotlin 2.0.21 and Java 17.

This is a developer test build. Native functionality has compiled in CI, but **physical phone testing, security review, error handling across networks, and signing migration remain necessary**. It is not Play Store-ready.