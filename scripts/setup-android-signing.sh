#!/usr/bin/env bash
# ParentPilot: one-time permanent Android signing on your own trusted Linux PC.
# Creates the private key locally and uploads it directly to encrypted GitHub
# Actions secrets. NEVER upload keys to issues, chats, or the public repository.
set -Eeuo pipefail
umask 077

REPO='shrek1802/ParentPilot'
ALIAS='parentpilot'
PRIVATE_DIR="$HOME/.local/share/parentpilot/signing"
KEYSTORE="$PRIVATE_DIR/parentpilot-release.jks"
PASSWORD_FILE="$PRIVATE_DIR/signing-password.txt"
FINGERPRINT_FILE="$PRIVATE_DIR/certificate-sha256.txt"

say() { printf '\n%s\n' "$*"; }
fail() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

if [[ "$EUID" -eq 0 ]]; then
  fail 'Run as your adult Linux user, NEVER using sudo.'
fi
[[ -d "$HOME" ]] || fail 'HOME directory unavailable.'
for item in gh keytool openssl base64; do
  if ! command -v "$item" >/dev/null 2>&1; then
    say 'Install these prerequisites on Linux Mint, then run the script again:'
    printf '%s\n' 'sudo apt update && sudo apt install gh openjdk-17-jdk-headless openssl'
    fail "Missing $item"
  fi
done

say 'ParentPilot — PERMANENT Android release signing'
say "Repository: $REPO"
say 'The key will stay on your PC and in encrypted GitHub Secrets, never in GitHub code.'

if ! gh auth status -h github.com >/dev/null 2>&1; then
  say 'Sign into your GitHub account in the browser…'
  gh auth login -h github.com -p https -w || fail 'GitHub login not completed.'
fi
gh secret list --repo "$REPO" --app actions >/dev/null ||
  fail 'GitHub Actions secret access denied. Sign into a repository administrator account.'

[[ ! -L "$PRIVATE_DIR" ]] || fail 'Signing folder cannot be a symlink.'
mkdir -p "$PRIVATE_DIR"
chmod 700 "$PRIVATE_DIR"
[[ ! -L "$KEYSTORE" && ! -L "$PASSWORD_FILE" ]] ||
  fail 'Unexpected symlink signing file; stopping.'

# Refuse accidental key rotation: replacing the old key would break Android updates.
if [[ ! -e "$KEYSTORE" && ! -e "$PASSWORD_FILE" ]]; then
  if gh secret list --repo "$REPO" --app actions |
      grep -Eq '^PARENTPILOT_SIGNING_KEYSTORE_B64([[:space:]]|$)'; then
    fail 'GitHub already contains a permanent key. Recover its original backup, rather than creating a new one.'
  fi
  say 'Generating the permanent RSA signing key locally…'
  tmpdir="$(mktemp -d "$PRIVATE_DIR/.new-signing.XXXXXXXX")"
  trap 'rm -rf -- "$tmpdir"' EXIT
  openssl rand -hex 32 > "$tmpdir/signing-password.txt"
  export PP_SIGN_PASS
  PP_SIGN_PASS="$(cat "$tmpdir/signing-password.txt")"
  keytool -genkeypair -noprompt -storetype JKS \
    -keystore "$tmpdir/parentpilot-release.jks" -alias "$ALIAS" \
    -keyalg RSA -keysize 3072 -validity 9125 \
    -dname 'CN=ParentPilot, OU=Family Software, O=ParentPilot, C=GB' \
    -storepass:env PP_SIGN_PASS -keypass:env PP_SIGN_PASS >/dev/null ||
    fail 'Java could not create the private key.'
  [[ -s "$tmpdir/parentpilot-release.jks" ]] || fail 'Keystore was not generated.'
  mv "$tmpdir/parentpilot-release.jks" "$KEYSTORE"
  mv "$tmpdir/signing-password.txt" "$PASSWORD_FILE"
  chmod 600 "$KEYSTORE" "$PASSWORD_FILE"
  rm -rf "$tmpdir"
  trap - EXIT
  say 'New permanent key created. Subsequent runs REUSE the same key.'
