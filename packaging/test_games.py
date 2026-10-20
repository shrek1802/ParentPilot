#!/usr/bin/python3
"""Offline regressions for optional ParentPilot games, no APT changes or users."""

from pathlib import Path
import importlib.util
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'parentpilot'))
import games_catalog as catalog
import games_install as installer

expected = {
    'gcompris': 'gcompris-qt',
    'tuxmath': 'tuxmath',
    'tuxtype': 'tuxtype',
    'tuxpaint': 'tuxpaint',
    'pingus': 'pingus',
    'supertux': 'supertux',
    'frozenbubble': 'frozen-bubble',
    'sudoku': 'gnome-sudoku',
}
assert dict((key, package) for key, _title, _category, _desc, package
            in catalog.GAMES) == expected
assert catalog.validate_game_ids([]) == ()
assert catalog.validate_game_ids(['tuxtype', 'supertux']) == ('tuxtype', 'supertux')
assert catalog.package_names(['tuxtype', 'supertux']) == ('tuxtype', 'supertux')
assert catalog.MEDIA_PLAYERS[0][4] == 'kodi'
assert catalog.validate_media_ids([]) == ()
assert catalog.validate_media_ids(['kodi']) == ('kodi',)
for invalid_media in ('kodi', None, True, ['kodi', 'kodi'], ['vlc'], ['--force-yes'], ['kodi;curl example.invalid']):
    try:
        catalog.validate_media_ids(invalid_media)
        raise AssertionError('Accepted invalid media selection: ' + repr(invalid_media))
    except ValueError:
        pass
for invalid in (
    'tuxmath', None, {'tuxmath': True}, ['not-a-package'],
    ['tuxmath', 'tuxmath'], ['supertux;rm -rf /'], ['--force-yes'],
    [[1]], [123], [True], list(expected) + ['x'],
):
    try:
        catalog.validate_game_ids(invalid)
        raise AssertionError('Accepted invalid selected games: ' + repr(invalid))
    except ValueError:
        pass

setup_path = ROOT / 'parentpilot/setup_root.py'
spec = importlib.util.spec_from_file_location('parentpilot_setup_for_games', setup_path)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
form = {
    'child_name': 'Tester', 'child_user': 'kidtest', 'child_password': 'abcdef',
    'parent_pin': '827391', 'youtube': 'kids', 'netflix': True,
    'autologin': False, 'family_filter': True, 'screen_view': False,
}
assert setup.validate(form)[1] == 'kidtest' # Backward compatibility, no games field.
assert setup.validate({**form, 'games': ['gcompris', 'supertux']})[1] == 'kidtest'
assert setup.validate({**form, 'kodi': True})[1] == 'kidtest'
for invalid_flag in ('true', 1, ['kodi'], None):
    try:
        setup.validate({**form, 'kodi': invalid_flag})
        raise AssertionError('Accepted invalid Kodi flag')
    except ValueError:
        pass
for invalid in (['invalid'], ['tuxpaint', 'tuxpaint'], False, 'supertux', None):
    try:
        setup.validate({**form, 'games': invalid})
        raise AssertionError('Unsafe setup games input accepted: ' + repr(invalid))
    except ValueError:
        pass

installed_packages = {'tuxmath'}
commands = []


def fake_runner(argv, **kwargs):
    commands.append(argv)
    if argv[0] == 'dpkg-query':
        pkg = argv[-1]
        if pkg in installed_packages:
            return SimpleNamespace(returncode=0, stdout='install ok installed')
        return SimpleNamespace(returncode=1, stdout='')
    if argv[0] == '/usr/bin/apt-get':
        assert argv[:4] == [
            '/usr/bin/apt-get', 'install', '-y', '--no-install-recommends',
        ]
        assert argv[-1] in (*expected.values(), 'kodi')
        assert kwargs.get('env', {}).get('DEBIAN_FRONTEND') == 'noninteractive'
        if argv[-1] == 'frozen-bubble':
            return SimpleNamespace(returncode=100, stderr='Package unavailable', stdout='')
        return SimpleNamespace(returncode=0, stdout='Installed', stderr='')
    raise AssertionError('Unexpected command: ' + repr(argv))


