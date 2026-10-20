#!/usr/bin/python3
"""Adult-approved, separate Kodi Flatpak trial on a managed ParentPilot laptop.

No APT Kodi removal, no migration of ~/.kodi, no change to child panel pins.
Only the official signed Flathub remote and the exact stable Kodi app ID.
The distinct test launcher is written only after installation succeeds.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from games_install import parentpilot_configured, validate_adult_origin

FLATPAK = '/usr/bin/flatpak'
APT = '/usr/bin/apt-get'
APP = 'tv.kodi.Kodi'
REMOTE = 'flathub'
REMOTE_URL = 'https://flathub.org/repo/flathub.flatpakrepo'
APP_REF = 'tv.kodi.Kodi//stable'
SHORTCUT = Path('/usr/share/applications/parentpilot-kodi-flatpak-test.desktop')
ORIGINS = {'https://dl.flathub.org/repo', 'https://flathub.org/repo'}
STAGE = 'PARENTPILOT_KODI_TEST:'

DESKTOP_ENTRY = (
    '[Desktop Entry]\n'
    'Type=Application\n'
    'Name=Kodi (New Version Test)\n'
    'Comment=Try the official Flathub Kodi without changing classic Kodi\n'
    'Exec=/usr/bin/flatpak run --system tv.kodi.Kodi\n'
    'Icon=tv.kodi.Kodi\n'
    'Terminal=false\n'
    'Categories=AudioVideo;Player;\n'
)


def announce(stage, detail):
    print(STAGE + stage + ':' + detail, flush=True)


def run_checked(args, timeout=300, runner=subprocess.run):
    """Invoke only fixed executable argument arrays; never use a shell."""
    p = runner(args, check=False, capture_output=True, text=True,
               timeout=timeout)
    if p.returncode != 0:
        error = (p.stderr or p.stdout or 'Command failed').strip()[-750:]
        raise RuntimeError(error)
    return (p.stdout or '').strip()


def flathub_origin(available_remotes):
    """Refuse an existing remote named flathub pointing elsewhere."""
    for line in available_remotes.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0] == REMOTE:
            return parts[1].rstrip('/')
    return None


def write_launcher(target=SHORTCUT):
    if target.is_symlink():
        raise RuntimeError('Refusing to replace a linked Kodi test shortcut.')
    if target.exists() and target.read_text(encoding='utf8') != DESKTOP_ENTRY:
        raise RuntimeError('An unrelated Kodi test launcher already exists.')
    target.write_text(DESKTOP_ENTRY, encoding='utf8')
    target.chmod(0o644)


def install_test(runner=subprocess.run, flatpak_exists=None, launcher=write_launcher):
    if flatpak_exists is None:
        flatpak_exists = Path(FLATPAK).is_file()
    if not flatpak_exists:
        announce('flatpak', 'Installing the Flatpak manager from Linux Mint APT…')
        run_checked([APT, 'install', '-y', '--no-install-recommends', 'flatpak'],
                    timeout=300, runner=runner)

    announce('remote', 'Checking the official signed Flathub repository…')
    run_checked([FLATPAK, '--system', 'remote-add', '--if-not-exists',
                 REMOTE, REMOTE_URL], timeout=90, runner=runner)
    remotes = run_checked(
        [FLATPAK, 'remotes', '--system', '--columns=name,url'],
        timeout=45, runner=runner)
    if flathub_origin(remotes) not in ORIGINS:
        raise RuntimeError('The existing Flathub remote has an unexpected URL. Installation stopped.')

    announce('install', 'Downloading and installing stable Kodi Flatpak and its runtime…')
    # Can take several minutes on older laptops. Flatpak will install missing
    # signed runtimes. This installs system-wide so the CHILD can use the app,
    # not just the adult account. Existing distro Kodi is untouched.
    run_checked([FLATPAK, '--system', 'install', '-y', '--noninteractive',
                 REMOTE, APP_REF], timeout=2400, runner=runner)

    announce('check', 'Verifying that the new Kodi is installed…')
    version = run_checked([FLATPAK, 'info', '--system', '--show-version',
                           APP], timeout=50, runner=runner)
    if not re.fullmatch(r'[0-9A-Za-z_.+-]{1,45}', version):
        raise RuntimeError('Unable to verify the new Kodi version.')
    launcher()
    announce('ready', 'Installed Kodi ' + version + '. Open Kodi (New Version Test) from Applications → Multimedia.')
    return version


def main():
    if os.geteuid() != 0 or sys.argv[1:] != ['--install-test']:
        raise RuntimeError('Only the adult ParentPilot Control Centre can install a Kodi trial.')
    validate_adult_origin()
    if not parentpilot_configured():
        raise RuntimeError('This laptop has not completed ParentPilot family setup.')
    install_test()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError,
            subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
        print('Kodi Flatpak test stopped: ' + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
