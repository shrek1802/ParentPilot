# ParentPilot Android companion — source preview

This is a minimal Android app written in Kotlin using the Android SDK's `NsdManager`. It finds `_maxfamily._tcp.` services advertised over the same Wi-Fi by the Linux laptop's Avahi daemon. It opens the PIN-protected parental HTTPS dashboard using the phone's browser; the PIN is not collected or stored by the app.

For use when the laptop is elsewhere, paste your **private** Tailscale Serve `https://....ts.net` URL. Both devices must be in the same private Tailscale network; Tailscale must be running on the phone.

**Build:** Open this `android-app` folder in Android Studio (Android SDK Platform 35, JDK 17), sync Gradle using a suitable Gradle 8.9 installation/wrapper, and build a debug APK. The source has not been compiled or device-tested in the authoring environment and **no APK is supplied**. A production release needs phone testing, signed builds, certificate/device pairing improvements and permissions review.

Never bypass TLS errors in an embedded browser. The app launches the default browser so the browser handles HTTPS trust checks. Local laptops currently use a self-signed certificate, and an unfamiliar Wi-Fi device could impersonate an mDNS service name, so verify the destination before entering your PIN. For remote use, Tailscale Serve presents a TLS certificate for the private `.ts.net` address.
