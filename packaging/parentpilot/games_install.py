#!/usr/bin/python3
"""Install parent's chosen APT games. Never uninstall or modify child settings.

Run by the first-time root setup wizard AFTER the controller is provisioned,
or by the adult-only Games & Learning GUI using PolicyKit authentication.
"""
import grp
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

from games_catalog import BY_ID, BY_MEDIA_ID, validate_game_ids, validate_media_ids

MARKER = Path('/etc/max-family-control/.parentpilot-deb-managed')
CFG = Path('/etc/max-family-control/config.json')


def parentpilot_configured():
    return MARKER.is_file() and CFG.is_file()


def validate_adult_origin(env=None):
    """A separately authenticated PolicyKit request must come from an admin."""
    env = env if env is not None else os.environ
    user_id = env.get('PKEXEC_UID', '')
    if not user_id.isdigit():
        raise RuntimeError('Launch Games & Learning from the adult desktop to authorise installing games.')
    uid = int(user_id)
    if uid == 0:
        raise RuntimeError('Run the games manager as a normal adult, not root.')
    user = pwd.getpwuid(uid)
    group_ids = os.getgrouplist(user.pw_name, user.pw_gid)
    names = set()
    for gid in group_ids:
        try:
            names.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            pass
    if not names.intersection({'sudo', 'admin', 'wheel'}):
        raise RuntimeError('An adult Linux administrator must approve game installation.')
    return user.pw_name


def is_installed(package, runner=subprocess.run):
    result = runner(['dpkg-query', '--show', '--showformat=' + '$' + '{Status}', package],
                    capture_output=True, text=True, timeout=10, check=False)
    return result.returncode == 0 and result.stdout.strip() == 'install ok installed'


def _install_approved(selected, catalogue, runner):
    """Only allowlisted APT packages; no repo additions, uninstall or add-ons."""
    installed, existing, failed = [], [], []
    for item_id in selected:
        display = catalogue[item_id][1]
        package = catalogue[item_id][4]
        print('Checking ' + display + '…', flush=True)
        try:
            if is_installed(package, runner=runner):
                existing.append(display)
                print('Already installed: ' + display, flush=True)
                continue
            # APT's allowlisted package selection cannot be turned into a
            # shell command or a user-controlled package list.
            result = runner([
                '/usr/bin/apt-get', 'install', '-y', '--no-install-recommends',
                package,
            ], capture_output=True, text=True, timeout=360, check=False,
               env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
            if result.returncode != 0:
                problem = (result.stderr or result.stdout or 'APT installation failed').strip()
                failed.append((display, problem[-550:]))
                print('Could not install ' + display + ': ' + problem[-550:], flush=True)
            else:
                installed.append(display)
                print('Installed: ' + display, flush=True)
        except (OSError, subprocess.TimeoutExpired) as exc:
            failed.append((display, str(exc)))
            print('Could not install ' + display + ': ' + str(exc), flush=True)
    return installed, existing, failed


def install_selected(game_ids, runner=subprocess.run):
    """Install only parent's selected, allowlisted educational games."""
    return _install_approved(validate_game_ids(list(game_ids)), BY_ID, runner)


def install_selected_media(media_ids, runner=subprocess.run):
    """Install only the selected official distribution media-player package."""
    return _install_approved(validate_media_ids(list(media_ids)), BY_MEDIA_ID, runner)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Game installation requires administrator permission.')
    if sys.argv[1:] != ['--from-manager']:
        raise ValueError('Launch ParentPilot Games & Learning from the adult desktop.')
    validate_adult_origin()
    if not parentpilot_configured():
        raise RuntimeError('Complete the ParentPilot family setup first.')
    payload = sys.stdin.read(2049)
    if len(payload) > 2048:
        raise ValueError('Game selection is too large.')
    request = json.loads(payload)
    if not isinstance(request, dict) or set(request) not in ({'games'}, {'games', 'media'}):
        raise ValueError('Invalid app installation request.')
    selection = validate_game_ids(request['games'])
    media = validate_media_ids(request.get('media', []))
    if not selection and not media:
        print('Nothing selected. Nothing changed.')
        return
    installed, existing, failed = install_selected(selection)
    media_installed, media_existing, media_failed = install_selected_media(media)
    print('Finished. New apps: ' + str(len(installed) + len(media_installed)) +
          ' · Already present: ' + str(len(existing) + len(media_existing)) +
          ' · Unavailable: ' + str(len(failed) + len(media_failed)), flush=True)
    if failed or media_failed:
        raise RuntimeError('Some selected apps could not be installed. Check the message above. '
                           'Other apps remain available. Confirm your internet '
                           'connection and APT repositories, then try again.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError,
            OSError, subprocess.CalledProcessError) as exc:
        print('PARENTPILOT GAMES STOPPED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
