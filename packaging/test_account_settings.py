#!/usr/bin/python3
"""Test existing-account credential edits without changing real system accounts."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent/'parentpilot'))
import account_settings as sec

assert sec.check_new_pin('517482')=='517482'
for value in ('123456','000000','111111','654321','12345','abcdef','1234567'):
    try:
        sec.check_new_pin(value)
        raise AssertionError('Accepted bad PIN')
    except ValueError:
        pass
assert sec.check_child_password('not-easy-739') == 'not-easy-739'
for pw in ('tiny','a:bccdefg','a\nb','bad\0value'):
    try:
        sec.check_child_password(pw)
        raise AssertionError('Accepted bad password')
    except ValueError:
        pass

old=sec.hash_pin('638592')
assert sec.verify_pin('638592',old)
assert not sec.verify_pin('000000',old)
assert not sec.verify_pin('638593',old)
assert not sec.verify_pin('',old)
assert not sec.verify_pin('123456',{'salt':'broken','hash':'empty'})
cfg={
    'child':'testchild',
    'password':old,
    'display_name':'Test child',
    'screen_view_enabled':True,
    'keep_other_settings':{'allowance_seconds':3600},
}
stored=[dict(cfg)]
commands=[]
def write(new,meta):
    stored[0]=json.loads(json.dumps(new))
def reload_good(runner):
    commands.append('reload')
with patch.object(sec,'existing_configuration',side_effect=lambda:(dict(stored[0]),None)),\
     patch.object(sec,'write_config',side_effect=write),\
     patch.object(sec,'reload_service',side_effect=reload_good):
    assert 'PIN updated' in sec.apply_parent_pin('638592','517482')
    assert sec.verify_pin('517482',stored[0]['password'])
    assert stored[0]['keep_other_settings'] == cfg['keep_other_settings']
    assert stored[0]['screen_view_enabled'] is True
    assert commands == ['reload']
    oldnew=json.loads(json.dumps(stored[0]))
    try:
        sec.apply_parent_pin('638592','271634')
        raise AssertionError('Wrong old PIN accepted')
    except ValueError:
        pass
    assert stored[0]==oldnew
    with patch.object(sec,'reload_service',side_effect=[RuntimeError('failed'),None]):
        try:
            sec.apply_parent_pin('517482','271634')
            raise AssertionError('Accepted service restart failure')
        except RuntimeError:
            pass
    assert stored[0]==oldnew, 'PIN not rolled back on restart failure'

called=[]
def runner(args,**opts):
    called.append((args,opts))
    return SimpleNamespace(returncode=0)
with patch.object(sec,'existing_configuration',return_value=(cfg,None)),\
     patch.object(sec.pwd,'getpwnam',return_value=SimpleNamespace(pw_name='testchild',pw_uid=1002,pw_gid=1002)):
    assert 'password updated' in sec.apply_child_password('other-long-password',runner=runner)
assert called[0][0] == ['/usr/sbin/chpasswd']
assert called[0][1]['input'] == 'testchild:other-long-password\n'
assert 'other-long-password' not in ' '.join(called[0][0])
with patch.object(sec,'existing_configuration',return_value=(cfg,None)),\
     patch.object(sec.pwd,'getpwnam',return_value=SimpleNamespace(pw_name='testchild',pw_uid=0,pw_gid=0)):
    try:
        sec.apply_child_password('other-long-password',runner=runner)
        raise AssertionError('Updated privileged account')
    except RuntimeError:
        pass
assert len(called)==1
for malformed in ({'action':'pin','new':'123456'},
                  {'action':'child_password','new':'valid-pass','child':'root'},
                  {'action':'restore','new':'secret'}):
    try:
        sec.dispatch(malformed)
        raise AssertionError('Accepted unexpected security request')
    except (ValueError,RuntimeError):
        pass
print('PASS: existing parent PIN hashing and rollback, Linux child password changes, allowlisted requests; no real accounts modified')
