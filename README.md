# ParentPilot — Family Screen Time Control

![ParentPilot](assets/parentpilot-logo.svg)

ParentPilot is an experimental screen-time controller for Linux Mint XFCE with an Android companion for local Wi-Fi discovery and an optional private Tailscale connection.

**Status: developer preview, not an enforcement-grade parental lock.** The Linux app can be bypassed by a sufficiently technical user. The Android companion source is not yet a signed or tested release APK.

The project was developed for a child account on Linux Mint, with configurable child display name and username, parent-approved extra time, daily allowances, paused screen and a mobile parent dashboard.

## Layout

- `desktop/`: Python timer service, web dashboard, child overlay, installer, and tests.
- `android-app/`: Android Studio companion for Wi-Fi discovery and launching the parent dashboard.
- `assets/`: shared app artwork.

**Please don't run the fresh installer on an existing working setup.** The original Max laptop uses customised v0.2.2 and should only be upgraded after a backup and compatibility test.

See `desktop/README.md` for setup instructions when available.
