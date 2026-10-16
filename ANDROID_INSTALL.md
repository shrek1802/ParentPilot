# ParentPilot Android companion — install and test

This is an **installable Android debug APK**, built from the sources in `android-app/` using GitHub Actions. It is signed using the Android SDK debug signing key. It is **not yet a production/Play Store release or device-tested app**.

## Get the APK

1. Open [GitHub Actions — Build ParentPilot Android APK](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml).
2. Select the most recent successful run on `main`.
3. Under **Artifacts**, download `ParentPilot-Android-debug-APK` (GitHub sign-in might be required).
4. Extract the ZIP; it contains `app-debug.apk`.
5. Copy the APK to an Android 8.0+ phone, open it with Files, and allow installation from the chosen source when Android asks.

## Discover the laptop (same Wi-Fi)

Install the separate `desktop/enable-discovery-existing.sh` script on a laptop that already has a **working** ParentPilot timer. This only enables Avahi/mDNS broadcasting; it does not change screen-time settings.

Connect both devices to the same Wi-Fi and open ParentPilot Android. Tap **Find nearby laptop**. Select your own laptop to open its existing HTTPS PIN dashboard in Chrome. The current laptop certificate is locally self-signed and Chrome may ask for one-time trust confirmation; verify the device is yours before proceeding. Guest Wi-Fi isolation and some hotspots block mDNS.

## When the laptop and phone are in different places

The Android app only auto-discovers laptops on the **same local network**. With Tailscale running on both devices and Tailscale Serve configured on the laptop, save the private HTTPS `.ts.net` name once to open it from elsewhere. Never expose port 8743 to the public internet.

## Debug APK notes

The debug build is for family testing. It isn't signed with a dedicated release key, so a future production-signed build may require uninstalling this APK first. It contains no PIN. PIN entry happens in the laptop's authenticated HTTPS dashboard. Always keep the laptop's working settings backed up and don't assume the fullscreen overlay is tamper-proof.

## ParentPilot Android v0.3.2 discovery troubleshooting

The **Find nearby laptop** button now shows a scan status immediately. If nothing responds within 12 seconds, the app explains what to check and offers **Connect directly on your Wi-Fi**.

To let the laptop announce its presence, run the existing optional `desktop/enable-discovery-existing.sh` with sudo on the laptop's adult account. It does not change the child PIN, timer or saved allowance. If it is already configured, the laptop should have `avahi-daemon` active and the file `/etc/avahi/services/family-control.service` present. Restarting the Android search does not install those laptop prerequisites.

For the **direct Wi-Fi fallback**, enter only the laptop's current private IPv4 address (for example `192.168.1.249`) or `https://192.168.1.249:8743/`. The app opens the HTTPS parent PIN dashboard in the phone's browser and saves the private IP for later; it never saves the PIN. This direct connection works when mDNS is blocked but the phone can still reach the laptop.

If Android doesn't grant discovery permissions, open **Settings → Apps → ParentPilot → Permissions** and allow the nearby-device permission, when available. Check both are on the same local network (not an isolated guest Wi-Fi). Some phone hotspot and caravan Wi-Fi systems block multicast or client-to-client traffic. If the IP address changes, update the saved address.

**Upgrading test APKs:** These are debug builds. On some phones a later build cannot replace an older APK because the debug signing key differs. If Android reports a signature/package conflict, uninstall only the old **ParentPilot Android app** and install the new APK. This doesn't touch the laptop timer, although you'll need to re-enter the saved phone connection details.
