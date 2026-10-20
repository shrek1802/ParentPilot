#!/usr/bin/python3
"""Screen-picture privacy regression tests (no real users/services are changed)."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))
import screen_settings as screen

with tempfile.TemporaryDirectory() as tmp:
    folder = Path(tmp) / 'private'
    folder.mkdir()
    file = folder / 'config.json'
    marker = folder / '.parentpilot-deb-managed'
    marker.write_text('ParentPilot-DEB-managed-v1\n')
    cfg = {
        'child': 'testchild', 'password': {'salt': 'private', 'hash': 'secret'},
        'display_name': 'Test child', 'screen_view_enabled': False,
        'other_config': {'keep': 'unchanged'}
    }
    file.write_text(json.dumps(cfg))
    file.chmod(0o640)
    metadata = file.stat()
    with patch.object(screen, 'CFG_DIR', folder), patch.object(screen, 'CONFIG', file), \
         patch.object(screen, 'MARKER', marker), \
         patch.object(screen, 'existing_configuration',
                      side_effect=lambda: (json.loads(file.read_text()), metadata)), \
         patch.object(screen.os, 'fchown'):
        commands = []
        def runner(args, **kwargs):
            commands.append(args)
            return SimpleNamespace(returncode=0)
        assert screen.change_screen_pictures(True, runner=runner) is True
        enabled = json.loads(file.read_text())
        assert enabled == {**cfg, 'screen_view_enabled': True}, 'Changed other settings'
        assert commands == [
            ['systemctl', 'restart', 'max-family-control.service'],
            ['systemctl', 'is-active', '--quiet', 'max-family-control.service']
        ]
        assert file.stat().st_mode & 0o777 == 0o640
        commands.clear()
        assert screen.change_screen_pictures(True, runner=runner) is True
        assert not commands, 'No-op must not restart service'
        assert screen.change_screen_pictures(False, runner=runner) is False
        assert json.loads(file.read_text()) == cfg
        # A failed service restart must revert the privacy change.
        first = [True]
        def failing(args, **kwargs):
            if first[0]:
                first[0] = False
                return SimpleNamespace(returncode=1)
            return SimpleNamespace(returncode=0)
        try:
            screen.change_screen_pictures(True, runner=failing)
            raise AssertionError('Failed service restart was accepted')
        except RuntimeError:
            pass
        assert json.loads(file.read_text()) == cfg
        try:
            screen.change_screen_pictures('enabled', runner=runner)
            raise AssertionError('Accepted non-bool')
        except ValueError:
            pass

    # ParentPilot's configuration must not be followed through a symlink.
    with patch.object(screen, 'CFG_DIR', folder), patch.object(screen, 'CONFIG', file), \
         patch.object(screen, 'MARKER', marker):
        (folder / 'link').symlink_to(file)
        with patch.object(screen, 'CONFIG', folder / 'link'):
            try:
                screen.existing_configuration()
                raise AssertionError('Followed linked private config')
            except RuntimeError:
                pass

with patch.object(screen.os, 'geteuid', return_value=0), \
     patch.object(screen.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='adult',pw_gid=1000)), \
     patch.object(screen.os, 'getgrouplist', return_value=[1000,27]), \
     patch.object(screen.grp, 'getgrgid', side_effect=lambda g: SimpleNamespace(gr_name='sudo' if g==27 else 'adult')):
    assert screen.authorised_adult({'PKEXEC_UID':'1000'}) == 'adult'
    for token in ('', '0', 'child', '1;rm'):
        try:
            screen.authorised_adult({'PKEXEC_UID':token})
            raise AssertionError('Accepted invalid PolicyKit caller')
        except RuntimeError:
            pass
with patch.object(screen.os, 'geteuid', return_value=1000):
    try:
        screen.authorised_adult({'PKEXEC_UID':'1000'})
        raise AssertionError('Accepted non-privileged backend process')
    except RuntimeError:
        pass
print('PASS: adult-only screen permission toggle, explicit enable/disable, retained settings, safe rollback')