done, existing, failed = installer.install_selected(
    ['tuxmath', 'supertux', 'frozenbubble'], runner=fake_runner
)
assert done == ['SuperTux']
assert existing == ['Tux Maths']
assert failed == [('Frozen Bubble', 'Package unavailable')]
assert [argv[-1] for argv in commands if argv[0] == '/usr/bin/apt-get'] == [
    'supertux', 'frozen-bubble'
]
assert all('remove' not in cmd and 'purge' not in cmd for cmd in commands)
assert installer.install_selected([], runner=fake_runner) == ([], [], [])
assert installer.install_selected_media(['kodi'], runner=fake_runner) == (['Kodi Media Centre'], [], [])
assert [argv[-1] for argv in commands if argv[0] == '/usr/bin/apt-get'][-1] == 'kodi'
# The adult installer emits genuine per-app progress immediately, including
# a terminal event for every selected item, even when APT cannot install it.
import contextlib
import io
import json
captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    result = installer.install_selected(['supertux', 'frozenbubble'], runner=fake_runner, progress=True)
assert result[0] == ['SuperTux']
events = [json.loads(line[len(installer.EVENT_PREFIX):])
          for line in captured.getvalue().splitlines()
          if line.startswith(installer.EVENT_PREFIX)]
assert [(e['event'], e['id']) for e in events] == [
    ('checking', 'supertux'), ('installing', 'supertux'), ('installed', 'supertux'),
    ('checking', 'frozenbubble'), ('installing', 'frozenbubble'),
    ('failed', 'frozenbubble')]
assert set(events[0]) == {'event', 'id', 'name'}

# Root backend authorisation checks use the PolicyKit caller, never an
# arbitrary request as coming from the child or a random shell.
with patch.object(installer.pwd, 'getpwuid',
                  return_value=SimpleNamespace(pw_name='adult', pw_gid=1000)), \
     patch.object(installer.os, 'getgrouplist', return_value=[1000, 27]), \
     patch.object(installer.grp, 'getgrgid',
                  side_effect=lambda gid: SimpleNamespace(
                      gr_name='sudo' if gid == 27 else 'adult')):
    assert installer.validate_adult_origin({'PKEXEC_UID': '1000'}) == 'adult'

for env in ({}, {'PKEXEC_UID': 'root'}, {'PKEXEC_UID': '0'}):
    try:
        installer.validate_adult_origin(env)
        raise AssertionError('Accepted unauthenticated/invalid caller ' + repr(env))
    except RuntimeError:
        pass

with patch.object(installer.pwd, 'getpwuid',
                  return_value=SimpleNamespace(pw_name='child', pw_gid=1002)), \
     patch.object(installer.os, 'getgrouplist', return_value=[1002]), \
     patch.object(installer.grp, 'getgrgid',
                  return_value=SimpleNamespace(gr_name='child')):
    try:
        installer.validate_adult_origin({'PKEXEC_UID': '1002'})
        raise AssertionError('Child account passed administrator check')
    except RuntimeError:
        pass

# Check the two screens reference the exact same game catalogue and both
# use distinct administrator-controlled installation workflows.
wizard_text = (ROOT / 'parentpilot/wizard.py').read_text()
manager_text = (ROOT / 'parentpilot/games_gui.py').read_text()
assert 'from games_catalog import GAMES' in wizard_text
assert 'for game_id, title, category, description, package in GAMES' in wizard_text
assert "data['games'] = " in wizard_text
assert "'--from-manager'" in manager_text
assert 'from games_catalog import GAMES' in manager_text
assert 'MEDIA PLAYERS' in manager_text
assert "'kodi':tk.BooleanVar(value=False)" in wizard_text
assert "'media': media_ids" in manager_text

print('PASS: 8 educational/2D games + optional Kodi, only selected APT packages, setup validation, '
      'partial failure, no removals, and adult-only installation')
