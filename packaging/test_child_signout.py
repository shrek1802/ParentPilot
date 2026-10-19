#!/usr/bin/env python3
"""Safe headless tests: approved child sign-out, no system logouts performed."""
import inspect
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / 'parentpilot'))
import update_install as upd

assert not upd.signed_in_child_session(None)
assert not upd.signed_in_child_session('Cannot safely confirm that the child is logged out')
assert upd.signed_in_child_session('Child Linux session c1 is still online')
assert upd.signed_in_child_session('Child session c1 is still shutting down')
assert not upd.signed_in_child_session('Child admin session c2 is active')

# A privileged updater must receive a real adult approval via PolicyKit,
# not merely an arbitrary command or an invocation from the child itself.
with patch.dict(os.environ, {}, clear=True):
    try:
        upd.verify_adult_approved_signout(2001)
        raise AssertionError('Silent or manual root child logout allowed')
    except RuntimeError:
        pass
with patch.dict(os.environ, {'PKEXEC_UID': '2001'}):
    try:
        upd.verify_adult_approved_signout(2001)
        raise AssertionError('Child could approve own logout')
    except RuntimeError:
        pass
with patch.dict(os.environ, {'PKEXEC_UID': '0'}):
    try:
        upd.verify_adult_approved_signout(2001)
        raise AssertionError('Root accepted as GUI-originating adult')
    except RuntimeError:
        pass
with patch.dict(os.environ, {'PKEXEC_UID': '1000'}), \
     patch.object(upd.pwd, 'getpwuid',
                  return_value=SimpleNamespace(pw_name='parentuser', pw_gid=1000)), \
     patch.object(upd.os, 'getgrouplist', return_value=[1000, 27]), \
     patch.object(upd.grp, 'getgrgid',
                  side_effect=lambda gid: SimpleNamespace(gr_name='sudo' if gid == 27 else 'parent')):
    assert upd.verify_adult_approved_signout(2001) == 'parentuser'
print('PASS: only authenticated administrator, never child/system user, may approve logout')

with tempfile.TemporaryDirectory() as tmp:
    cfg = Path(tmp)
    (cfg / 'config.json').write_text('{"child":"testchild"}')
    with patch.object(upd, 'CFG', cfg), \
         patch.object(upd, 'configured_for_updates', return_value=True), \
         patch.object(upd.pwd, 'getpwnam',
                      return_value=SimpleNamespace(pw_uid=2001, pw_gid=2001)):
        # No logout is attempted if no child session needs closing.
        with patch.object(upd, 'verify_adult_approved_signout', return_value='parentuser'), \
             patch.object(upd, 'child_session_block_reason', return_value=None), \
             patch.object(upd.subprocess, 'run') as run:
            assert upd.sign_out_child_with_approval() is False
            run.assert_not_called()

        # A normal active child session is ended using logind, never the parent.
        with patch.object(upd, 'verify_adult_approved_signout', return_value='parentuser'), \
             patch.object(upd, 'child_session_block_reason',
                          side_effect=['Child Linux session c1 is still online', None]), \
             patch.object(upd, 'wait_for_child_logout', return_value=None), \
             patch.object(upd.subprocess, 'run',
                          return_value=SimpleNamespace(returncode=0)) as run:
            assert upd.sign_out_child_with_approval() is True
            assert run.call_count == 1
            assert run.call_args.args[0] == ['loginctl', 'terminate-user', 'testchild']

        # Any ambiguous or inconsistent session data must never invoke logind.
        with patch.object(upd, 'verify_adult_approved_signout', return_value='parentuser'), \
             patch.object(upd, 'child_session_block_reason',
                          return_value='Cannot safely confirm that the child is logged out'), \
             patch.object(upd.subprocess, 'run') as run:
            try:
                upd.sign_out_child_with_approval()
                raise AssertionError('Ambiguous child logind status was accepted')
            except RuntimeError:
                pass
            run.assert_not_called()
print('PASS: no child session no-op, active child-only logout, ambiguous logind fails closed')

# Check the ordering explicitly: never log out a child until archive verification
# and snapshot backup are complete (to avoid needless lost work on failures).
source = inspect.getsource(upd.install)
assert source.index('download_verified(release, directory)') < source.index('save_snapshot()')
assert source.index('save_snapshot()') < source.index('sign_out_child_with_approval()')
assert source.index('sign_out_child_with_approval()') < source.index("cmd('apt-get'")
assert '--sign-out-child' in inspect.getsource(upd.main)
print('PASS: verified package -> private backup -> optional sign-out -> APT')
