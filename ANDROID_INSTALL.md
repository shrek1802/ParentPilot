# Install ParentPilot's native Android app

ParentPilot `0.4.2-updates-preview` is a **native in-app parental dashboard**. It no longer launches a website for timer controls or viewing pictures. It remains a **developer preview** requiring real-phone testing.

## Download the permanently signed Android app

Download **[ParentPilot-Android-v7.apk](https://github.com/shrek1802/ParentPilot/releases/download/v0.5.0-preview8/ParentPilot-Android-v7.apk)** from the [verified Preview 8 GitHub Release](https://github.com/shrek1802/ParentPilot/releases/tag/v0.5.0-preview8) and install it on Android 8 or newer.

This build was checked in GitHub Actions: application ID `uk.familycontrol.remote`, version code **7**, and SHA-256 signing certificate matching the permanent encrypted repository fingerprint. **Do not install old DEBUG builds on a new family phone.**

If an earlier temporary DEBUG APK is installed, Android may require uninstalling **only the old phone app once** because its certificate differs. Installing this permanently signed APK establishes the signing identity for subsequent updates. Every later APK must retain this same signing certificate and have a higher version code. The Linux laptop, accounts, PIN and pictures are unaffected. See [Android developer notes](android-app/README.md).

This remains a development preview, not a Play Store release. Preview 8 itself does not trigger Android's automatic stable-update checker; future stable releases will, once they carry properly signed, higher-version APKs.

## Connect to the laptop

1. Connect phone and laptop to the **same trusted Wi-Fi**, or use their private Tailscale network.
2. Open ParentPilot and tap **Find nearby laptop**, or enter the laptop's private IPv4 address (for example `192.168.1.249`) in the app. Remote connections accept private HTTPS `.ts.net` names.
3. Enter the existing **six-digit parent PIN**.
4. The first time you use a local address, ParentPilot shows the laptop certificate's **SHA-256 fingerprint**. On the adult Linux administrator account run:

   ```bash
   sudo openssl x509 -in /etc/max-family-control/server.crt -noout -fingerprint -sha256
   ```

   **Compare the complete fingerprint.** Tap **I verified it matches** only if it is identical.
5. Connect. The screen-time dashboard, pause/resume, screenshot viewer, saved-image gallery and phone downloads are now inside the app.

For later connections, the app remembers the laptop address and verified certificate, but **not the parent PIN**. An unexpected certificate change must be checked again rather than automatically trusted.

## What works inside the app

- Check remaining time and child activity
- Set/add minutes, pause, resume, end, unlimited or managed time
- Request screen pictures and enlarge with pinch/zoom
- Save chosen screenshots to the laptop; view or delete old ones
- Download an image to the phone through Android's document picker

The laptop's optional screen-viewing feature must be enabled by an administrator. It uses individual parent-requested screenshots, **not a continuous screen recording**; the child receives a visible notification.

## New software updates

The native app now has **More → Software updates**. It automatically checks official GitHub Releases after sign-in, shows a notice when a new version qualifies, and offers a reviewed in-app download followed by Android's normal installation approval. Stable is selected by default; preview releases require opting in. An APK will only update an existing phone app if its **signing key matches**.

The updater requires a correctly published GitHub Release; a successful Actions debug build is not an auto-update release. Permanent signing secrets have to be configured first. See [ParentPilot update guide](docs/UPDATES.md).

## Troubleshooting

- **Cannot find laptop:** confirm same Wi-Fi, Avahi/mDNS enabled on the laptop, no guest network or client isolation. Enter its private IP manually if discovery fails.
- **Certificate mismatch:** do **not** proceed until the laptop certificate is independently verified; changes may signal a different laptop or connection interception.
- **Wrong PIN:** use the laptop's existing six-digit parent PIN. Multiple failed attempts temporarily block logins.
- **Picture unavailable:** ensure the child is signed in to their desktop and optional screen viewing is enabled; individual unsaved pictures expire.
- **Android reports signature conflict:** the previous APK was signed with a different key. Future releases need the same persistent signing certificate (see the Android developer notes). Uninstalling the old Android app may be necessary once to establish a new signing identity.
- **Tailscale:** both devices must be connected to the private VPN; use the private `https://...ts.net` hostname, not public port forwarding.

Never expose the laptop dashboard publicly, share a PIN/keystore in support issues or treat the experimental graphical lock as tamper-proof.