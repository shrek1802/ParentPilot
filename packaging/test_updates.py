#!/usr/bin/env python3
"""Offline tests for ParentPilot update metadata, trust policy and data backups."""
import hashlib
from pathlib import Path
import tempfile
import types
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'parentpilot'))
import update_release as rel
import update_install as upd


def sample(tag='v0.5.0-preview7', version='0.5.0~preview7',
           prerelease=True, origin='https://github.com/shrek1802/ParentPilot'):
    name = 'parentpilot_' + version + '_all.deb'
    digest = 'sha256:' + 'a' * 64
    return {
        'tag_name': tag, 'prerelease': prerelease, 'draft': False,
        'body': 'Improved timer and security fixes.',
        'assets': [{
            'name': name, 'digest': digest, 'size': 829120,
            'browser_download_url': origin + '/releases/download/' + tag + '/' + name,
        }]
    }


old = '0.5.0~preview6'
preview = rel.find_update([sample()], old, 'preview')
assert preview and preview['version'] == '0.5.0~preview7'
assert rel.find_update([sample()], old, 'stable') is None
assert rel.newer_version('0.5.0~preview7', old)
assert not rel.newer_version(old, '0.5.0~preview7')
# GitHub sanitises '~' to '.' in published asset filenames. The internal
# Debian version must still be read as 0.5.0~preview7, not 0.5.0.preview7.
normalised = sample()
normalised['assets'][0]['name'] = 'parentpilot_0.5.0.preview7_all.deb'
normalised['assets'][0]['browser_download_url'] = (
    'https://github.com/shrek1802/ParentPilot/releases/download/'
    'v0.5.0-preview7/parentpilot_0.5.0.preview7_all.deb'
)
normalised_found = rel.find_update([normalised], old, 'preview')
assert normalised_found is not None
assert normalised_found['version'] == '0.5.0~preview7'
assert normalised_found['filename'] == 'parentpilot_0.5.0.preview7_all.deb'
mismatched = sample()
mismatched['assets'][0]['name'] = 'parentpilot_0.5.0.preview8_all.deb'
mismatched['assets'][0]['browser_download_url'] = (
    'https://github.com/shrek1802/ParentPilot/releases/download/'
    'v0.5.0-preview7/parentpilot_0.5.0.preview8_all.deb'
)
assert rel.find_update([mismatched], old, 'preview') is None

assert rel.find_update([sample()], '0.5.0~preview7', 'preview') is None
assert rel.find_update([sample(tag='v0.5.0', version='0.5.0',
                               prerelease=False)], old, 'stable') is not None
for invalid in [
    lambda r: r['assets'][0].update(digest=''),
    lambda r: r['assets'][0].update(digest='sha256:' + 'x' * 64),
    lambda r: r['assets'][0].update(size=9999999999),
    lambda r: r['assets'][0].update(browser_download_url='https://attacker.invalid/steal.deb'),
    lambda r: r.update(draft=True),
    lambda r: r.update(tag_name='bad/../tag'),
    lambda r: r['assets'][0].update(name='../fake.deb'),
]:
    entry = sample()
    invalid(entry)
    assert rel.find_update([entry], old, 'preview') is None, entry
assert rel.find_update([], old) is None
try:
    rel.find_update({}, old)
    raise AssertionError('Invalid metadata must be rejected')
except ValueError:
    pass
print('PASS: stable/preview selection, Debian version comparison, SHA metadata and release origin')


with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    upd.CFG = root / 'config'
    upd.DATA = root / 'data'
    upd.TARGET = root / 'deployed'
    upd.PACKAGE = root / 'package'
    upd.UNIT = root / 'service.unit'
    upd.MARKER = upd.CFG / '.parentpilot-deb-managed'
    upd.BACKUPS = root / 'backups'
    upd.CFG.mkdir()
    upd.DATA.mkdir()
    upd.TARGET.mkdir()
    upd.PACKAGE.mkdir()
    (upd.CFG / 'config.json').write_text('{"child":"testchild","password":"protected"}')
    (upd.CFG / 'desktop-token').write_text('secret-token')
    (upd.CFG / 'server.key').write_text('private-certificate-key')
    (upd.DATA / 'state.json').write_text('{"allowance_seconds":1800}')
    (upd.DATA / 'saved-screens').mkdir()
    (upd.DATA / 'saved-screens' / 'proof.jpg').write_bytes(b'\xff\xd8' + b'data')
    (upd.TARGET / 'control_server.py').write_text('old service')
    (upd.TARGET / 'old-extra-file.txt').write_text('keep')
    (upd.PACKAGE / 'control_server.py').write_text('new service')
    (upd.PACKAGE / 'parentpilot_screen_parent.js').write_text('new frontend')
    upd.UNIT.write_text('[Service]\nExecStart=old\n')
    assert not upd.configured_for_updates()
    upd.MARKER.write_text('ParentPilot-DEB-managed-v1')
    assert upd.configured_for_updates()
    saved_version = upd.installed_version
    saved_command = upd.cmd
    try:
        upd.installed_version = lambda: '0.5.0~preview6'
        backup = upd.save_snapshot()
        assert (backup / 'configuration' / 'server.key').read_text() == 'private-certificate-key'
        assert (backup / 'data' / 'saved-screens' / 'proof.jpg').is_file()
        assert (backup / 'version.txt').read_text().strip() == '0.5.0~preview6'
        assert oct(upd.BACKUPS.stat().st_mode & 0o777) == '0o700'
        upd.deploy_program_files()
        assert (upd.TARGET / 'control_server.py').read_text() == 'new service'
        assert (upd.TARGET / 'old-extra-file.txt').read_text() == 'keep'
        (upd.DATA / 'state.json').write_text('corrupted')
        (upd.CFG / 'config.json').write_text('{}')
        upd.cmd = lambda *args, **kwargs: types.SimpleNamespace(stdout='')
        upd.restore_snapshot(backup)
        assert (upd.CFG / 'config.json').read_text() == '{"child":"testchild","password":"protected"}'
        assert (upd.DATA / 'state.json').read_text() == '{"allowance_seconds":1800}'
        assert (upd.DATA / 'saved-screens' / 'proof.jpg').exists()
        assert (upd.TARGET / 'control_server.py').read_text() == 'old service'
    finally:
        upd.cmd = saved_command
        upd.installed_version = saved_version
print('PASS: fresh-install marker, private PIN/token/screen backups, deployed copy and recovery')

print('PASS: ParentPilot update system security regression tests')
