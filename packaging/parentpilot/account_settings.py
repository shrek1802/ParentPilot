#!/usr/bin/python3
"""Adult-approved changes to the EXISTING ParentPilot PIN or child Linux password.

Only invoked via PolicyKit by the adult Control Centre. Nothing in here
creates a user, alters screen-time allowances, PIN retries, or saved pictures.
Credential material arrives via a bounded stdin pipe, never command arguments
or diagnostic logs.
"""
import base64
import hashlib
import hmac
import json
import os
import pwd
import re
import secrets
import subprocess
import sys

from games_install import validate_adult_origin
from screen_settings import existing_configuration, write_config, reload_service

PIN_RE = re.compile(r'^[0-9]{6}$', flags=re.ASCII)
CHILD_RE = re.compile(r'^[a-z][a-z0-9_-]{0,30}$', flags=re.ASCII)
BANNED_PINS = frozenset(('000000', '111111', '123456', '654321'))


def check_new_pin(value):
    if (type(value) is not str or not PIN_RE.fullmatch(value) or value in BANNED_PINS
            or len(set(value)) == 1):
        raise ValueError('Choose a less obvious six-digit PIN.')
    return value


def verify_pin(value, hashed):
    try:
        salt=base64.b64decode(hashed['salt'],validate=True)
        expected=base64.b64decode(hashed['hash'],validate=True)
        if len(salt)<8 or len(expected)!=32:
            return False
        supplied=hashlib.pbkdf2_hmac('sha256',value.encode('utf-8'),salt,320000)
        return hmac.compare_digest(supplied,expected)
    except (KeyError,ValueError,TypeError,OverflowError):
        return False


def hash_pin(value):
    salt=secrets.token_bytes(16)
    hashed=hashlib.pbkdf2_hmac('sha256',value.encode('utf-8'),salt,320000)
    return {'salt':base64.b64encode(salt).decode('ascii'),
            'hash':base64.b64encode(hashed).decode('ascii')}


def check_child_password(password):
    if (type(password) is not str or not 8<=len(password)<=128 or
            ':' in password or any(c in password for c in ('\r','\n','\0'))):
        raise ValueError('Child password must be 8–128 characters, without colons or line breaks.')
    return password


def apply_parent_pin(previous, fresh, runner=subprocess.run):
    """Verify current PIN even after a separate Linux admin password prompt."""
    config, meta=existing_configuration()
    if (type(previous) is not str or not PIN_RE.fullmatch(previous) or
            not verify_pin(previous, config['password'])):
        raise ValueError('Current parent PIN is incorrect.')
    check_new_pin(fresh)
    if previous==fresh:
        raise ValueError('Choose a different parent PIN.')
    new=dict(config)
    new['password']=hash_pin(fresh)
    write_config(new,meta)
    try:
        # Restart discards old authenticated parent web sessions and picks up
        # the new PIN; it does not reset the existing allowance.
        reload_service(runner)
    except Exception:
        write_config(config,meta)
        try:
            reload_service(runner)
        except Exception:
            pass
        raise RuntimeError('ParentPilot service could not apply the new PIN. Original PIN restored.')
    return 'Parent PIN updated. Sign in to the parent app again with the new PIN.'


def apply_child_password(password, runner=subprocess.run):
    check_child_password(password)
    config,_=existing_configuration()
    name=config['child']
    if not CHILD_RE.fullmatch(name) or name in ('root','maxfamily','nobody'):
        raise RuntimeError('Existing configured child account is invalid.')
    user=pwd.getpwnam(name)
    if user.pw_uid==0 or user.pw_name!=name:
        raise RuntimeError('Refusing to change a privileged account.')
    # Never pass a password through command-line args; no child logout and
    # no user deletion. chpasswd updates the existing Linux login credential.
    result=runner(['/usr/sbin/chpasswd'],input=name+':'+password+'\n',
                  capture_output=True,text=True,timeout=25,check=False)
    if result.returncode!=0:
        raise RuntimeError('The child password could not be changed. Try again from the adult account.')
    return 'Child login password updated. Use it at the next child sign-in.'


def dispatch(request, runner=subprocess.run):
    if not isinstance(request,dict) or request.get('action') not in ('pin','child_password'):
        raise ValueError('Invalid security action.')
    if request['action']=='pin':
        if set(request)!= {'action','current','new'}:
            raise ValueError('Invalid parent PIN request.')
        return apply_parent_pin(request['current'],request['new'],runner=runner)
    if set(request)!= {'action','new'}:
        raise ValueError('Invalid child password request.')
    return apply_child_password(request['new'],runner=runner)


def main():
    if os.geteuid()!=0 or sys.argv[1:]!=['--from-centre']:
        raise RuntimeError('Start this operation in the adult ParentPilot Control Centre.')
    validate_adult_origin()
    raw=sys.stdin.read(1025)
    if len(raw)>1024:
        raise ValueError('Security request is too large.')
    result=dispatch(json.loads(raw))
    print('SECURITY_RESULT:'+result,flush=True)


if __name__=='__main__':
    try:
        main()
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,
            subprocess.SubprocessError,subprocess.TimeoutExpired) as error:
        # Never print the caller's request or the actual supplied credentials.
        print('ParentPilot Security: '+str(error),file=sys.stderr)
        sys.exit(1)
