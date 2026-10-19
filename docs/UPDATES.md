# ParentPilot updates — Android and Linux

ParentPilot's automatic **update notifications and parent-approved installers** are introduced in the Preview 8 Linux DEB and Android v0.4.2 (version code 7).

**Development status:** the updater logic has automated build and security tests, but end-to-end release installation on a physical XFCE laptop and Android phone must be tested before this is offered as a public stable product.

## What a parent sees

**Android:** after signing into the native ParentPilot app, it checks for newer published GitHub Releases. When one is available, a small notice appears on the Home tab. Open **More → Software updates** for the new version, release notes and **Download and install update**. The app downloads the APK into its private cache, verifies GitHub's published SHA-256 digest, checks the Android package ID, version and exact signing certificate against the currently installed app, then opens **Android's system installer**. The parent explicitly approves installation. No direct browser dashboard or silent installs.

**Linux XFCE:** the adult administrator's desktop checks for updates when the adult logs in and displays a small desktop notification if a newer stable release is available. Open **Applications → Settings → ParentPilot Updates** to see the installed version, release notes, Stable/Preview channel and **Install update**. The installer requires a fresh administrator authentication prompt through PolicyKit (pkexec).

Children do not get update controls. The updater checks for a child desktop session and **refuses to replace active child lock code while a child is signed in**.

## Linux upgrade safeguards

The Linux updater is **only supported on a laptop newly configured with the Preview 8 (or newer) DEB setup wizard**. The first-run wizard writes a root-owned \`.parentpilot-deb-managed\` marker only after successful setup. Earlier hand-customised installations do not have the marker and are deliberately refused.

The privileged upgrade helper:
1. Re-checks the official GitHub Releases API as root and refuses temporary GitHub Actions artifacts.
2. Downloads the declared ParentPilot DEB over HTTPS, checks its GitHub-published SHA-256 digest, package identity, architecture and newer Debian version.
3. Creates a private root-only snapshot under \`/var/backups/parentpilot/\` of the deployed desktop code, parent PIN configuration, tokens, state, saved screenshots and service unit.
4. Installs the verified DEB using APT **without re-running the first-time wizard** or recreating accounts.
5. Deploys the new package-owned program files, restarts the timer service and checks that the local dashboard responds.
6. If something fails, restores backed-up program files and settings and tries to restart the previous service. **This is service/data recovery, not guaranteed full package rollback**: after an APT failure the package database may still reflect a new version and require manual repair.

**Don't shut down the laptop during installation.** Sign the child out before updating, then sign them back in after a successful upgrade. Backups contain private PIN hashes, tokens and screen pictures, so never upload them publicly.

## Stable and preview release channels

Android currently checks **Stable** releases only. The Linux administrator can deliberately switch between **Stable** and **Preview** in ParentPilot Updates. Debug Android preview APKs are not automatically installable upgrades because their signing certificate changes between CI builds.

Both updaters read **published GitHub Releases** with appropriately named assets:

| Platform | Expected asset | Other requirements |
| --- | --- | --- |
| Android | \`ParentPilot-Android-v7.apk\` (versionCode increases every release) | Same installed package ID and permanent APK signer; published SHA-256 digest |
| Linux | \`parentpilot_0.5.0~preview8_all.deb\` (example) | Debian version newer than installed; published SHA-256 digest; newly managed installation marker |

CI Artifacts are **not releases** and expire, so they do not trigger an update notice. Notifications require a qualifying published release with a valid asset name, SHA-256 digest and newer version. GitHub release asset names normalise the Debian tilde to a dot (for example `parentpilot_0.5.0.preview8_all.deb`), while the internal Debian package version stays `0.5.0~preview8`.

## Maintainer release publishing

Repository: \`shrek1802/ParentPilot\`. A gated [GitHub Actions release workflow](../.github/workflows/publish-parentpilot-release.yml) runs when a maintainer deliberately pushes a tag such as \`v0.5.0-preview8\`. It requires all five private secrets **before publishing anything**:

- \`PARENTPILOT_SIGNING_KEYSTORE_B64\`: base64-encoded permanent private Android JKS keystore
- \`PARENTPILOT_SIGNING_STORE_PASSWORD\`
- \`PARENTPILOT_SIGNING_KEY_ALIAS\`
- \`PARENTPILOT_SIGNING_KEY_PASSWORD\`
- \`PARENTPILOT_ANDROID_EXPECTED_CERT_SHA256\`: hex fingerprint of the expected APK signing certificate

Create the private keystore **on a trusted computer** with Android Studio or \`keytool\`, back it up securely, and set the secrets using **GitHub → Repository Settings → Secrets and variables → Actions**. Never add a signing key, passwords, tokens, or plaintext base64 keystore to the public repository or an issue. Losing the key prevents updating an app installed under that signer.

The workflow compares the signed APK's certificate with the expected persistent fingerprint before publishing, builds the Linux DEB, runs tests, and publishes both assets with GitHub-generated SHA-256 digests and release notes.

**Important migration:** old GitHub debug APKs used different temporary signing certificates. Keeping the Android application ID alone does not allow them to update each other. The user may need to uninstall **only the old Android phone app once** to move to the permanent release-signed APK. The child laptop, its timer, accounts, PIN and gallery are unaffected by an Android phone-app reinstall. Once using a persistent private signer, later releases signed with that same key will update normally.

## Security limitations and release gates

GitHub Release digests detect corrupted or substituted downloads relative to GitHub metadata, but **are not an independent publisher signature**. A compromised GitHub release account could change both an asset and its digest. Before general public deployment, add an independently verified package signature or signed APT repository for Linux, audit the updater and test both normal upgrades and failure recovery on spare devices.

Do **not** hand a laptop to another family relying on updates until the first-release signing key is configured, a matching signed release is published and tested, and a complete fresh-install/upgrade/rollback drill has passed on a disposable XFCE/X11 laptop.
