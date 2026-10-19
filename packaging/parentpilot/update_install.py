#!/usr/bin/python3
"""Adult-approved ParentPilot DEB updater (not part of the child UI).

Only for machines provisioned by the NEW Debian-family wizard. Never adopt or
overwrite an older customized installation, and never reset accounts or PINs.
The updater is run via pkexec, re-fetches release metadata as root, validates the
package digest and metadata, backs up files, and verifies the service after update.
"""
import json
import os
import grp
import signal
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


def child_session_block_reason():
    """Protect active child XFCE sessions, but ignore fully closing stale logind records.

    XFCE's Switch user leaves the child session online even if it is not the
    currently visible session; that's NOT a logout. Conversely, systemd-logind
    can report a transient State=closing session after a proper logout.
    Only ignore the latter after independently checking no child XFCE UI/lock
    process remains. Unknown status must fail closed.
    """
    try:
        child = json.loads((CFG / 'config.json').read_text())['child']
        if not isinstance(child, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', child):
            raise ValueError('Invalid child account in configuration.')
        session_output = cmd('loginctl', 'list-sessions', '--no-legend', timeout=6).stdout
        sessions = []
        for line in session_output.splitlines():
            columns = line.split()
            if len(columns) < 3:
                raise ValueError('Unexpected loginctl session listing.')
            if columns[2] == child:
                session_id = columns[0]
                if not re.fullmatch(r'[a-zA-Z0-9]{1,24}', session_id):
                    raise ValueError('Unexpected loginctl session identifier.')
                sessions.append(session_id)
        if not sessions:
            return None

        for session_id in sessions:
            result = cmd('loginctl', 'show-session', session_id,
                         '-p', 'Name', '-p', 'State', '-p', 'Active',
                         '-p', 'Type', timeout=6).stdout
            details = dict(
                line.split('=', 1) for line in result.splitlines() if '=' in line
            )
            if details.get('Name') != child:
                raise ValueError('Unexpected session owner.')
            state = details.get('State', '').lower()
            active = details.get('Active', '').lower()
            if state == 'closing' and active == 'no':
                # Some XFCE child sessions take time to clean up; do not
                # restart the lock while a graphical process still exists.
                ps = subprocess.run(
                    ['ps', '-u', child, '-o', 'args='],
                    capture_output=True, text=True, timeout=6, check=False)
                if ps.returncode not in (0, 1):
                    raise RuntimeError('Cannot inspect child processes.')
                if any(part in ps.stdout for part in (
                        'xfce4-session', 'xfce4-panel', 'xfwm4',
                        '/max_desktop.py', '/max_desktop_supervisor.py')):
                    return ('Child session ' + session_id +
                            ' is still shutting down with a running desktop. '
                            'Wait a moment and try again.')
                continue
            if state not in ('active', 'online', 'closing') or active not in ('yes', 'no'):
                raise ValueError('Unknown loginctl session state.')
            return ('Child Linux session ' + session_id + ' is still ' + state +
                    ' (active=' + active + '). Switching users does not log '
                    'the child out. From the adult account, use '
                    '"sudo loginctl terminate-user ' + child + '" after saving '
                    "the child's open work, then retry.")
        return None
    except (OSError, KeyError, ValueError, RuntimeError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return ('Cannot safely confirm that the child is logged out (' +
                type(exc).__name__ + '). From the adult account, check '
                '"loginctl list-sessions" and try again.')


def child_signed_in():
    """Compatibility wrapper for existing clients; fail closed on uncertainty."""
    return child_session_block_reason() is not None


def verified_child_account():
    """Use only the configured non-administrator child, never a supplied username."""
    details = json.loads((CFG / 'config.json').read_text())
    child = details['child']
    if not isinstance(child, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', child):
        raise RuntimeError('Invalid configured child account; update stopped.')
    account = pwd.getpwnam(child)
    if account.pw_uid < 1000 or account.pw_uid == os.getuid():
        raise RuntimeError('Configured child must be a separate non-system Linux user.')
    return child, account


def verify_adult_approved_signout(child_uid):
    """A sign-out request MUST originate from an authenticated adult GUI via pkexec."""
    owner = os.environ.get('PKEXEC_UID', '')
    if not owner.isascii() or not owner.isdecimal():
        raise RuntimeError('Automatic sign-out requires an adult-approved PolicyKit request.')
    caller_uid = int(owner)
    if caller_uid in (0, child_uid):
        raise RuntimeError('Refusing to sign out the administrator or requesting account.')
    caller = pwd.getpwuid(caller_uid)
    group_ids = os.getgrouplist(caller.pw_name, caller.pw_gid)
    adult_groups = {'sudo', 'admin', 'wheel'}
    if not any(grp.getgrgid(g).gr_name in adult_groups for g in group_ids):
        raise RuntimeError('Automatic child sign-out requires a Linux administrator.')
    return caller.pw_name


def signed_in_child_session(reason):
    """Never terminate accounts just because a system query failed or was ambiguous."""
    return (
        reason is not None and (
            reason.startswith('Child Linux session ') or
            reason.startswith('Child session ')
        )
    )


def wait_for_child_logout(seconds=5):
    deadline = time.monotonic() + seconds
    while True:
        reason = child_session_block_reason()
        if reason is None:
            return None
        if not signed_in_child_session(reason):
            raise RuntimeError('Unable to verify child logout safely: ' + reason)
        if time.monotonic() >= deadline:
            return reason
        time.sleep(0.5)


def sign_out_child_with_approval():
    """Explicitly approved by the adult; only after download and private backup.

    XFCE fast user switching leaves the child's session running. logind should
    terminate it; on some Mint machines its orphaned Python/GeoClue processes
    can keep the session in State=closing, so use child-UID scoped SIGTERM only
    after a grace period. Never SIGKILL or terminate unrelated user accounts.
    """
    if not configured_for_updates():
        raise RuntimeError('The original managed installation marker is missing.')
    child, account = verified_child_account()
    parent = verify_adult_approved_signout(account.pw_uid)
    before = child_session_block_reason()
    if before is None:
        return False
    if not signed_in_child_session(before):
        raise RuntimeError('Cannot safely identify the child session: ' + before)
    print('Adult ' + parent + ' approved child account sign-out before upgrading.', flush=True)
    print('Warning: unsaved work in child applications may be lost.', flush=True)
    # Explicit string argument, not a shell command and never the invoking adult.
    result = subprocess.run(
        ['loginctl', 'terminate-user', child],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if result.returncode != 0:
        # Recheck before interpreting a race during a logout as failure.
        if child_session_block_reason() is not None:
            raise RuntimeError('Could not sign out the child through logind: ' +
                               (result.stderr.strip()[:240] or 'unknown failure'))
    blocked = wait_for_child_logout()
    if blocked:
        # Any remaining processes belong to the configured child account only.
        # This is a deliberate second SIGTERM, never a blanket pkill as root.
        r = subprocess.run(
            ['ps', '-u', child, '-o', 'pid='],
            capture_output=True, text=True, timeout=6, check=False,
        )
        if r.returncode not in (0, 1):
            raise RuntimeError('Cannot inspect remaining child processes.')
        for line in r.stdout.splitlines():
            raw = line.strip()
            if not raw.isdecimal():
                raise RuntimeError('Unexpected child process identifier.')
            pid = int(raw)
            if pid <= 1:
                raise RuntimeError('Invalid child process identifier.')
            # Verify the process is still owned by the child (PID reuse guard).
            try:
                status = Path('/proc') / str(pid) / 'status'
                fields = status.read_text().splitlines()
                uids = next(x.split()[1:] for x in fields if x.startswith('Uid:'))
                if int(uids[0]) != account.pw_uid:
                    continue
                os.kill(pid, signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass
            except (OSError, ValueError, StopIteration) as exc:
                raise RuntimeError('Failed to stop an orphaned child process.') from exc
        blocked = wait_for_child_logout(seconds=8)
    if blocked:
        raise RuntimeError('Child session could not finish logging out. ' +
                           'No DEB files were installed; try again from the adult account. ' +
                           blocked)
    print('Child signed out. Administrator session and settings remain intact.', flush=True)
    return True


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


def install(channel, expected_tag, allow_child_signout=False):
    if not configured_for_updates():
        raise RuntimeError(
            'This is not a fresh DEB-managed ParentPilot installation. '
            'Existing customised systems must not be updated automatically.')
    block_reason = child_session_block_reason()
    if block_reason and not allow_child_signout:
        raise RuntimeError(block_reason)
    if block_reason and allow_child_signout and not signed_in_child_session(block_reason):
        raise RuntimeError('Cannot safely identify the child session: ' + block_reason)
    if allow_child_signout:
        _, child_account = verified_child_account()
        verify_adult_approved_signout(child_account.pw_uid)
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
            # Do not sign out the child until the release was downloaded,
            # verified and the private recovery snapshot completed.
            signed_out = False
            if allow_child_signout:
                signed_out = sign_out_child_with_approval()
            block_reason = child_session_block_reason()
            if block_reason:
                raise RuntimeError('Child session still running: ' + block_reason)
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
    if signed_out:
        print('ParentPilot signed out the child for this update.', flush=True)
    print('Sign the child back in when ready to use the updated desktop.', flush=True)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Administrator authentication is required.')
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in ('stable', 'preview'):
        raise ValueError(
            'Usage: update_install.py stable|preview RELEASE_TAG [--sign-out-child]')
    if len(sys.argv) == 4 and sys.argv[3] != '--sign-out-child':
        raise ValueError('Unsupported update option.')
    channel, tag = sys.argv[1:3]
    if not TAG.fullmatch(tag):
        raise ValueError('Invalid release tag.')
    install(channel, tag, allow_child_signout=(len(sys.argv) == 4))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('PARENTPILOT UPDATE STOPPED: ' + str(error), file=sys.stderr)
        sys.exit(1)