elif [[ -f "$KEYSTORE" && -f "$PASSWORD_FILE" ]]; then
  say 'Existing permanent key found — reusing it.'
else
  fail 'One signing file is missing. Restore the original key AND password from backup.'
fi

chmod 600 "$KEYSTORE" "$PASSWORD_FILE"
export PP_SIGN_PASS
PP_SIGN_PASS="$(cat "$PASSWORD_FILE")"
[[ "$PP_SIGN_PASS" =~ ^[0-9a-f]{64}$ ]] || fail 'Invalid stored signing password.'
keytool -list -storetype JKS -keystore "$KEYSTORE" -alias "$ALIAS" \
  -storepass:env PP_SIGN_PASS >/dev/null ||
  fail 'Could not open the saved private signing key.'

# Public certificate fingerprint, safe to display and compare in CI.
fingerprint="$(
  keytool -exportcert -rfc -storetype JKS -keystore "$KEYSTORE" \
    -alias "$ALIAS" -storepass:env PP_SIGN_PASS |
    openssl x509 -noout -fingerprint -sha256 |
    sed 's/^.*=//' | tr -d ':\r\n' | tr '[:upper:]' '[:lower:]'
)"
[[ "$fingerprint" =~ ^[0-9a-f]{64}$ ]] ||
  fail 'Cannot verify the signing certificate fingerprint.'
printf '%s\n' "$fingerprint" > "$FINGERPRINT_FILE"
chmod 644 "$FINGERPRINT_FILE"

say 'Sending five secret values directly to GitHub Actions (not displaying them)…'
base64 -w0 "$KEYSTORE" |
  gh secret set PARENTPILOT_SIGNING_KEYSTORE_B64 -R "$REPO" --app actions ||
  fail 'GitHub rejected keystore upload. Your local key was retained.'
printf '%s' "$PP_SIGN_PASS" |
  gh secret set PARENTPILOT_SIGNING_STORE_PASSWORD -R "$REPO" --app actions ||
  fail 'GitHub rejected store password upload.'
printf '%s' "$ALIAS" |
  gh secret set PARENTPILOT_SIGNING_KEY_ALIAS -R "$REPO" --app actions ||
  fail 'GitHub rejected signing alias upload.'
printf '%s' "$PP_SIGN_PASS" |
  gh secret set PARENTPILOT_SIGNING_KEY_PASSWORD -R "$REPO" --app actions ||
  fail 'GitHub rejected key password upload.'
printf '%s' "$fingerprint" |
  gh secret set PARENTPILOT_ANDROID_EXPECTED_CERT_SHA256 -R "$REPO" --app actions ||
  fail 'GitHub rejected certificate fingerprint upload.'
unset PP_SIGN_PASS

for name in \
  PARENTPILOT_SIGNING_KEYSTORE_B64 \
  PARENTPILOT_SIGNING_STORE_PASSWORD \
  PARENTPILOT_SIGNING_KEY_ALIAS \
  PARENTPILOT_SIGNING_KEY_PASSWORD \
  PARENTPILOT_ANDROID_EXPECTED_CERT_SHA256
do
  gh secret list -R "$REPO" --app actions |
    grep -Eq "^$name([[:space:]]|$)" ||
    fail "Secret $name could not be confirmed."
done

say 'SUCCESS! GitHub Actions now has the permanent ParentPilot signing credentials.'
printf 'Public certificate SHA-256: %s\n' "$fingerprint"
printf 'Private keystore backup: %s\n' "$KEYSTORE"
printf 'Private password backup: %s\n' "$PASSWORD_FILE"
say 'Back up BOTH private files to an encrypted offline drive. NEVER share them in chat.'
say 'Next: run the Android build on GitHub; it will verify the same certificate.'
