# ParentPilot Android companion

The ParentPilot Android companion helps parents connect to a ParentPilot-controlled Linux laptop. It discovers devices on the **same Wi-Fi** using Android network service discovery, then opens the laptop's **PIN-protected HTTPS dashboard in the phone's browser**.

**Current scope:** The Android app is a discovery and connection companion, not a fully native parental dashboard. It does not collect or store the parent PIN.

## Install a test build

GitHub Actions produces a downloadable **debug APK** for testing:

1. Open [Build ParentPilot Android APK](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml).
2. Open a successful workflow run and download **ParentPilot-Android-debug-APK** under **Artifacts**.
3. Extract the artifact ZIP, then install `app-debug.apk` on a test Android device.

This build is **not Play Store ready** or production-signed. A different debug signing key can prevent one test APK from installing over another.

For complete installation, permissions and connection instructions, see [the Android setup guide](../ANDROID_INSTALL.md).

## Connect to a laptop

- **Same Wi-Fi:** select **Find nearby laptop**. Android discovery requires multicast/mDNS and client-to-client traffic; some guest networks and hotspots block it.
- **Direct local connection:** enter the laptop's private IP address if automatic discovery fails.
- **Different networks:** configure a **private VPN** such as Tailscale and use the laptop's private HTTPS hostname. Never publicly forward the parental control port.

The laptop may use a local, self-signed HTTPS certificate. Confirm that the device you are connecting to is yours before trusting a browser warning. The app uses the system browser for HTTPS and PIN entry.

## Build from source

The app is written in **Kotlin** with Android's `NsdManager`. Open `android-app/` in Android Studio with a compatible Android SDK/JDK and Gradle toolchain. The [Android CI workflow](https://github.com/shrek1802/ParentPilot/actions/workflows/build-android.yml) defines the automated debug build.

## Development status

Real-device testing across different Android releases, routers and Linux desktops is still needed. Release signing, authenticated device pairing and fully native parent controls have not been completed. Treat all APKs as **development previews**, and do not include family-identifying data in public bug reports.
