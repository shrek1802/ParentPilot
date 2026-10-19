#!/usr/bin/python3
"""Adult-approved ParentPilot DEB updater (not part of the child UI).

Only for machines provisioned by the NEW Debian-family wizard. Never adopt or
overwrite an older customized installation, and never reset accounts or PINs.
The updater is run via pkexec, re-fetches release metadata as root, validates the
package digest and metadata, backs up files, and verifies the service after update.
"""
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from update_release import (
    RELEASE_PREFIX, TAG, MAX_DEB, fetch_updates, hash_file, installed_version,
    newer_version,
)

CFG = Path('/etc/max-family-control')
DATA = Path('/var/lib/max-family-control')
TARGET = Path('/opt/max-family-control')
PACKAGE = Path('/usr/lib/parentpilot/desktop')
UNIT = Path('/etc/systemd/system/max-family-control.service')
MARKER = CFG / '.parentpilot-deb-managed'
BACKUPS = Path('/var/backups/parentpilot')
SYSTEMCTL = '/usr/bin/systemctl'
TRUSTED_DOWNLOAD_HOSTS = {
    'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'
}


def cmd(*args, timeout=120):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)


def configured_for_updates():
    return (MARKER.is_file() and not MARKER.is_symlink()
            and TARGET.is_dir() and (CFG / 'config.json').is_file()
            and UNIT.is_file())


def child_signed_in():
    # Updating executable lock code during an active child session is unsafe.
    try:
        child = json.loads((CFG / 'config.json').read_text())['child']
        session_output = cmd('loginctl', 'list-sessions', '--no-legend', timeout=6).stdout
        for line in session_output.splitlines():
            columns = line.split()
            if len(columns) >= 3 and columns[2] == child:
                return True
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired):
        # Unknown session state: conservative; require parent intervention.
        return True
    return False


def save_snapshot():
    BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    BACKUPS.chmod(0o700)
    backup = BACKUPS / (time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(5))
    backup.mkdir(mode=0o700)
    for name, source in [
        ('deployed', TARGET), ('configuration', CFG), ('data', DATA)
    ]:
        if source.exists():
            shutil.copytree(source, backup / name, symlinks=True)
    shutil.copy2(UNIT, backup / 'control-service.unit')
    # Preserve ONLY the managed child's XFCE panel file, not their entire
    # home directory. The layout patch never changes parent accounts.
    try:
        child = json.loads((CFG / 'config.json').read_text())['child']
        child_entry = pwd.getpwnam(child)
        panel_file = (Path(child_entry.pw_dir) /
                      '.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml')
        if panel_file.is_file() and not panel_file.is_symlink():
            shutil.copy2(panel_file, backup / 'child-panel.xml')
    except (OSError, KeyError, ValueError):
        raise RuntimeError('Cannot back up the child panel. Refusing update.')
    (backup / 'version.txt').write_text(installed_version() + '\n')
    (backup / 'version.txt').chmod(0o600)
    print('Private backup created: ' + str(backup), flush=True)
    return backup


def restore_snapshot(backup):
    # This restores deployed control code and app data. It cannot change the
    # Debian package version installed by apt; disclose that limitation.
    for name, destination in [
        ('deployed', TARGET), ('configuration', CFG), ('data', DATA)
    ]:
        source = backup / name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
    saved_panel = backup / 'child-panel.xml'
    if saved_panel.is_file():
        child = json.loads((CFG / 'config.json').read_text())['child']
        child_entry = pwd.getpwnam(child)
        panel_file = (Path(child_entry.pw_dir) /
                      '.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml')
        if not panel_file.is_symlink() and panel_file.parent.is_dir():
            shutil.copy2(saved_panel, panel_file)
            os.chown(panel_file, child_entry.pw_uid, child_entry.pw_gid)
    original_unit = backup / 'control-service.unit'
    if original_unit.is_file():
        shutil.copy2(original_unit, UNIT)
    cmd(SYSTEMCTL, 'daemon-reload', timeout=30)


