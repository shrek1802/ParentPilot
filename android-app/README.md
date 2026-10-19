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

On login, ParentPilot checks published GitHub Releases and shows a notice on Home if a newer Android version is available. Open **More → Software updates** to read the release notes, manually check, choose Stable (default) or Preview, and install with Android's own approval dialog.

Downloads are checked against the published SHA-256 digest and verified for the exact Android app ID, newer version code and **matching installed signing certificate**. Releases from temporary GitHub Actions artifacts do not qualify. The app never installs without Android and parent approval. See [the update guide](../docs/UPDATES.md).

## One-time security check for local HTTPS

ParentPilot's local HTTPS certificate is self-signed. Before sending the PIN, the app shows its **SHA-256 certificate fingerprint**. On the Linux laptop, open an adult administrator terminal and compare it with:

```bash
sudo openssl x509 -in /etc/max-family-control/server.crt -noout -fingerprint -sha256
```

Only choose **I verified it matches** when the fingerprint is identical. The app then pins that specific certificate for that laptop address; an unexpected certificate change blocks future connections. Unlike a browser that allows a click-through warning, the native app does **not** silently disable HTTPS verification. Tailscale `.ts.net` addresses use Android's normal trusted HTTPS certificate verification.

## Same application ID and installation updates

**Package name stays `uk.familycontrol.remote`.** Version code is increased to 5 (`0.4.0-native-preview`).

An Android APK can update an installed APK **only when both the application ID and signing certificate match**. Older GitHub Actions debug builds used ephemeral signing keys, so an APK from a different run may fail to install over them despite having the same ID. The original signing private key cannot be recovered from an installed APK.

For **future consistent signed releases**, configure the following as private GitHub Actions repository secrets:

- `PARENTPILOT_SIGNING_KEYSTORE_B64`: base64 of the **private** JKS keystore
- `PARENTPILOT_SIGNING_STORE_PASSWORD`
- `PARENTPILOT_SIGNING_KEY_ALIAS`
- `PARENTPILOT_SIGNING_KEY_PASSWORD`

The Android build workflow then generates a separately labelled **ParentPilot-Android-Native-Signed-APK** using that same persistent key across versions. Keep the keystore and its passwords backed up securely outside GitHub. **Never commit, publish or send a private keystore in issues or chat.** If a pre-existing APK was signed with an unknown debug key, one uninstall/reinstall on the *Android phone* may be unavoidable before moving to a stable signing identity. This does **not** affect the child laptop or its timer/PIN/gallery. The phone's saved connection address may need re-entering.

Without the signing secrets, GitHub uploads **ParentPilot-Android-Native-Debug-APK** for testing. Its signer is **not** guaranteed to match previous runs.

## Build and limitations

Use [Android GitHub Actions](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml) to build the app. It uses Gradle 8.9, Android SDK 35, Kotlin 2.0.21 and Java 17.

This is a developer test build. Native functionality has compiled in CI, but **physical phone testing, security review, error handling across networks, and signing migration remain necessary**. It is not Play Store-ready.