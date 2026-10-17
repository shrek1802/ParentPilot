#!/usr/bin/env python3
"""No root / no GUI smoke tests for the timer and remote web controls."""
import datetime, http.cookiejar, importlib, json, os, pathlib, ssl, tempfile, threading, subprocess
import urllib.request, urllib.error, urllib.parse
from http.server import ThreadingHTTPServer

with tempfile.TemporaryDirectory() as tmp:
    os.environ['MAXFC_CONFIG_DIR'] = tmp+'/config'
    os.environ['MAXFC_DATA_DIR'] = tmp+'/data'
    import control_server as m
    m.CONFIG_DIR.mkdir(); m.DATA_DIR.mkdir()
    m.atomic_write(m.CONFIG_FILE, {'child':'max','display_name':'Max', 'password':m.hash_password('123456'), 'screen_view_enabled':True})
    m.DESKTOP_TOKEN_FILE.write_text('test-desktop-token-1234567890-test-token-1234567890')
    ctrl=m.Control()
    assert ctrl.snapshot()['allowed'] is False
    assert ctrl.snapshot()['paused'] is True
    ctrl.change('set', 60)
    assert ctrl.snapshot()['remaining_seconds'] == 3600
    ctrl.state['used_seconds'] = 1800
    assert ctrl.snapshot()['remaining_seconds'] == 1800
    ctrl.change('add',30)
    assert ctrl.snapshot()['remaining_seconds'] == 3600
    ctrl.change('pause')
    assert ctrl.snapshot()['allowed'] is False
    ctrl.change('resume')
    assert ctrl.snapshot()['allowed'] is True
    ctrl.change('end')
    assert ctrl.snapshot()['allowed'] is False
    ctrl.change('unlimited')
    assert ctrl.snapshot()['allowed'] is True
    ctrl.change('managed')
    assert ctrl.snapshot()['allowed'] is False
    assert m.verify_password('123456',ctrl.cfg['password'])
    assert not m.verify_password('wrongpass',ctrl.cfg['password'])
    ctrl.change('set', 15)
    m.atomic_write(m.STATE_FILE,ctrl.state)
    again = m.Control()
    assert again.snapshot()['remaining_seconds'] == 900
    assert ctrl.snapshot()['child'] == 'max'
    s=ThreadingHTTPServer(('127.0.0.1',0),m.Handler)
    s.control=ctrl
    cert=tmp+'/server.crt'; key=tmp+'/server.key'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-sha256','-nodes','-days','1','-keyout',key,'-out',cert,'-subj','/CN=localhost'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
    s.socket=tls.wrap_socket(s.socket,server_side=True)
    port=s.server_address[1]
    th=threading.Thread(target=s.serve_forever,daemon=True);th.start()
    jar=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    url=f'https://127.0.0.1:{port}'
    token={'X-MaxFC-Desktop-Token': m.DESKTOP_TOKEN_FILE.read_text()}
    def post(path,**kw):
        body=urllib.parse.urlencode(kw).encode()
        return op.open(urllib.request.Request(url+path,data=body,headers={'Content-Type':'application/x-www-form-urlencoded',**(token if path=='/local-grant' else {})}))
    assert b'Parent sign in' in op.open(url+'/').read()
    try:
        post('/action',action='pause').read()
        raise AssertionError('Unauthenticated action allowed')
    except urllib.error.HTTPError as e: assert e.code==403
    try:
        post('/login',password='badpass').read()
        raise AssertionError('Wrong password accepted')
    except urllib.error.HTTPError as e: assert e.code==403
    post('/login',password='123456').read()
    result=op.open(url+'/').read().decode()
    assert 'ParentPilot' in result
    import re
    csrf=re.search('name="csrf" value="([^"]+)"',result).group(1)
    try:
        post('/action',action='pause',csrf='not-valid').read()
        raise AssertionError('CSRF bypass')
    except urllib.error.HTTPError as e: assert e.code==403
    post('/action',action='pause',csrf=csrf).read()
    assert ctrl.snapshot()['paused'] is True
    post('/action',action='add30',csrf=csrf).read()
    assert ctrl.snapshot()['allowed'] is True
    assert ctrl.snapshot()['remaining_seconds']==2700
    try:
        post('/local-grant',password='wrongpass',minutes='30').read()
        raise AssertionError('Wrong password accepted for local parent access')
    except urllib.error.HTTPError as e: assert e.code==403
    res=json.load(post('/local-grant',password='123456',minutes='15'))
    assert res['ok'] and ctrl.snapshot()['remaining_seconds']==3600
    assert json.load(op.open(urllib.request.Request(url+'/api/state',headers=token)))['child']=='max'
    try:
        op.open(url+'/api/state').read()
        raise AssertionError('Unauthenticated state API was accessible')
    except urllib.error.HTTPError as e: assert e.code==403
    try:
        req=urllib.request.Request(url+'/local-grant',data=urllib.parse.urlencode({'password':'123456','minutes':'60'}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
        op.open(req).read()
        raise AssertionError('Anonymous local-grant via proxy')
    except urllib.error.HTTPError as e: assert e.code==403
    assert 'pattern="[0-9]{6}"' in m.login_html()
    # Optional screen sharing cannot be accessed without a parent session;
    # the child must explicitly approve every request using the desktop token.
    assert ctrl.screen_state()['screen_status'] == 'idle'
    post('/action',action='request-screen',csrf=csrf).read()
    request_id = ctrl.screen_state(desktop=True)['screen_request']
    assert ctrl.screen_state()['screen_status'] == 'pending'
    assert 'screen_request' not in ctrl.screen_state()
    jpeg = b'\xff\xd8\xff' + bytes(140) + b'\xff\xd9'
    anon = urllib.request.Request(url+'/screen.jpg')
    try:
        urllib.request.urlopen(anon,context=ssl._create_unverified_context()).read()
        raise AssertionError('Unauthenticated parent preview was allowed')
    except urllib.error.HTTPError as e: assert e.code == 403
    unauth = urllib.request.Request(url+'/api/screen/upload',data=jpeg,
        headers={'Content-Type':'image/jpeg','X-ParentPilot-Screen-Request':request_id})
    try:
        op.open(unauth).read()
        raise AssertionError('Child screen image was accepted without local token')
    except urllib.error.HTTPError as e: assert e.code == 403
    authenticated = urllib.request.Request(url+'/api/screen/upload',data=jpeg,
        headers={'Content-Type':'image/jpeg','X-ParentPilot-Screen-Request':request_id,**token})
    assert op.open(authenticated).read() == b'OK'
    assert op.open(url+'/screen.jpg').read() == jpeg
    ctrl.screen_image_until = 0.0
    assert ctrl.get_screen() is None
    post('/action',action='request-screen',csrf=csrf).read()
    request_id = ctrl.screen_state(desktop=True)['screen_request']
    assert op.open(urllib.request.Request(url+'/api/screen/decline',
        data=urllib.parse.urlencode({'request':request_id}).encode(),
        headers={'Content-Type':'application/x-www-form-urlencoded',**token})).read() == b'OK'
    assert ctrl.screen_state()['screen_status'] == 'declined'
    s.shutdown()
    print('PASS: timer, persistence, pause, resume, unlimited, password, CSRF, parent web controls and local bonus time')