def download_verified(release, directory):
    url = release['url']
    if not url.startswith(RELEASE_PREFIX + release['tag'] + '/'):
        raise ValueError('Unexpected release origin.')
    request = urllib.request.Request(
        url, headers={'User-Agent': 'ParentPilot-Linux-Updater'})
    path = directory / release['filename']
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            actual_url = urllib.parse.urlparse(response.geturl())
            if actual_url.scheme != 'https' or actual_url.hostname not in TRUSTED_DOWNLOAD_HOSTS:
                raise ValueError('Download redirected to an untrusted server.')
            total = 0
            with open(path, 'xb') as output:
                while True:
                    block = response.read(1024 * 128)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_DEB or total > release['size']:
                        raise ValueError('Downloaded package exceeds its declared size.')
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
        if total != release['size']:
            raise ValueError('Incomplete ParentPilot DEB.')
        if hash_file(path) != release['sha256']:
            raise ValueError('ParentPilot package SHA-256 does not match published release.')
        pkg = cmd('dpkg-deb', '-f', str(path), 'Package', timeout=10).stdout.strip()
        version = cmd('dpkg-deb', '-f', str(path), 'Version', timeout=10).stdout.strip()
        arch = cmd('dpkg-deb', '-f', str(path), 'Architecture', timeout=10).stdout.strip()
        if pkg != 'parentpilot' or version != release['version'] or arch != 'all':
            raise ValueError('Unexpected package name, architecture, or version.')
        if not newer_version(version, installed_version()):
            raise ValueError('This release is no longer newer than the installed version.')
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def deploy_program_files():
    if not PACKAGE.is_dir() or not (PACKAGE / 'control_server.py').is_file():
        raise RuntimeError('The new ParentPilot package does not contain control files.')
    # Copy only package-owned files, preserve local ancillary files.
    shutil.copytree(PACKAGE, TARGET, dirs_exist_ok=True)
    for item in PACKAGE.rglob('*'):
        if item.is_file():
            other = TARGET / item.relative_to(PACKAGE)
            if hash_file(item) != hash_file(other):
                raise IOError('Package deployment integrity check failed: ' + item.name)


def repair_managed_child_panel():
    """Apply layout refresh as child user, never root, only to our XFCE panel."""
    child = json.loads((CFG / 'config.json').read_text())['child']
    account = pwd.getpwnam(child)
    if account.pw_uid == 0:
        raise RuntimeError('Refusing to repair the root account panel.')
    program = '/usr/lib/parentpilot/child_panel.py'
    if not Path(program).is_file():
        raise RuntimeError('Child panel repair module missing from DEB.')
    result = cmd('runuser', '-u', child, '--', '/usr/bin/python3',
                 program, '--repair', timeout=30)
    print(result.stdout.strip(), flush=True)


def health_check():
    cmd(SYSTEMCTL, 'restart', 'max-family-control.service', timeout=25)
    cmd(SYSTEMCTL, 'is-active', '--quiet', 'max-family-control.service', timeout=10)
    # ParentPilot server is HTTPS using a locally generated self-signed cert.
    # This is a loopback-only liveness check, never a remote credential request.
    ctx = ssl._create_unverified_context()
    for _ in range(15):
        try:
            with urllib.request.urlopen('https://127.0.0.1:8743/',
                                        context=ctx, timeout=3) as answer:
                if answer.status == 200:
                    return
        except (OSError, ValueError):
            time.sleep(0.6)
    raise RuntimeError('ParentPilot service did not respond after updating.')


def install(channel, expected_tag):
    if not configured_for_updates():
        raise RuntimeError(
            'This is not a fresh DEB-managed ParentPilot installation. '
            'Existing customised systems must not be updated automatically.')
    if child_signed_in():
        raise RuntimeError(
            'The child is currently signed in. Sign the child out from XFCE '
            'before updating so the active lock cannot be interrupted.')
    current = installed_version()
    release = fetch_updates(channel, current)
    if not release or release['tag'] != expected_tag:
        raise RuntimeError('Selected release is unavailable or is no longer the latest.')
    print('Verified release metadata for ' + release['version'], flush=True)
    with tempfile.TemporaryDirectory(prefix='parentpilot-update-') as work:
        directory = Path(work)
        archive = download_verified(release, directory)
        backup = save_snapshot()
        try:
            print('Installing verified DEB through APT…', flush=True)
            cmd('apt-get', 'install', '-y', '--no-remove',
                '--no-install-recommends', str(archive), timeout=300)
            deploy_program_files()
            repair_managed_child_panel()
            health_check()
        except Exception:
            print('Update failed. Restoring previously deployed service and data…', flush=True)
            try:
                restore_snapshot(backup)
                health_check()
                print('Previously deployed control service restored. '
                      'APT package metadata may still show a newer version.', flush=True)
            except Exception as recovery:
                print('AUTOMATIC RECOVERY FAILED: ' + str(recovery), file=sys.stderr)
                print('Private backup available at: ' + str(backup), file=sys.stderr)
            raise
    print('SUCCESS: updated ParentPilot to ' + release['version'] +
          '; child account, PIN, timer data and saved pictures retained.', flush=True)
    print('Please ask the child to log in again to load the updated desktop.', flush=True)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Administrator authentication is required.')
    if len(sys.argv) != 3 or sys.argv[1] not in ('stable', 'preview'):
        raise ValueError('Usage: update_install.py stable|preview RELEASE_TAG')
    channel, tag = sys.argv[1], sys.argv[2]
    if not TAG.fullmatch(tag):
        raise ValueError('Invalid release tag.')
    install(channel, tag)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('PARENTPILOT UPDATE STOPPED: ' + str(error), file=sys.stderr)
        sys.exit(1)
