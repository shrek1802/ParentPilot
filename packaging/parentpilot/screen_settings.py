#!/usr/bin/python3
"""Privileged adult-only ParentPilot screen-picture permission setting.

Changes exactly one boolean in the existing managed configuration. No account,
PIN, screenshot, token, timer, or screen-time value is reset. Installed only
with the ParentPilot DEB; called by pkexec after adult approval.
"""
import grp
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tempfile

CFG_DIR = Path('/etc/max-family-control')
CONFIG = CFG_DIR / 'config.json'
MARKER = CFG_DIR / '.parentpilot-deb-managed'
SERVICE = 'max-family-control.service'


def authorised_adult(env=None):
    if os.geteuid() != 0:
        raise RuntimeError('Administrator authentication is required.')
    caller = (os.environ if env is None else env).get('PKEXEC_UID', '')
    if not caller.isascii() or not caller.isdecimal() or int(caller) == 0:
        raise RuntimeError('Open ParentPilot Screen Pictures from the adult Applications menu.')
    adult = pwd.getpwuid(int(caller))
    names = set()
    for group_id in os.getgrouplist(adult.pw_name, adult.pw_gid):
        try:
            names.add(grp.getgrgid(group_id).gr_name)
        except KeyError:
            pass
    if not names.intersection({'sudo', 'admin', 'wheel'}):
        raise RuntimeError('A Linux administrator must approve this change.')
    return adult.pw_name


def existing_configuration():
    if (CFG_DIR.is_symlink() or CONFIG.is_symlink() or
            MARKER.is_symlink() or not MARKER.is_file() or
            not CONFIG.is_file()):
        raise RuntimeError('This is not a managed ParentPilot installation.')
    metadata = CONFIG.stat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or
            metadata.st_mode & 0o022):
        raise RuntimeError('ParentPilot configuration permissions are unsafe.')
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or type(data.get('screen_view_enabled')) is not bool
            or not isinstance(data.get('child'), str)
            or not isinstance(data.get('password'), dict)):
        raise RuntimeError('ParentPilot configuration was not recognised.')
    return data, metadata


def write_config(data, previous_metadata):
    # Atomic replacement on the same filesystem, preserving the original
    # root:maxfamily group so the running service can still read its config.
    fd, pathname = tempfile.mkstemp(prefix='.parentpilot-screen-', dir=str(CFG_DIR))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fchown(handle.fileno(), previous_metadata.st_uid, previous_metadata.st_gid)
            os.fchmod(handle.fileno(), stat.S_IMODE(previous_metadata.st_mode))
            os.fsync(handle.fileno())
        os.replace(pathname, CONFIG)
    finally:
        Path(pathname).unlink(missing_ok=True)


def reload_service(runner=subprocess.run):
    for args in (
        ['systemctl', 'restart', SERVICE],
        ['systemctl', 'is-active', '--quiet', SERVICE],
    ):
        result = runner(args, capture_output=True, text=True, timeout=35, check=False)
        if result.returncode != 0:
            raise RuntimeError('ParentPilot control service could not restart successfully.')


def change_screen_pictures(enable, runner=subprocess.run):
    if type(enable) is not bool:
        raise ValueError('A true or false permission is required.')
    previous, metadata = existing_configuration()
    if previous['screen_view_enabled'] == enable:
        return enable  # Do not restart a working service for no-op.
    new_config = dict(previous)
    new_config['screen_view_enabled'] = enable
    write_config(new_config, metadata)
    try:
        # Existing service reads the permission at startup. Restart only the
        # ParentPilot service; neither Linux account nor the desktop is changed.
        reload_service(runner)
    except Exception:
        # Never leave a partially applied sensitive permission on disk.
        write_config(previous, metadata)
        try:
            reload_service(runner)
        except Exception:
            pass
        raise
    return enable


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in (
        '--status', '--enable', '--disable'):
        raise RuntimeError('Unsupported ParentPilot Screen Pictures operation.')
    authorised_adult()
    if sys.argv[1] == '--status':
        data, _ = existing_configuration()
        enabled = data['screen_view_enabled']
    else:
        enabled = change_screen_pictures(sys.argv[1] == '--enable')
    print('SCREEN_PICTURES:' + ('enabled' if enabled else 'disabled'), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, TypeError,
            subprocess.TimeoutExpired, subprocess.SubprocessError) as error:
        print('ParentPilot Screen Pictures: ' + str(error), file=sys.stderr)
        sys.exit(1)
